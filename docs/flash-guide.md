# Flash Guide: Redmi Note 8 (ginkgo)

This guide provides quick fastboot command reference for flashing or updating mainline Linux on Xiaomi Redmi Note 8 (codename: ginkgo).

For a complete beginner tutorial with step-by-step setup instructions, please see the [Installation Guide](install-guide.md).

---

## Safety Requirements

- Target: Xiaomi Redmi Note 8 only (SM6125).
- Unlocked bootloader is required (`fastboot getvar unlocked` -> `yes`).
- Flashing the rootfs to `userdata` will format all personal files on the device.

---

## 1. Quick Full Installation (Clean Install)

Decompress `rootfs.ext4.zst` using `zstd -d rootfs.ext4.zst`. Then put your phone into fastboot mode (Hold Volume Down + Power) and run:

```bash
# 1. Flash rootfs to userdata
fastboot flash userdata rootfs.ext4

# 2. Flash empty DTBO
fastboot flash dtbo dtbo-empty.img

# 3. Flash mainline kernel
fastboot flash boot boot.img

# 4. Disable verified boot
fastboot flash vbmeta --disable-verification vbmeta.img

# 5. Reboot into Linux
fastboot reboot
```

---

## 2. Kernel Update Only (Preserves Your Data)

If you already have Ubuntu installed and only want to update the mainline kernel:

```bash
fastboot flash dtbo dtbo-empty.img
fastboot flash boot boot.img
fastboot reboot
```

---

## 3. Temporary Test Boot (No Flashing)

If you built or received a new `boot.img` and want to test it in RAM without modifying your phone storage:

```bash
fastboot boot out/boot.img
```
If you encounter any issues, simply reboot the phone by holding the Power button for 10 seconds to restore your previously flashed system.

---

## 4. Default Login Credentials

- User: `ginkgo`
  - Password: `ginkgo`
- Root: `root`
  - Password: `password`
- SSH IP over USB: `192.168.7.2` (Host IP: `192.168.7.1`)
