#!/bin/bash
# ==============================================================================
# Ginkgo ZRAM Swap Setup & Lifecycle Manager
# Target: Xiaomi Redmi Note 8 (SM6125 / trinket)
# Kernel: 7.0.0-00001-g62f9dac57de4-dirty #142 SMP PREEMPT
# ==============================================================================
set -euo pipefail

ZRAM_DEV="/dev/zram0"
ZRAM_SYS="/sys/block/zram0"

# ------------------------------------------------------------------------------
# Module Loader Helper
# Checks /sys/module/<name> and /proc/modules first.
# Attempts modprobe, then falls back to searching /lib/modules/ginkgo-extra,
# /lib/modules/$(uname -r), and /lib/modules recursively.
# ------------------------------------------------------------------------------
load_module() {
    local mod="$1"
    shift
    local mod_name="${mod%.ko}"
    local mod_sysfs="${mod_name//-/_}"

    # 1. Already loaded or statically built-in
    if [ -d "/sys/module/$mod_sysfs" ] || grep -qw "$mod_sysfs" /proc/modules 2>/dev/null; then
        return 0
    fi

    # 2. Try modprobe (works if modules.dep is up to date)
    if modprobe "$mod_name" "$@" 2>/dev/null; then
        return 0
    fi

    # 3. Fallback: scan candidate directories for .ko
    local kver
    kver=$(uname -r 2>/dev/null || echo "")
    local search_paths=(
        "/lib/modules/ginkgo-extra"
        "/lib/modules/$kver"
        "/lib/modules"
    )

    local ko_file=""
    for dir in "${search_paths[@]}"; do
        [ -d "$dir" ] || continue
        if [ -f "$dir/${mod_name}.ko" ]; then
            ko_file="$dir/${mod_name}.ko"
            break
        fi
        # Recursive lookup in subdirectories
        ko_file=$(find "$dir" -type f -name "${mod_name}.ko" 2>/dev/null | head -n 1)
        if [ -n "$ko_file" ] && [ -f "$ko_file" ]; then
            break
        fi
    done

    if [ -n "$ko_file" ] && [ -f "$ko_file" ]; then
        if insmod "$ko_file" "$@" 2>/dev/null; then
            return 0
        fi
    fi

    return 1
}

# ------------------------------------------------------------------------------
# Ensure Kernel Modules (Ordered by Dependency)
# ------------------------------------------------------------------------------
ensure_modules() {
    # 1. Compression backend dependencies (lz4_compress or lz4, optional zstd)
    load_module lz4_compress || load_module lz4 || true
    load_module zstd_compress || load_module zstd || true

    # 2. Memory allocator backend (zsmalloc) - Mandatory dependency for zram
    if ! load_module zsmalloc; then
        echo "ERROR: Failed to load zsmalloc module" >&2
        return 1
    fi

    # 3. ZRAM driver - instantiated with num_devices=1
    if ! load_module zram num_devices=1; then
        # Try without module options if parameter rejected
        if ! load_module zram; then
            echo "ERROR: Failed to load zram module" >&2
            return 1
        fi
    fi

    # 4. Device allocation if /sys/block/zram0 was not created automatically
    if [ ! -d "$ZRAM_SYS" ] && [ -f /sys/class/zram-control/hotadd ]; then
        cat /sys/class/zram-control/hotadd >/dev/null 2>&1 || true
    fi

    # Wait for device node creation
    local attempts=30
    while [ ! -b "$ZRAM_DEV" ] && [ "$attempts" -gt 0 ]; do
        sleep 0.1
        attempts=$((attempts - 1))
    done

    if [ ! -b "$ZRAM_DEV" ]; then
        echo "ERROR: $ZRAM_DEV block device node failed to materialize" >&2
        return 1
    fi

    return 0
}

# ------------------------------------------------------------------------------
# Dynamic Size Calculator (50% RAM, baseline 2GB for Ginkgo ~3.5GB)
# ------------------------------------------------------------------------------
calculate_disksize() {
    local mem_total_kb
    mem_total_kb=$(awk '/^MemTotal:/ {print $2}' /proc/meminfo 2>/dev/null || echo "")

    if [ -n "$mem_total_kb" ] && [ "$mem_total_kb" -gt 0 ] 2>/dev/null; then
        local half_ram_mb=$(( mem_total_kb / 2048 ))
        # For standard ~3.5GB ginkgo userdata layout, target 2G
        if [ "$half_ram_mb" -ge 1600 ] && [ "$half_ram_mb" -le 2200 ]; then
            echo "2G"
        else
            echo "${half_ram_mb}M"
        fi
    else
        echo "2G"
    fi
}

# ------------------------------------------------------------------------------
# Compression Algorithm Selection (lz4 > zstd > lzo-rle > lzo)
# ------------------------------------------------------------------------------
configure_compression() {
    local comp_file="$ZRAM_SYS/comp_algorithm"
    [ -f "$comp_file" ] || return 0

    local supported
    supported=$(cat "$comp_file" 2>/dev/null || echo "")

    if echo "$supported" | grep -qw "lz4"; then
        echo lz4 > "$comp_file" 2>/dev/null || true
    elif echo "$supported" | grep -qw "zstd"; then
        echo zstd > "$comp_file" 2>/dev/null || true
    elif echo "$supported" | grep -qw "lzo-rle"; then
        echo lzo-rle > "$comp_file" 2>/dev/null || true
    fi
}

