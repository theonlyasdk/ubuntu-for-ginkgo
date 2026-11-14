dmesg | grep -iE 'drm|dsi|panel|tianma|msm_dsi|novatek' | tail -n 30
systemctl status sddm --no-pager
journalctl -u sddm -n 30 --no-pager
