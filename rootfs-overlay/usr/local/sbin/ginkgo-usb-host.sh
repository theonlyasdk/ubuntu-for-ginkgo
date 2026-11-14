#!/bin/sh
# Switch ginkgo Type-C from RNDIS gadget (SSH) to USB host (keyboard/mouse).
# SSH over 192.168.7.2 will drop. Use an OTG adapter, then plug the device.
set -eu

ROLE=""
for r in /sys/class/usb_role/*/role; do
	if [ -e "$r" ]; then
		ROLE="$r"
		break
	fi
done

if [ -z "$ROLE" ]; then
	echo "error: usb role switch missing (need dr_mode=otg + usb-role-switch)" >&2
	exit 1
fi

# 1. Stop RNDIS gadget cleanly
systemctl stop usb-gadget-rndis.service 2>/dev/null || true
if [ -d /sys/kernel/config/usb_gadget/ginkgo ]; then
	echo "" > /sys/kernel/config/usb_gadget/ginkgo/UDC 2>/dev/null || true
fi

# 2. Switch role to host
echo host > "$ROLE"

# 3. Turn ON 5V VBUS boost power for OTG peripherals
VBUS_STATE=""
for s in /sys/bus/platform/devices/otg-vbus/state /sys/devices/platform/otg-vbus/state; do
	if [ -e "$s" ]; then
		VBUS_STATE="$s"
		break
	fi
done

if [ -n "$VBUS_STATE" ]; then
	echo enabled > "$VBUS_STATE"
	echo "VBUS 5V power: $(cat "$VBUS_STATE")"
else
	echo "warning: otg-vbus consumer not found in sysfs" >&2
fi

echo "Type-C is USB host with VBUS power ON. Plug OTG adapter + mouse/keyboard."
echo -n "role="; cat "$ROLE"
