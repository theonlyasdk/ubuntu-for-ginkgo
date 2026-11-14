#!/bin/sh
# WCN3990 ROM ships without a valid factory BD address. Program a stable
# locally-administered one before bluetoothd starts; the kernel reprograms
# it on every power on (it is lost across power cycles).
# btmgmt hangs when stdin is /dev/null (systemd), so hold a pipe open.
ADDR=86:d2:39:0f:1e:ee

load_mod() {
    mod="$1"
    file="${2:-$mod.ko}"
    if ! grep -qw "$mod" /proc/modules 2>/dev/null; then
        modprobe "$mod" 2>/dev/null || insmod "/lib/modules/ginkgo-extra/$file" 2>/dev/null || true
    fi
}

# Crypto modules required for Bluetooth Secure Connections (SC) ECDH P-256 pairing
load_mod ecc ecc.ko
load_mod ecdh_generic ecdh_generic.ko

# Bluetooth profile modules (telephony / audio / networking / input)
load_mod rfcomm rfcomm.ko
load_mod bnep bnep.ko
load_mod hidp hidp.ko

bt() { (sleep 10 &) | timeout 2 btmgmt "$@"; }
i=0
while [ "$i" -lt 30 ]; do
    if bt info 2>/dev/null | grep -q hci0; then
        break
    fi
    sleep 0.5
    i=$((i+1))
done
bt power off >/dev/null 2>&1
bt public-addr "$ADDR" >/dev/null 2>&1
bt ssp on >/dev/null 2>&1
bt sc on >/dev/null 2>&1
bt power on >/dev/null 2>&1
