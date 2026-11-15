# ubuntu-for-ginkgo

Mainline Linux 7.0 + Ubuntu 26.04 LTS (Plasma 6 Wayland) for **Xiaomi Redmi Note 8** (codename **ginkgo**, Qualcomm Snapdragon 665 / **SM6125**).

This project boots a modern mainline Linux 7.0 kernel and an Ubuntu 26.04 arm64 (`resolute`) rootfs directly on device hardware. Designed for the global **Tianma NT36672A** panel SKU with hardware-accelerated graphics, active touch sync, high-speed Wi-Fi, and 2GB LZ4 ZRAM swap.

| Subsystem | Hardware Component | Status | Notes |
|---|---|---|---|
| **Kernel** | Mainline Linux 7.0 (`#142 SMP PREEMPT`) | **Working** | `mitigations=off`, `CONFIG_HZ_1000=y` |
| **Userspace** | Ubuntu 26.04 LTS arm64 (`resolute`) | **Working** | ext4 rootfs on eMMC `userdata` (`mmcblk0p87`) |
| **Desktop** | KDE Plasma 6 on Wayland + SDDM | **Working** | Autologin user `ginkgo`, Xwayland active |
| **GPU 3D** | Adreno 610 (Freedreno Gallium msm) | **Working** | Fluid 60 FPS hardware acceleration |
| **Display** | Tianma NT36672A 1080×2340 60Hz DSI | **Working** | DPU 5.0 video-mode, no FIFO overflows |
| **Touchscreen**| Novatek NT36672A on SPI2 | **Working** | Active multi-touch; `<300ms` SRAM reload via `ginkgo_touch_sync.ko` |
| **Swap & RAM** | 2 GB LZ4 Compressed Swap (`/dev/zram0`) | **Working** | Priority 100, zero readahead latency |
| **RTC Clock** | PM6125 hardware RTC (`/dev/rtc0`) | **Working** | Driven by `rtc-pm8xxx.ko`, retains time across reboots |
| **Wi-Fi** | Qualcomm WCN3990 (`ath10k_snoc`) | **Working** | 5GHz 802.11ac confirmed (292.5 Mbps) |
| **Bluetooth** | Qualcomm WCN3990 (ROM Mode) | **Working** | Bluetooth 5.0, stable BD address, crypto modules loaded |
| **Connectivity**| DWC3 USB Type-C (RNDIS Gadget) | **Working** | SSH at `192.168.7.2`, ICS internet at `192.168.137.50` |
| **Battery & Power** | PMI632 Fuel Gauge (`qgauge@4800`) | **Working with limitations** | Recovery uses the earlier percentage-reporting driver; USB charger monitoring remains [experimental](docs/pmi632-battery-driver.md) |

---

## Interactive Architecture & Roadmap

