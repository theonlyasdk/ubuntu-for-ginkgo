# Redmi Note 8 (ginkgo) Bluetooth & Audio Bringup Chronicle (2026-11-14)

> Device: Xiaomi Redmi Note 8 (codenamed `ginkgo`)  
> SoC: Qualcomm Snapdragon 665 / SM6125 (trinket)  
> Bluetooth Controller: Qualcomm WCN3990 combo (Wi-Fi + BT)  
> System: Mainline Linux 7.0 (`7.0.0-00001-g62f9dac57de4-dirty #142 SMP PREEMPT aarch64`), Ubuntu 26.04 LTS (`resolute`)  
> Audio Framework: PipeWire 1.0+ with WirePlumber session manager  

---

## 1. Executive Summary

This document records the architectural findings, hardware catches, kernel module requirements, and discovery mechanisms uncovered during the bringup of Bluetooth and wireless audio (A2DP) on mainline Linux for the Redmi Note 8 (`ginkgo`).

Key accomplishments:
1. Located factory Bluetooth firmware stored on raw EMMC partition 36 (`/dev/mmcblk0p36`, labeled `bluetooth`).
2. Identified and resolved missing cryptographic kernel modules (`ecc.ko`, `ecdh_generic.ko`) and profile drivers (`rfcomm.ko`, `bnep.ko`, `hidp.ko`) required by BlueZ for Secure Simple Pairing (SSP) and LE Secure Connections.
3. Analyzed WCN3990 ROM mode vs Rampatch NVM operation under the `#142` mainline kernel.
4. Solved persistent BD address assignment via `bt-set-addr.sh` and systemd drop-in `bluetooth.service.d/bdaddr.conf`.
5. Analyzed the behavioral physics and pairing protocols of modern dual-mode wireless headsets (OnePlus Bullets Wireless Z2), including BLE Google Fast Pair Service (GFPS) advertising (`ADV_IND`), BR/EDR A2DP audio profiles, and D-Bus authentication agent requirements.
6. Resolved USB Type-C OTG Host vs Device role switching, VBUS 5V regulator control, and Gadget UDC re-binding logic to prevent network loss.

---

## 2. Hardware Architecture & WCN3990 UART Link

The Qualcomm WCN3990 is a single-die combo chip providing dual-band 802.11ac Wi-Fi and Bluetooth 5.0. On SM6125:
- **Transport Bus**: Connected via Qualcomm Universal Peripheral UART instance 9 (`qup_uart9`, device node `/dev/ttyMSM1`).
- **Power Management**: Managed by PMIC regulators (`vdd-io`, `vdd-core`, `vdd-pa`) and clock lines (`cxo_24m`).
- **Kernel Driver**: `hci_qca.ko` (`drivers/bluetooth/hci_qca.c`), interacting with `qcom-wcnss-core`.

### 2.1 The `#142` Kernel ROM Mode Fix

Under downstream Android, Little Kernel and initscripts download a TLV firmware patch (`crbtfw12.tlv`) and NVM configuration (`crnv12.bin`) across UART at 3.2 Mbps. On mainline Linux 7.0, the kernel patch `0003-wcn3990-bt-rom-mode-fix.patch` sets:
```c
qca_skip_fw = true;
qca_skip_oper_speed = true;
```
This bypasses firmware rampatch loading over UART and operates the controller in base ROM mode at 115200 baud.

### 2.2 Factory EMMC Firmware Partition

The factory firmware for all WCN3990 revisions is embedded on the device's internal storage:
- **Block Device**: `/dev/mmcblk0p36`
- **Filesystem**: VFAT (label `bluetooth`)
- **Mount Point**: `/mnt/bt` (or `/lib/firmware/qca/`)
- **Extracted Images**:
  - `crbtfw11.tlv`, `crbtfw20.tlv`, `crbtfw21.tlv`, `cmbtfw12.tlv`
  - `crnv11.bin`, `crnv20.bin`, `crnv21.bin`, `cmnv12.bin`
- **Verification**: Byte-for-byte SHA256 comparison verified that `/lib/firmware/qca/crbtfw12.tlv` (44,955 bytes) and `crnv12.bin` (2,590 bytes) are identical to the onboard vendor images.

---

## 3. Cryptographic Primitives & Profile Modules

Upstream BlueZ (`bluetoothd`) requires Linux kernel cryptographic algorithms to complete Secure Simple Pairing (SSP) and Elliptic Curve Diffie-Hellman (ECDH) key exchanges. Without these modules:
- Pairing requests immediately abort with `org.bluez.Error.Failed` or silent disconnect.
- Profiles like RFCOMM (serial / AT commands), BNEP (networking), and HIDP (keyboards / mice) fail to instantiate sockets.

Because `#142` kernel did not build these modules into the core `Image`, out-of-tree modules matching kernel vermagic `7.0.0-00001-g62f9dac57de4-dirty` are stored in `/lib/modules/ginkgo-extra/`:

| Module | Purpose |
|--------|---------|
| `ecc.ko` | Elliptic Curve Cryptography core algorithms |
| `ecdh_generic.ko` | ECDH key agreement primitive for Bluetooth 4.2+ LE Secure Connections |
| `rfcomm.ko` | RFCOMM protocol layer for headset control and serial comms |
| `bnep.ko` | Bluetooth Network Encapsulation Protocol for PAN tethering |
| `hidp.ko` | Bluetooth Human Interface Device Profile |

These are loaded at boot before `bluetooth.service` by `ginkgo-bt-modules.service`:
```ini
[Unit]
Description=Ginkgo Bluetooth Extra Kernel Modules
DefaultDependencies=no
Before=bluetooth.service
After=systemd-modules-load.service

[Service]
Type=oneshot
ExecStart=/sbin/modprobe -a ecc ecdh_generic rfcomm bnep hidp
RemainAfterExit=yes

[Install]
WantedBy=bluetooth.target
```

