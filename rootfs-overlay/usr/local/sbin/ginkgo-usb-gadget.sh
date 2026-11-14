#!/bin/sh
# Switch ginkgo Type-C back from USB host to RNDIS gadget (SSH / 192.168.7.2).
# Unplug OTG adapter before connecting to host PC!
set -eu

# 1. Turn OFF VBUS power first to avoid back-powering PC
for s in /sys/bus/platform/devices/otg-vbus/state /sys/devices/platform/otg-vbus/state; do
	if [ -e "$s" ]; then
		echo disabled > "$s" 2>/dev/null || true
		echo "VBUS 5V power: $(cat "$s")"
		break
	fi
done

# 2. Switch USB role back to device
for r in /sys/class/usb_role/*/role; do
	if [ -e "$r" ]; then
		echo device > "$r" 2>/dev/null || true
		echo -n "role="; cat "$r"
		break
	fi
done

# 3. Restart RNDIS gadget service
systemctl restart usb-gadget-rndis.service 2>/dev/null || true
echo "Type-C restored to USB device/gadget mode (SSH 192.168.7.2)."
