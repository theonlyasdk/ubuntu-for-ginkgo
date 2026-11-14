find /sys -name '*panel_sleep*' 2>/dev/null
find /sys -name '*panel*' 2>/dev/null | grep -v '/module/' | head -n 30
