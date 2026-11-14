#!/bin/bash
# CPU / GPU power profile for ginkgo.
#
# Usage:
#   ginkgo-power-mode.sh                 apply the profile from /etc/ginkgo-power-mode.conf
#   ginkgo-power-mode.sh performance     pin every core and the Adreno at maximum
#   ginkgo-power-mode.sh balanced        default: schedutil, frequencies follow the load
#   ginkgo-power-mode.sh eco             minimum frequencies, deep idle states allowed
#
# Why this exists: ginkgo-performance.service pinned all eight cores to
# "performance" and the Adreno 610 to max_freq for the entire session. That is
# fine for a demo and terrible for a battery - the SoC then idles around 40 C
# and the 4000 mAh cell is gone in a couple of hours. The image now starts in
# "balanced"; maximum is one command away.
#
# The choice is remembered in /etc/ginkgo-power-mode.conf so it survives a
# reboot.
set -eu

CONF=/etc/ginkgo-power-mode.conf
DEFAULT=balanced

usage() {
	echo "usage: $0 [performance|balanced|eco]" >&2
	echo "  (no argument) applies the profile stored in $CONF" >&2
}

case "${1:-}" in
	-h|--help|help)
		usage
		exit 0
		;;
esac

mode="${1:-}"
if [ -z "$mode" ]; then
	mode="$(tr -d '[:space:]' < "$CONF" 2>/dev/null || true)"
	[ -n "$mode" ] || mode="$DEFAULT"
fi

case "$mode" in
	performance|balanced|eco) ;;
	*)
		usage
		echo "error: unknown profile '$mode'" >&2
		exit 2
		;;
esac

# Remember an explicitly requested profile.
if [ $# -ge 1 ]; then
	mkdir -p "$(dirname "$CONF")"
	echo "$mode" > "$CONF"
fi

# ---------------------------------------------------------------- helpers
have() { grep -qw "$1" "$2" 2>/dev/null; }

set_cpu_governor() {
	gov="$1"
	for p in /sys/devices/system/cpu/cpufreq/policy*; do
		[ -d "$p" ] || continue
		# keep every core online: the big cluster has to be able to come up
		for c in "$p"/../cpu[0-9]*/online; do
			[ -w "$c" ] && echo 1 > "$c" 2>/dev/null || true
		done
		if have "$gov" "$p/scaling_available_governors"; then
			echo "$gov" > "$p/scaling_governor" 2>/dev/null || true
		elif [ "$gov" = schedutil ] && have powersave "$p/scaling_available_governors"; then
			# no schedutil: powersave still scales with the load
			echo powersave > "$p/scaling_governor" 2>/dev/null || true
		fi
	done
}

set_devfreq_governor() {
	dev="$1"
	gov="$2"
	[ -d "$dev" ] || return 0
	if [ -w "$dev/governor" ] && have "$gov" "$dev/available_governors"; then
		echo "$gov" > "$dev/governor" 2>/dev/null || true
	fi
}

set_cpuidle() {
	# $1 = "deep" keeps the deep idle states, "shallow" drops them
	state="$1"
	for d in /sys/devices/system/cpu/cpu[0-9]*/cpuidle; do
		[ -d "$d" ] || continue
		for s in "$d"/state*; do
			[ -w "$s" ] || continue
			case "$state" in
				deep) echo 1 > "$s" 2>/dev/null || true ;;
				shallow) echo 0 > "$s" 2>/dev/null || true ;;
			esac
		done
	done
}

GPU=/sys/class/devfreq/5900000.gpu

# ---------------------------------------------------------------- profiles
case "$mode" in
	performance)
		set_cpu_governor performance
		set_cpuidle shallow
		if [ -d "$GPU" ]; then
			set_devfreq_governor "$GPU" userspace
			if [ -w "$GPU/userspace/set_freq" ]; then
				cat "$GPU/max_freq" > "$GPU/userspace/set_freq" 2>/dev/null || true
			fi
		fi
		for dev in /sys/class/devfreq/*; do
			[ -d "$dev" ] || continue
			set_devfreq_governor "$dev" performance
		done
		;;
	balanced)
		set_cpu_governor schedutil
		set_cpuidle deep
		if [ -d "$GPU" ]; then
			set_devfreq_governor "$GPU" schedutil
			set_devfreq_governor "$GPU" simple
		fi
		for dev in /sys/class/devfreq/*; do
			[ -d "$dev" ] || continue
			set_devfreq_governor "$dev" schedutil
		done
		;;
	eco)
		set_cpu_governor powersave
		set_cpuidle deep
		if [ -d "$GPU" ]; then
			set_devfreq_governor "$GPU" powersave
			set_devfreq_governor "$GPU" simple
		fi
		for dev in /sys/class/devfreq/*; do
			[ -d "$dev" ] || continue
			set_devfreq_governor "$dev" powersave
		done
		;;
esac

echo "ginkgo power profile: $mode"
for p in /sys/devices/system/cpu/cpufreq/policy*; do
	[ -d "$p" ] || continue
	echo "  cpu $(cat "$p/related_cpus" 2>/dev/null): $(cat "$p/scaling_governor" 2>/dev/null) @ $(cat "$p/scaling_cur_freq" 2>/dev/null) Hz"
done
if [ -d "$GPU" ]; then
	echo "  gpu: $(cat "$GPU/governor" 2>/dev/null) @ $(cat "$GPU/cur_freq" 2>/dev/null) Hz"
fi
