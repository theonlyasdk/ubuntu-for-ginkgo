cat /sys/devices/platform/soc@0/5e00000.display-subsystem/dsi-controller@5e14000/5e14000.panel/panel_sleep 2>/dev/null
cat /sys/class/drm/card0-DSI-1/status 2>/dev/null
cat /sys/class/drm/card0-DSI-1/enabled 2>/dev/null
cat /sys/class/drm/card0-DSI-1/dpms 2>/dev/null
cat /sys/class/backlight/*/brightness 2>/dev/null
ps aux | grep -E '(plasmashell|kwin)'
