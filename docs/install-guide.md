# Redmi Note 8 (ginkgo) Mainline Linux Installation Guide

This guide walks you through installing mainline Linux with Ubuntu 26.04 and KDE Plasma on your Xiaomi Redmi Note 8 (codename: ginkgo).

## Requirements

Before starting, make sure you have:
1. A Xiaomi Redmi Note 8 (ginkgo, Snapdragon 6125). Do not flash this on Note 8 Pro (begonia) or Note 8T (willow).
2. An unlocked bootloader.
3. A USB-C to USB-A cable connected to your computer.
4. Fastboot and ADB installed on your computer:
   - On Windows: Download the Android SDK Platform-Tools and extract them.
   - On Linux (Ubuntu/Debian): `sudo apt install android-sdk-platform-tools zstd`
   - On macOS: `brew install android-platform-tools zstd`
5. At least 50% battery on your phone.

> [!WARNING]
> This process will completely wipe your phone (the userdata partition). Backup any personal data, photos, or documents before proceeding.

---

## 1. Files You Need

Download the release files from the GitHub Releases page:
- `boot.img`: The mainline Linux kernel and device tree for the standard Tianma display. (If your device is a China-ROM unit with the Huaxing panel, use `boot-huaxing.img`.)
- `dtbo-empty.img`: Clears the Android DTBO partition so the bootloader uses the mainline device tree.
- `vbmeta.img`: Stock or empty vbmeta with verification disabled.
- `rootfs.ext4.zst`: The Ubuntu 26.04 root filesystem with KDE Plasma desktop.

### Decompress the root filesystem
If `rootfs.ext4` is compressed as `.zst`, decompress it on your computer:
- On Linux/macOS:
  ```bash
  zstd -d rootfs.ext4.zst
  ```
- On Windows: Use 7-Zip (with Zstandard plugin) or run zstd in PowerShell:
  ```powershell
  zstd -d rootfs.ext4.zst
  ```
You will get the uncompressed `rootfs.ext4` file (around 2 to 4 GB).

---

## 2. Boot Your Phone into Fastboot Mode

1. Turn off your phone completely.
2. Hold the **Volume Down** button and the **Power** button together until the FASTBOOT screen appears.
3. Connect your phone to your computer with the USB cable.
4. On your computer, open a terminal (or Command Prompt) and verify the connection:
   ```bash
   fastboot devices
   ```
   You should see your device serial number followed by `fastboot`.

5. Verify that your device is unlocked:
   ```bash
   fastboot getvar unlocked
   ```
   It must output: `unlocked: yes`.

6. Verify that the product is ginkgo:
   ```bash
   fastboot getvar product
   ```
   It must output: `product: ginkgo`. If it outputs anything else, stop immediately.

---

## 3. Flash the Images

Run the following commands in your terminal one by one:

### Step 1: Flash the root filesystem to userdata
This installs Ubuntu onto the internal storage.
```bash
fastboot flash userdata rootfs.ext4
```
*Note: This command takes a minute or two because it writes the full root filesystem.*

### Step 2: Flash the empty DTBO
This prevents the bootloader from applying Android overlays.
```bash
fastboot flash dtbo dtbo-empty.img
```

### Step 3: Flash the mainline kernel
```bash
fastboot flash boot boot.img
```
*(If your device is a China-ROM unit with the Huaxing FT8719 panel, flash `boot-huaxing.img` instead. Units sold outside China use the Tianma panel and need the normal `boot.img`.)*

### Step 4: Disable verified boot
```bash
fastboot flash vbmeta --disable-verification vbmeta.img
```

### Step 5: Reboot into Linux
```bash
fastboot reboot
```

---

## 4. First Boot and Login

The phone will restart and boot mainline Linux:
1. The screen will display the boot animation and systemd startup messages.
2. After a few seconds, the KDE Plasma desktop (or SDDM login screen) will appear.
3. Touch is enabled out of the box. You can tap, swipe, and use the on-screen keyboard.

### Default Passwords
- **Desktop User**: `ginkgo`
  - Password: `ginkgo`
- **Root Administrator**: `root`
  - Password: `password`

---

## 5. Connecting to Wi-Fi

You have two easy ways to connect to Wi-Fi:

