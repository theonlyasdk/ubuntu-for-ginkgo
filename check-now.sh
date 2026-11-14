ps -ef | grep -E '(plasma|kwin|sddm)'
journalctl -b _UID=1000 -u plasma-plasmashell.service -n 20 --no-pager
