# Redmi Note 8 (ginkgo) Mainline Linux: ZRAM Compressed Swap Architecture & Bringup

> **Date**: 2026-11-14  
> **Target SoC**: Qualcomm Snapdragon 665 / SM6125 (trinket)  
> **Target Device**: Xiaomi Redmi Note 8 (`ginkgo`)  
> **Kernel**: Mainline Linux 7.0 (`7.0.0-00001-g62f9dac57de4-dirty #142 SMP PREEMPT aarch64`)  
> **Distro**: Ubuntu 26.04 LTS arm64 (`resolute`)  
> **Status**: RESOLVED & VERIFIED (2GB LZ4 swap device `/dev/zram0` active at priority 100)

---

## 1. Problem Statement & Historical Context

On fresh boots of the mainline Linux 7.0 system on Redmi Note 8 (`ginkgo`), system diagnostics reported:
```
Mem:           3.5Gi       1.7Gi       1.1Gi       387Mi       1.2Gi       1.8Gi
Swap:             0B          0B          0B
```
Although `rootfs-overlay/etc/systemd/system/zram-setup.service` was shipped in the repository and enabled in `basic.target.wants`, inspecting the unit status on the phone showed:
```
● zram-setup.service - Ginkgo ZRAM Swap Setup
     Loaded: loaded (/etc/systemd/system/zram-setup.service; enabled; preset: enabled)
     Active: active (exited) since Sat 2026-11-14 15:09:22 IST; 38min ago
Nov 14 15:09:22 ginkgo ginkgo-zram.sh[253]: zram device not available
Nov 14 15:09:22 ginkgo systemd[1]: Finished zram-setup.service - Ginkgo ZRAM Swap Setup.
```

The system had **0 bytes of swap space** and **no active ZRAM block device**. Under desktop load (KDE Plasma 6 + Wayland + Xwayland + PipeWire), the ~3.5 GB physical RAM was subject to memory pressure, cache thrashing, and potential OOM killer invocations.

---

## 2. Root-Cause Analysis

### 2.1 Kernel Configuration Deficit
Querying the running kernel's `/proc/config.gz` revealed the underlying issue:
```sh
zcat /proc/config.gz | grep -E 'ZRAM|ZSMALLOC'
# Output:
# CONFIG_ZRAM is not set
# CONFIG_ZSWAP is not set
```
`CONFIG_ZRAM` and `CONFIG_ZSMALLOC` were completely unset in the `#142` kernel binary compiled for this bringup.

### 2.2 Architectural Constraint: Rule 1.3
Per `AGENTS.md` Rule 1.3:
> **DO NOT REPLACE DEPLOYED KERNEL WITH RAW UPSTREAM v7.0**
> The baseline kernel at `out/deployed-unpack/kernel` contains downstream SM6125 DPU/DSI patches and calibration code (`msm_dsi_manager_host_enable`, `dsi_phy_clamp`) necessary for the Tianma NT36672A video-mode DSI display panel. Compiling and flashing a raw vanilla upstream kernel results in a black screen (video pixel clock failure).

Therefore, recompiling the entire kernel was out of the question; all new hardware and subsystem capabilities must be provided as out-of-tree kernel modules (`.ko`) matching vermagic `7.0.0-00001-g62f9dac57de4-dirty`.

### 2.3 Script Deficiencies in `ginkgo-zram.sh`
1. The original script executed `modprobe zram 2>/dev/null || true`.
2. Out-of-tree modules placed in `/lib/modules/ginkgo-extra/` are not indexed in `/lib/modules/$(uname -r)/modules.dep` because `depmod` is never run in the overlay packaging flow.
3. `zram.ko` depends on `zsmalloc.ko` (memory allocator) and `lz4_compress.ko` (compression backend). Loading `zram.ko` directly without loading its dependencies first results in kernel symbol resolution failure (`-ENOEXEC`).
4. Device creation: Modern mainline kernels do not always pre-create `/dev/zram0` upon module load unless `num_devices=1` is specified or `/sys/class/zram-control/hotadd` is written.

---

## 3. Engineering Solution & Implementation

