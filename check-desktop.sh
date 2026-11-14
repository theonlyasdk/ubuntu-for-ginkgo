systemctl status sddm
ps aux | grep -E '(sddm|plasma|kwin|Xwayland)'
systemctl is-active graphical.target
dmesg | tail -n 30
