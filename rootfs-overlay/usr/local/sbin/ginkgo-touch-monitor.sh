#!/bin/sh
# Monitor backlight brightness for screen unblank (display turn-on) events.
# When display unblanks after being at 0 brightness, trigger touch reload.

BL_PATH="/sys/class/backlight/ktd3136-backlight/actual_brightness"
TRIGGER="/sys/kernel/ginkgo_touch/resume"

was_blank=0

while true; do
    if [ -f "$BL_PATH" ] && [ -w "$TRIGGER" ]; then
        b=$(cat "$BL_PATH" 2>/dev/null || echo 1)
        if [ "$b" -eq 0 ]; then
            was_blank=1
        elif [ "$was_blank" -eq 1 ] && [ "$b" -gt 0 ]; then
            was_blank=0
            echo "ginkgo-touch-monitor: display unblanked, triggering touch resume..." > /dev/kmsg
            echo 1 > "$TRIGGER" 2>/dev/null || true
        fi
    fi
    sleep 0.5
done