Explore the full hardware topology, 9 subsystem cards, component readiness tracker, execution steps, and copyable coding agent prompts online:
- 🌐 **[Live System Atlas & Interactive Roadmap (GitHub Pages)](https://theonlyasdk.github.io/ubuntu-for-ginkgo/)**
- 📄 Local File: [docs/ginkgo-roadmap.html](docs/ginkgo-roadmap.html) (double-click to open in any web browser)

---

## Essential Guides & Docs

- **[Installation Guide](docs/install-guide.md)**: Full step-by-step setup guide for host and phone.
- **[Fastboot Flash Cheat Sheet](docs/flash-guide.md)**: Quick commands for flashing kernel, rootfs, and disabling verified boot.
- **[Device Agent Index (AGENTS.md)](AGENTS.md)**: Operational guide covering USB RNDIS networking, SSH access, services, and kernel architecture.
- **[Engineering Audit Chronicle](docs/audit/)**: Complete technical history of display bring-up, Wi-Fi, touch recovery, and performance tuning.

## Panel SKUs (Tianma vs Huaxing)

ginkgo shipped with more than one display. Same DSI connector, different panel IC and init sequence.

| Image | Panel | Status |
|-------|--------|--------|
| `boot.img` (default) | **Tianma NT36672A** 1080×2340 | Supported. Display, fbcon, SPI touch, Plasma desktop. This is the SKU this project targets. |
| `boot-huaxing.img` | **Huaxing / CSOT FT8719** | **China-ROM variant only.** Display lights up (pclk locked to the proven Tianma 183012 kHz); touch is still off. Not a supported desktop image, and a Tianma unit never needs it. |

The Huaxing FT8719 panel ships on units sold with the **China ROM**. Units sold
outside China carry the Tianma NT36672A, which the default `boot.img` drives.

A China-ROM Huaxing phone stays black on the Tianma `boot.img`. Flash
`boot-huaxing.img` instead (prefer `fastboot boot` once before writing the
partition).

Type-C is USB gadget by default so SSH/RNDIS keep working. Keyboard/mouse needs an OTG adapter and, on the phone:

```bash
ginkgo-usb-host.sh
```

SSH drops until you reboot (or switch the role back to `device` and restart `usb-gadget-rndis`).

On stock Android you can see which panel you have:

```bash
dmesg | grep -iE 'tianma|huaxing|ft8719|nt36672a|TP info'
```

If a panel does not light up, open a [GitHub issue](https://github.com/Huabin1010/ginkgo-mainline-linux/issues/new) and attach the **boot log** (from power-on through DRM/panel probe). That is enough; no need for photos of the whole session.

**UART (best if the screen is black).** 1.8 V only. Phone TX **TP0003** → adapter RX, phone RX **TP0012** → adapter TX, plus GND. Start capture **before** power-on. Wiring: [UART guide](docs/audit/ginkgo-usb-ttl-uart.md).

```bash
picocom -b 115200 /dev/ttyUSB0 | tee uart.log
```

**USB SSH (if the kernel reaches userspace).** USB RNDIS, then `root@192.168.7.2` — password `password`. The desktop user `ginkgo` logs in with password `ginkgo`.

```bash
ssh root@192.168.7.2 'dmesg' > dmesg.txt
```

Paste or attach `uart.log` / `dmesg.txt`. These lines matter most:

```text
panel init complete
power mode readback
dsi_err
```

## Quick start

```bash
# 1. Host packages (once, needs sudo)
./scripts/setup-deps.sh

# 2. Fetch kernel sources (once)
./scripts/setup-kernel.sh

# 3. Build kernel + ginkgo DTB
./scripts/build-kernel.sh

# 4. Pack boot.img
./scripts/build-bootimg.sh

# 5. Build Ubuntu rootfs
./scripts/build-rootfs.sh
./scripts/configure-rootfs.sh
./scripts/build-rootfs-image.sh

# 6. Flash (device in fastboot)
./scripts/flash-boot.sh
# First install only — this wipes userdata:
# fastboot flash userdata out/rootfs.ext4
```

Kernel sources (`linux/`) and build outputs (`out/`) are not in git. Clone and compile them with the scripts above.

## Flash order

Flash rootfs first, then boot, then disable vbmeta verification.

```bash
export PATH="$HOME/.local/bin:$PATH"

# 1. fastboot (adb reboot bootloader, or the key combo)

# 2. Ubuntu rootfs → userdata (wipes that partition)
fastboot flash userdata out/rootfs.ext4

# 3. Mainline kernel
fastboot flash boot out/boot.img

# 4. Disable verified boot
fastboot flash vbmeta --disable-verification vbmeta.img

# 5. Reboot
fastboot reboot
```

Login: serial `ttyMSM0` or SSH over USB RNDIS (`root@192.168.7.2`). Passwords are intentionally trivial: `root` / `password`, desktop user `ginkgo` / `ginkgo`. The image reads the root password from the gitignored file `rootfs-overlay/etc/ginkgo-root-password`, or `$GINKGO_ROOT_PASSWORD`.

Serial console: `ttyMSM0,115200n8` @ `0x4a90000` (1.8 V only). Wiring: [UART guide](docs/audit/ginkgo-usb-ttl-uart.md).

## Layout

```
config/           Kernel config fragment
scripts/          Build, flash, UART, and host USB helpers
docs/             English technical notes
firmware/ginkgo/  Device-extracted firmware
reference/        Downstream + mainline DTS / driver excerpts
rootfs-overlay/   Files copied into the Ubuntu image
backup/ginkgo/    Partition map and restore notes (images are gitignored)
host/             Host NetworkManager snippet for USB RNDIS
```

## Documentation

| Topic | Document |
|-------|----------|
| Full Installation Guide | [install guide](docs/install-guide.md) |
| Flash Command Cheat Sheet | [flash guide](docs/flash-guide.md) |
| Doc Index | [docs/README.md](docs/README.md) |
| Engineering Audits | [docs/audit/](docs/audit/) |
| Full Chronicle | [bring-up chronicle](docs/audit/ginkgo-mainline-bringup-chronicle.md) |
| Porting Handbook | [porting guide](docs/audit/mainline-ginkgo-porting-guide.md) |
| UART Wiring | [UART guide](docs/audit/ginkgo-usb-ttl-uart.md) |
| Wi-Fi Bring-up | [2026-08-18](docs/audit/ginkgo-wifi-complete-2026-08-18.md) |
| Display | [2026-08-17](docs/audit/ginkgo-display-complete-2026-08-17.md) |
| Touch | [2026-08-17](docs/audit/ginkgo-touch-complete-2026-08-17.md) |

## Environment

See `scripts/env.sh`:

| Variable | Default | Meaning |
|----------|---------|---------|
| `KERNEL_TAG` | v7.0 | Kernel version |
| `KBUILD_OUTPUT` | `out/kernel` | Build tree |
| `JOBS` | `nproc` | Parallel jobs |
| `GINKGO_ROOT_PASSWORD` | *(unset)* | Root password for the image; otherwise read from the overlay file |

## License

Build scripts and original documentation in this repository are [GPL-2.0-only](LICENSE), same as the Linux kernel. Downstream excerpts under `reference/` keep their upstream licenses. Device firmware blobs are proprietary; they are provided only for running Linux on the device they were extracted from.
