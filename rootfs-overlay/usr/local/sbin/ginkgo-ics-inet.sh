#!/bin/sh
# Add ICS secondary IP + route + DNS after the RNDIS gadget comes up.
# Use metric 2000 so that Wi-Fi (metric 600) has default-route precedence.
sleep 3
ip addr add 192.168.137.50/24 dev usb0 2>/dev/null || true
ip route replace default via 192.168.137.1 dev usb0 metric 2000 2>/dev/null || true
if ! grep -q nameserver /etc/resolv.conf 2>/dev/null; then
	printf "nameserver 8.8.8.8\nnameserver 1.1.1.1\n" > /etc/resolv.conf
fi