### Option A: From the Desktop UI
1. Tap the Wi-Fi icon in the system tray on the panel.
2. Select your Wi-Fi network (2.4 GHz or 5 GHz).
3. Enter your Wi-Fi password and tap Connect.

### Option B: From the Terminal
Open the terminal app on the phone or use SSH and run:
```bash
nmcli dev wifi connect "YourNetworkName" password "YourPassword"
```

Once connected, your phone has full internet access. The system clock automatically syncs using network time (systemd-timesyncd).

---

## 6. Accessing the Phone from Your PC (SSH & Debugging)

Whenever the phone is connected to your PC with the USB cable, it creates a virtual network interface (USB RNDIS).

- The phone IP is: `192.168.7.2`
- The host PC address is: `192.168.7.1`

You can SSH into the phone from your PC terminal:
```bash
ssh ginkgo@192.168.7.2
```
or as root:
```bash
ssh root@192.168.7.2
```
Enter `password` when prompted.

---

## 7. Using USB OTG (Mouse, Keyboard, Flash Drives)

Your phone supports USB Host mode (OTG) to connect standard USB accessories like a mouse, keyboard, or USB hub.

### To switch to USB Host (OTG) mode:
Run this command in the terminal on the phone:
```bash
sudo ginkgo-usb-host.sh
```
This enables 5V power on the USB-C port and switches the port to host mode. You can now plug in your USB-C dongle or OTG adapter. Any connected mouse or keyboard will light up and work immediately.

### To switch back to PC connection (RNDIS & SSH):
When you want to reconnect the phone to your PC for debugging:
```bash
sudo ginkgo-usb-gadget.sh
```
This safely turns off 5V power and returns the USB port to gadget mode.

---

## 8. Battery and Power Management

- The battery level and charging state are fully supported by the onboard PMI632 fuel gauge driver.
- You can check battery status in the desktop tray, or by running:
  ```bash
  cat /sys/class/power_supply/qcom-battery/uevent
  ```

---

## 9. Updating the Kernel in the Future

If you want to update to a newer mainline kernel in the future, you do not need to wipe your data again. Just reboot into fastboot and flash the updated boot image:
```bash
fastboot flash dtbo dtbo-empty.img
fastboot flash boot boot.img
fastboot reboot
```
Your installed apps, settings, and personal files on the userdata partition will remain completely untouched.

---

## 10. Performance, Boot Speed, and Security Notice

> [!WARNING]
> **IMPORTANT SECURITY NOTICE: CPU SPECTRE AND MELTDOWN MITIGATIONS ARE DISABLED.**
> 
> **THIS SYSTEM RUNS WITH THE KERNEL COMMAND LINE `mitigations=off`.**
> **ALL HARDWARE CPU MITIGATIONS FOR SPECTRE V1, SPECTRE V2, AND SPECULATIVE STORE BYPASS ARE DELIBERATELY TURNED OFF TO MAXIMIZE SYSTEM RESPONSIVENESS AND APPLICATION SPEED.**
> 
> **THIS IS APPROPRIATE FOR THIS DEVICE BECAUSE IT IS AN EXPERIMENTAL SINGLE-USER LINUX WORKSTATION CONNECTED DIRECTLY OVER A LOCAL USB CABLE RATHER THAN A MULTI-USER CLOUD SERVER. HOWEVER, BE AWARE THAT UNTRUSTED CODE RUNNING LOCALLY COULD THEORETICALLY EXPLOIT SPECULATIVE CPU EXECUTION VULNERABILITIES.**

### Boot Time and Performance Tuning
- The kernel uses `quiet loglevel=4` during boot to avoid stalling on the slow 115200 baud serial console.
- Userspace starts up in approximately 11 seconds, and the KDE Plasma graphical desktop is ready in about 7 seconds.
- CPU scaling governor is set to `performance` early during startup, locking all eight Snapdragon 6125 cores to their maximum clock frequencies (1.80 GHz on efficiency cores, 2.02 GHz on performance cores).
- Unnecessary background daemons that cause crash loops or excessive disk activity on mobile eMMC storage (such as `fwupd`, `apport`, `smartmontools`, and `maliit-server`) are permanently masked.

