#!/bin/sh
# Ginkgo RTC synchronization helper
set -e

OFFSET_FILE="/etc/rtc-offset"
SYSFS_OFFSET="/sys/class/rtc/rtc0/device/offset"

case "${1:-start}" in
    start)
        OFFSET=0
        if [ -s "$OFFSET_FILE" ]; then
            OFFSET=$(cat "$OFFSET_FILE" 2>/dev/null || echo 0)
        fi

        if ! lsmod | grep -q rtc_pm8xxx; then
            insmod /lib/modules/ginkgo-extra/rtc-pm8xxx.ko offset="$OFFSET" 2>/dev/null || true
        fi

        if [ -f "$SYSFS_OFFSET" ] && [ "$OFFSET" -gt 0 ] 2>/dev/null; then
            echo "$OFFSET" > "$SYSFS_OFFSET" 2>/dev/null || true
        fi

        # Synchronize system clock from RTC
        if [ -e /dev/rtc0 ]; then
            hwclock -s --utc 2>/dev/null || true
        fi
        ;;

    stop|save)
        if [ -f "$SYSFS_OFFSET" ]; then
            cat "$SYSFS_OFFSET" > "$OFFSET_FILE"
        elif [ -e /dev/rtc0 ]; then
            # Calculate offset: system unix epoch minus rtc unix epoch
            SYS_SECS=$(date +%s)
            RTC_SECS=$(hwclock --get --utc 2>/dev/null | date -f - +%s 2>/dev/null || echo 0)
            if [ "$RTC_SECS" -gt 0 ]; then
                echo "$((SYS_SECS - RTC_SECS))" > "$OFFSET_FILE"
            fi
        fi
        ;;

    sync)
        # Update RTC from system time and save offset
        if [ -e /dev/rtc0 ]; then
            hwclock -w --utc 2>/dev/null || true
        fi
        if [ -f "$SYSFS_OFFSET" ]; then
            cat "$SYSFS_OFFSET" > "$OFFSET_FILE"
        fi
        ;;

    *)
        echo "Usage: $0 {start|stop|save|sync}"
        exit 1
        ;;
esac
