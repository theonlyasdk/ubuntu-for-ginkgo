#!/bin/bash
# Apply IN regulatory domain (India) and ensure wlan0 is configured after
# MPSS and ath10k bring-up.
# Do not bounce wlan0 (down/up): dynamic interface bouncing races with ath10k
# scan/vdev state and crashes WLAN.HL.3.x firmware during bring-up.
set -euo pipefail

# Wait for wlan0 net device to be registered by ath10k/MPSS (up to 60s)
for _ in $(seq 1 60); do
	[[ -d /sys/class/net/wlan0 ]] && break
	sleep 1
done

if [[ ! -d /sys/class/net/wlan0 ]]; then
	echo "ginkgo-wifi-setup: wlan0 interface did not appear within 60s" >&2
	exit 0
fi

# Wait for wireless regulatory database (up to 60s)
for _ in $(seq 1 60); do
	[[ -e /lib/firmware/regulatory.db ]] && break
	sleep 1
done

if [[ -e /lib/firmware/regulatory.db ]]; then
	iw reg reload >/dev/null 2>&1 || true
	iw reg set IN >/dev/null 2>&1 || true
fi

# Verify active MAC address (provided by modem NVRAM/MPSS to ath10k)
CURRENT_MAC=$(cat /sys/class/net/wlan0/address 2>/dev/null || true)
if [[ -n "$CURRENT_MAC" ]]; then
	logger -t ginkgo-wifi-setup "wlan0 active MAC: $CURRENT_MAC, regulatory domain: IN"
fi