---

## 4. Persistent BD Address Programming

In ROM mode, the WCN3990 powers up with an uninitialized BD address (often `00:00:00:00:00:00` or random unassigned bytes). This causes:
1. Bluetooth host identification to change every boot.
2. Previously paired devices failing to recognize the phone.
3. BlueZ clearing its state cache.

To resolve this, a systemd drop-in `/etc/systemd/system/bluetooth.service.d/bdaddr.conf` invokes `/usr/local/sbin/bt-set-addr.sh` prior to starting `bluetoothd`:
```sh
#!/bin/bash
# bt-set-addr.sh: Program stable BD address and enable SSP/SC
DEV="hci0"
ADDR="86:D2:39:0F:1E:EE"

btmgmt --index "$DEV" power off 2>/dev/null || true
btmgmt --index "$DEV" public-addr "$ADDR"
btmgmt --index "$DEV" ssp on
btmgmt --index "$DEV" sc on
btmgmt --index "$DEV" le on
btmgmt --index "$DEV" connectable on
btmgmt --index "$DEV" discov on
btmgmt --index "$DEV" power on
```
This assigns a stable locally-administered MAC (`86:D2:39:0F:1E:EE`) and ensures SSP and LE capabilities are advertised.

---

## 5. Dual-Mode Headset Behavior (OnePlus Bullets Wireless Z2)

Modern Bluetooth audio headsets exhibit complex multi-transport states that affect automated pairing:

### 5.1 Magnetic Switch & Reconnection Mode
- When the magnetic earbuds are joined, the headset powers down.
- When separated without holding the pairing button, the headset enters **Reconnection Mode**:
  - Paging is targeted strictly to previously bonded masters (e.g. host PC).
  - Paging attempts from unknown addresses receive no response, resulting in `HCI Event: Connect Complete: Status: Page Timeout (0x04)`.
- Holding the physical multifunction button for 3 seconds puts the headset into **Pairing Mode**:
  - White LED blinks continuously.
  - Page scan parameters switch to continuous listening.
  - Inactivity timeout: Pairing mode automatically expires after 60 to 120 seconds.

### 5.2 Google Fast Pair & Dual-Mode Transport
- In pairing mode, the headset broadcasts BLE Undirected Connectable advertisements (`ADV_IND`) containing Service Data UUID `0xFE2C` (Google Fast Pair Service, GFPS).
- BlueZ discovery captures these advertisements via LE passive scan (`RSSI -47 dBm`).
- A2DP audio profiles (`0000110b-0000-1000-8000-00805f9b34fb`) operate exclusively over Classic BR/EDR.
- **Trap**: If BlueZ sets `LastUsedBearer=le` and attempts an LE-only link without Cross-Transport Key Derivation (CTKD), audio profiles will not bind. Devices must have `SupportedTechnologies=BR/EDR;LE;` and initiate classic ACL connection for PipeWire A2DP endpoints.

### 5.3 Automated Authentication Agent
BlueZ requires an interactive D-Bus Agent to authorize pairings:
- Headset pairing triggers an agent confirmation prompt (`DisplayYesNo` or `AuthorizeService`).
- Without an active agent, the pairing request stalls and fails with `org.bluez.Error.ConnectionAttemptFailed`.
- Automated testing requires a background Python agent (`pair_agent.py`) or `bluetoothctl` running with `agent on` and `default-agent` to reply `yes`.

---

## 6. USB OTG Host vs Device Gadget Switching Mechanics

The Type-C controller on SM6125 (`4e00000.usb`) supports dual-role switching. Improper role transitions can break the RNDIS USB network.

### 6.1 Switching to Host Mode (OTG Keyboard/Mouse)
Script: `/usr/local/sbin/ginkgo-usb-host.sh`
1. Enables 5V VBUS boost regulator:
   ```sh
   echo enabled > /sys/bus/platform/devices/otg-vbus/state
   ```
2. Switches controller role to host:
   ```sh
   echo host > /sys/class/usb_role/4e00000.usb-role-switch/role
   ```
3. UDC gadget is automatically detached. USB RNDIS network drops.

### 6.2 Restoring Device Gadget Mode (SSH & Network)
To recover the network without a full hardware reboot:
1. Disable VBUS 5V boost regulator:
   ```sh
   echo disabled > /sys/bus/platform/devices/otg-vbus/state
   ```
2. Switch controller role back to device:
   ```sh
   echo device > /sys/class/usb_role/4e00000.usb-role-switch/role
   ```
3. Re-bind UDC driver:
   ```sh
   echo 4e00000.usb > /sys/kernel/config/usb_gadget/ginkgo/UDC
   ```
4. In `/usr/local/sbin/usb-gadget-rndis.sh`, `setup_gadget()` has been enhanced to check if the configfs directory exists, and if so, safely re-binds `$GADGET/UDC` rather than failing.

---

## 7. Dual-Path Network & SSH Automation

Host-to-phone communication is supported through two simultaneous interfaces:
1. **USB RNDIS (`usb0`)**: `192.168.7.2` (Host: `192.168.7.1`). Zero latency, immune to Wi-Fi drops.
2. **Wi-Fi (`wlan0`)**: `ath10k_snoc` connected via WCN3990 modem subsystem (`ginkgo-mpss.service`). IP dynamically assigned (e.g. `10.220.61.184`).

Host helper scripts:
- `ssh-exec.ps1`: Automatically binds `-b 192.168.7.1` when targeting `192.168.7.2`, and transparently routes to `$env:GINKGO_IP` if USB is disconnected.
- `scp-exec.ps1`: Handles secure file transfers across both network paths without interactive password prompts.