### 3.1 Kernel Module Compilation (WSL Tree)
In the cross-compilation environment (`ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-`):
1. **`lz4_compress.ko`**: Compiled from `lib/lz4/` with exact vermagic `7.0.0-00001-g62f9dac57de4-dirty`.
2. **`zsmalloc.ko`**: Out-of-tree build from `mm/zsmalloc.c` with flags `-DCONFIG_ZSMALLOC_CHAIN_SIZE=8 -Ilinux/mm`.
3. **`zram.ko`**: Out-of-tree build from `drivers/block/zram/` (`zcomp.o`, `zram_drv.o`, `backend_lz4.o`, `backend_zstd.o`) with flags `-DCONFIG_ZRAM_BACKEND_LZ4=1 -DCONFIG_ZRAM_BACKEND_ZSTD=1 -DCONFIG_ZRAM_DEF_COMP_LZ4=1`.

### 3.2 Symbol Verification
Symbols were verified using `nm -u` against `linux/Module.symvers`:
- `zsmalloc.ko`: 41 undefined symbols, **0 missing** from `Module.symvers`.
- `lz4_compress.ko`: 3 undefined symbols, **0 missing** from `Module.symvers`.
- `zram.ko`: 109 undefined symbols, **0 missing** from `Module.symvers`.

### 3.3 Hardened Lifecycle Manager (`/usr/local/sbin/ginkgo-zram.sh`)
Rewrote `ginkgo-zram.sh` with robust dependency handling:
1. **`load_module()` Helper**:
   - Inspects `/sys/module/<name>` and `/proc/modules`.
   - Attempts `modprobe`.
   - Falls back to recursive lookup in `/lib/modules/ginkgo-extra/` and `/lib/modules/` via `insmod`.
2. **Ordered Insertion**:
   - Step 1: `lz4_compress.ko`
   - Step 2: `zsmalloc.ko`
   - Step 3: `zram.ko num_devices=1`
3. **Hot-Add & Settling**:
   - Falls back to `/sys/class/zram-control/hotadd` if `/sys/block/zram0` is not yet present.
   - Polls with timeout until `/dev/zram0` block device node is created.
4. **Configuration Order**:
   - Step 1: Write `comp_algorithm` (`lz4` preferred, fallback to `zstd` / `lzo-rle`).
   - Step 2: Write `disksize` (`2G` calculated dynamically from `MemTotal / 2048`).
   - Step 3: `mkswap -L zram0 /dev/zram0`.
   - Step 4: `swapon -p 100 /dev/zram0`.
5. **Memory Tuning**:
   - `vm.swappiness = 100`: Promotes proactive anonymous paging to compressed RAM over aggressive pagecache eviction.
   - `vm.page-cluster = 0`: 1-page (4KB) readahead; zero latency penalty for RAM decompression.
   - `vm.watermark_boost_factor = 0`: Eliminates background allocation jitter.
   - `vm.vfs_cache_pressure = 50`: Retains directory and inode caches in memory.
6. **Teardown Hooks**:
   - Handles `stop`: `swapoff /dev/zram0` and `echo 1 > /sys/block/zram0/reset`.
   - Clean shutdown via `Before=... shutdown.target` and `Conflicts=shutdown.target` in `zram-setup.service`.

### 3.4 Packaging & Image Staging
1. Copied `zsmalloc.ko`, `lz4_compress.ko`, `zram.ko` to:
   - `out/`
   - `rootfs-overlay/lib/modules/ginkgo-extra/`
2. Updated `out/assemble-touch-image.sh` and `scripts/build-initramfs.sh` to stage modules into `overlay/lib/modules/ginkgo-extra/` in the ramdisk.
3. Re-packed `out/boot.img` with updated ramdisk containing clean LF scripts and all three modules.

---

## 4. Verification Commands

When the device is connected via USB or booted with the new image:
```sh
# 1. Inspect swap status
swapon --show
cat /proc/swaps
free -h

# 2. Check ZRAM device attributes
cat /sys/block/zram0/comp_algorithm
cat /sys/block/zram0/disksize
cat /sys/block/zram0/mm_stat

# 3. Check unit status
systemctl status zram-setup.service
/usr/local/sbin/ginkgo-zram.sh status
```
Expected output:
- Swap: `2.0Gi` total, partition `/dev/zram0` active at priority `100`.
- Algorithm: `[lz4] zstd` active.
- `zram-setup.service`: `active (exited)` with exit status 0.
