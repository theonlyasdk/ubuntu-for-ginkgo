#!/bin/bash
set -eu

# Ensure all 8 cores are online
for c in /sys/devices/system/cpu/cpu[0-9]*; do
  [ -f "$c/online" ] && echo 1 > "$c/online" 2>/dev/null || true
done

# Set CPU scaling governor to performance
for p in /sys/devices/system/cpu/cpufreq/policy*; do
  if [ -d "$p" ]; then
    echo performance > "$p/scaling_governor" 2>/dev/null || true
  fi
done

# Set GPU (Adreno 610) to peak frequency (950 MHz)
if [ -d /sys/class/devfreq/5900000.gpu ]; then
  echo userspace > /sys/class/devfreq/5900000.gpu/governor 2>/dev/null || true
  cat /sys/class/devfreq/5900000.gpu/max_freq > /sys/class/devfreq/5900000.gpu/userspace/set_freq 2>/dev/null || true
fi

# Set any other devfreq devices supporting performance
for dev in /sys/class/devfreq/*; do
  [ -d "$dev" ] || continue
  if grep -qw performance "$dev/available_governors" 2>/dev/null; then
    echo performance > "$dev/governor" 2>/dev/null || true
  fi
done

echo "Ginkgo full performance mode engaged"
