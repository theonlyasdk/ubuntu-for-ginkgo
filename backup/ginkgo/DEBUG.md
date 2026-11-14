# How to capture errors when the phone will not boot

## What can be captured automatically?

| Situation | Capturable? | How |
|-----------|-------------|-----|
| Kernel panic, but the phone **still reaches fastboot** | Partly | `fastboot getvar`; **ramoops** keeps the log, read `pstore` after restoring Android |
| **USB adb works** (kernel came up, init did not) | Yes | `adb shell dmesg` |
| **Completely black screen / reboot loop** | No - cannot be captured remotely | Needs a **UART serial cable**, or restore Android and read `pstore` |
| After restoring LineageOS | Yes | `./scripts/capture-logs.sh` reads `pstore` / `last_kmsg` |

**Conclusion:** without a serial cable the most reliable path is **ramoops + restore
Android and read `pstore`**. The mainline ginkgo DTB already enables ramoops
(`pstore_mem @ 0xffc00000`).

---

## Recommended flow (after a failed flash)

```bash
# 1. Hold Volume-Down + Power to reach fastboot (if it still gets that far)

# 2. Restore the Android boot image (this keeps the pstore memory contents)
./scripts/restore-android.sh

# 3. As soon as the system is up, grab the logs
./scripts/capture-logs.sh

# 4. Send the files from backup/ginkgo/logs/ for analysis
```

---

## Serial debugging (best option, optional)

ginkgo UART: `ttyMSM0, 115200n8`, address `0x4a90000`

- Needs a **USB-TTL serial cable** soldered to the mainboard test points (the
  Redmi Note 8 community has published pinouts).
- Host side:
  ```bash
  sudo apt install picocom
  picocom -b 115200 /dev/ttyUSB0
  ```
- The boot.img cmdline already contains `earlycon=msm_serial_dm,0x4a90000`

With a serial cable the whole run is visible, from the first
`Uncompressing Linux...` line to the panic message.

---

## Debug configuration that is already built in

- **earlycon** + **console=ttyMSM0** (boot.img cmdline)
- **CONFIG_PSTORE_RAM** + **ramoops** (DTS)
- **CONFIG_SERIAL_MSM_CONSOLE**

---

## Extra debugging (optional, before flashing)

Rebuild `boot.img` with a more verbose cmdline:

```bash
CMDLINE="console=ttyMSM0,115200n8 earlycon=msm_serial_dm,0x4a90000 ignore_loglevel loglevel=8 \
  root=/dev/disk/by-partlabel/userdata rootwait rw init=/sbin/init" \
  ./scripts/build-bootimg.sh
```