# ------------------------------------------------------------------------------
# Sysctl VM Tuning for ZRAM on Kryo 260
# ------------------------------------------------------------------------------
apply_sysctl_tuning() {
    # vm.swappiness = 100: balance anon swap against pagecache eviction
    sysctl -w vm.swappiness=100 >/dev/null 2>&1 || true

    # vm.page-cluster = 0: 1-page (4KB) readahead; zero latency penalty for RAM decomp
    sysctl -w vm.page-cluster=0 >/dev/null 2>&1 || true

    # vm.watermark_boost_factor = 0: eliminate memory compaction stutter during allocations
    sysctl -w vm.watermark_boost_factor=0 >/dev/null 2>&1 || true

    # vm.vfs_cache_pressure = 50: preserve directory and inode metadata in memory
    sysctl -w vm.vfs_cache_pressure=50 >/dev/null 2>&1 || true
}

# ------------------------------------------------------------------------------
# Start Action
# ------------------------------------------------------------------------------
start_zram() {
    # Check if already active swap
    if grep -q "zram0" /proc/swaps 2>/dev/null; then
        echo "zram0 is already active as swap"
        apply_sysctl_tuning
        exit 0
    fi

    # Ensure kernel modules and block device node
    if ! ensure_modules; then
        echo "ERROR: Failed to initialize zram hardware device" >&2
        exit 1
    fi

    # Clean reset if device is in a dirty/partial state
    local cur_size
    cur_size=$(cat "$ZRAM_SYS/disksize" 2>/dev/null || echo 0)
    if [ "$cur_size" -gt 0 ] 2>/dev/null; then
        swapoff "$ZRAM_DEV" 2>/dev/null || true
        echo 1 > "$ZRAM_SYS/reset" 2>/dev/null || true
    fi

    # Configure optimal compression backend before setting disksize
    configure_compression

    # Set calculated disksize
    local target_size
    target_size=$(calculate_disksize)
    if ! echo "$target_size" > "$ZRAM_SYS/disksize" 2>/dev/null; then
        echo "ERROR: Failed to set disksize $target_size on $ZRAM_SYS/disksize" >&2
        exit 1
    fi

    # Initialize swap signature
    if ! mkswap -L zram0 "$ZRAM_DEV" >/dev/null 2>&1; then
        echo "ERROR: Failed to mkswap on $ZRAM_DEV" >&2
        echo 1 > "$ZRAM_SYS/reset" 2>/dev/null || true
        exit 1
    fi

    # Activate swap with high priority (100)
    if ! swapon -p 100 "$ZRAM_DEV" 2>/dev/null; then
        echo "ERROR: Failed to swapon $ZRAM_DEV" >&2
        echo 1 > "$ZRAM_SYS/reset" 2>/dev/null || true
        exit 1
    fi

    # Apply sysctl memory tuning
    apply_sysctl_tuning

    local active_alg
    active_alg=$(cat "$ZRAM_SYS/comp_algorithm" 2>/dev/null | grep -o '\[.*\]' | tr -d '[]' || echo "default")
    echo "ZRAM swap ($target_size, $active_alg, priority 100) active on $ZRAM_DEV"
}

# ------------------------------------------------------------------------------
# Stop Action
# ------------------------------------------------------------------------------
stop_zram() {
    echo "Deactivating ZRAM swap..."
    if grep -q "zram0" /proc/swaps 2>/dev/null; then
        swapoff "$ZRAM_DEV" 2>/dev/null || true
    fi

    if [ -f "$ZRAM_SYS/reset" ]; then
        echo 1 > "$ZRAM_SYS/reset" 2>/dev/null || true
    fi

    echo "ZRAM swap deactivated and memory reset."
}

# ------------------------------------------------------------------------------
# Status Action
# ------------------------------------------------------------------------------
status_zram() {
    echo "=== Ginkgo ZRAM Swap Status ==="
    if grep -q "zram0" /proc/swaps 2>/dev/null; then
        grep "zram0" /proc/swaps
    else
        echo "zram0 swap: NOT ACTIVE"
    fi

    if [ -d "$ZRAM_SYS" ]; then
        echo "Algorithm: $(cat "$ZRAM_SYS/comp_algorithm" 2>/dev/null || echo 'N/A')"
        echo "Disk Size: $(cat "$ZRAM_SYS/disksize" 2>/dev/null || echo 'N/A') bytes"
        if [ -f "$ZRAM_SYS/mm_stat" ]; then
            echo "MM Stat:   $(cat "$ZRAM_SYS/mm_stat" 2>/dev/null)"
        fi
    fi

    echo "Sysctl vm.swappiness: $(sysctl -n vm.swappiness 2>/dev/null || echo 'N/A')"
    echo "Sysctl vm.page-cluster: $(sysctl -n vm.page-cluster 2>/dev/null || echo 'N/A')"
    echo "Sysctl vm.watermark_boost_factor: $(sysctl -n vm.watermark_boost_factor 2>/dev/null || echo 'N/A')"
}

# ------------------------------------------------------------------------------
# Main Dispatcher
# ------------------------------------------------------------------------------
case "${1:-start}" in
    start)
        start_zram
        ;;
    stop)
        stop_zram
        ;;
    restart)
        stop_zram
        start_zram
        ;;
    status)
        status_zram
        ;;
    *)
        echo "Usage: $0 {start|stop|restart|status}" >&2
        exit 1
        ;;
esac
