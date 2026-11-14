systemd-analyze blame | head -n 25
systemd-analyze critical-chain
journalctl -b _UID=1000 -n 40 --no-pager
