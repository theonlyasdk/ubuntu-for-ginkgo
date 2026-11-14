# Known issues / backlog for ginkgo mainline

Everything that is still broken, unfinished or unverified on the Redmi Note 8
(ginkgo) mainline build, with the evidence behind it and the shortest path to a
fix. Status: **verified** (reproduced in this tree), **carried** (seen in an
earlier session, not re-checked recently), **expected** (known by inspection).

Read this before starting work: several items look unrelated but share one
root cause (see "Themes" at the bottom).

---

## A. Bluetooth

| # | Issue | Evidence | Fix path | Status |
|---|-------|----------|----------|--------|
| A1 | **BR/EDR connect/pair always fails.** Page timeout, `status 0x04`. | `btmgmt --index 0 pair -c NoInputNoOutput -t bredr 08:F9:7E:5B:4D:64` → `Connect Failed (status 0x04, Page Timeout)`; btmon shows `Create Connection` → `Connect Complete: Page Timeout (0x04)`. | Needs a known-good peer: power on the Rockerz 550 / OnePlus Bullets, **turn the PC's Bluetooth off first** (both are paired to Windows and will auto-connect to it), then pair from the phone with a `btmon` capture running. | verified |
| A2 | Phone's BR/EDR **inquiry finds nothing** — it never discovers a single classic device, even though Windows was powered on and discoverable. | `btmgmt find` for 30 s → zero BR/EDR results, only LE beacons. The phone's LE RX works (hears `20:A9:DC:03:8D:AC` at −56/−69 dBm), so this is specific to classic BT. | Same capture session as A1. If the earbuds are found, the phone's inquiry path works and the problem is link setup; if not, the phone's classic RF is dead. | verified |
| A3 | The controller runs **ROM firmware with no NVM/calibration** and no factory BD address. | dmesg: `QCA skipping rampatch download, using ROM firmware` + `QCA Failed to request file: qca/crbtfw12.tlv (-11)`. `qca_download_firmware()` returns `-EAGAIN` for both patch and NVM with `qca_skip_fw=1`. | Full firmware download times out on the **first TLV segment** (`command 0xfc00 tx timeout`). Retry after a true power cycle; try `crbtfw21.tlv`; or accept ROM mode. | carried |
| A4 | **NVM-only download never attempted.** `qca_skip_fw=0` + `qca_skip_patch=1` would load calibration and the factory BD address while skipping the TLV. | `qca_skip_patch=1` with `qca_skip_fw=0` is untested; it can wedge the chip. | **Needs a reboot to recover if it wedges — ask first.** This is the most likely real fix for A1/A2. | expected |
| A5 | The BD address is **fake and injected at boot** (`86:D2:39:0F:1E:EE`). It is locally administered and loses its factory identity on every power cycle. | `/usr/local/sbin/bt-set-addr.sh`, wired in via `bluetooth.service.d/bdaddr.conf`; the ROM has no factory address to keep. | Once A3/A4 work, stop overriding the address and let the chip use its own. | verified |
| A6 | The old `bt-set-addr.sh` used to hold stdin for 10 s per `btmgmt` call, which starved the kernel's `power_on` work and hid hci0 from mgmt. | Reproduced earlier: `btmgmt info` showed no index for minutes. | **Fixed** — the script now uses a fast pipe. Keep the fast pattern; do not reintroduce `sleep`-fed pipes. | fixed |

## B. Battery and power

| # | Issue | Evidence | Fix path | Status |
|---|-------|----------|----------|--------|
| B1 | **Battery readings are frozen.** `current_now` sat at exactly 37231 µA for 60 s, `capacity` is always 100 %, `voltage_now` barely moves. | `/sys/class/power_supply/qcom-battery/*` sampled every 10 s over 60 s — all identical. | The minimal PMI632 QG driver reads registers that nothing refreshes: the full CAF `qpnp-qg` algorithm (which programs the QG ADC and the SOC state machine) is not in mainline. Either configure the QG hardware from the driver, or read the battery voltage from the PMIC **VADC** (`pmi632_vadc`, upstream `qcom-spmi-adc5`) and drop the fake current. **Needs a kernel change → rebuild + flash.** | verified |
| B2 | **No charger / USB power supply node at all.** The phone cannot know it is plugged in; status is permanently "Not charging" while tethered. | `/sys/class/power_supply/` contains only `qcom-battery`. The upstream `pmi632_charger` driver does not exist in mainline. | Add a `POWER_SUPPLY_TYPE_USB`/`USB_DCP` node whose `online` follows VBUS presence (the `otg-vbus` regulator state or the USB role switch) and whose status drives the battery status. Needs a kernel change. | verified |
| B3 | **Battery temperature is not exposed** at all. | `temp` / `temperature` absent under `/sys/class/power_supply/qcom-battery/`. | The QG has a thermistor input; needs the CAF port or a VADC channel. | verified |
| B4 | `ginkgo-performance.service` pinned **all 8 cores to `performance`** and the Adreno 610 to `max_freq` for the whole session. | `scaling_governor=performance` on policies 0-3 (1.80 GHz) and 4-7 (2.02 GHz); `cpu-thermal` 40.7 °C at idle. | **Done in the repo**: `ginkgo-power-mode.sh` (`performance` / `balanced` / `eco`) + `ginkgo-power-mode.service`, default `balanced`; `ginkgo-performance.service` is no longer enabled by the image scripts. Still needs to be applied to the live device. | verified (repo done, device pending) |
| B5 | **No zram, no swap** on a 3.5 GB device. | `/proc/swaps` empty, `/sys/block/zram0` absent. The repo ships `zram-setup.service` + `ginkgo-zram.sh` (2 GB LZ4) but the running image does not have it active. | `systemctl enable --now zram-setup.service`. Check whether the unit is present on the device at all. | verified |
| B6 | `fwupd` is **running** although the docs say it is masked. | Process list shows `fwupd` (1.6 % RSS). `configure-rootfs.sh` masks `pd-mapper` and `smartmontools`, not `fwupd`. | Mask `fwupd.service` + `fwupd-refresh.timer`. | verified |
| B7 | The display **never sleeps** (requested deliberately). The panel and the compositor therefore run at full tilt forever. | `~/.config/powerdevilrc`: `TurnOffDisplayWhenIdle=false`, `DimDisplayWhenIdle=false`, all timeouts `0`; verified with an 11.5 min idle test — panel never blanked. | Keep it, but add a toggle so "always on" and "blank after N minutes" are one command apart. | verified |
| B8 | The battery is a **4000 mAh** cell with three different batch profiles; the driver ignores all of it. | `reference/downstream/dts/xiaomi/ginkgo/battery/qg-batterydata-{atl,light,unknow}-4000mah.dtsi`, `ginkgo-trinket-battery.dtsi`. | Use the QG battery data (or at least a fixed 4000 mAh `CHARGE_FULL`) so `capacity` can be computed from charge instead of voltage. Needs a kernel change. | verified |
| B9 | Downstream charger limits are unknown to mainline: FCC/USB ICL 3 A, FV 4.4 V, JEITA, thermal-mitigation table, auto-recharge at 99 %. | `ginkgo-trinket-battery.dtsi` (`pmi632_charger` block). | Only relevant once B2 exists. | carried |

## C. Sensors and positioning

| # | Issue | Evidence | Fix path | Status |
|---|-------|----------|----------|--------|
| C1 | **No accelerometer / gyro.** Nothing appears under `/sys/bus/iio/devices/`. | Upstream v7.0 has **no** `qcom,sdm845-accel` and **no** BMI160 driver (`drivers/iio/accel/Makefile` lists bma*/bmc150/bmi088/kionix only). | Identify the chip from the downstream DTS, then add a small **out-of-tree IIO driver** — no kernel rebuild needed, it matches the existing `qcom-pmi632-qg.ko` pattern. | verified (gap) |
| C2 | **No compass / magnetometer.** | Upstream v7.0 `drivers/iio/magnetometer/` has **no** AK09911/AK09918. | Same as C1: small out-of-tree IIO driver for the AKM part, once the chip is known. | verified (gap) |
| C3 | **No GPS.** | Upstream v7.0 `drivers/gnss/` has only serial/MTK/Sirf/u-blox/USB — **no Qualcomm WCSS/SSR driver**. | Would need the SSR/WSs stack (`qcom_q6v5_wcss` remoteproc + a GNSS driver) **and** the SSR GNSS modem firmware, which the repo does not have. Largest item in this file. | verified (gap) |
| C4 | Which sensor chips this unit actually carries is still unknown — the downstream sensor DTS is not in the repo's `reference/` subset. | `reference/downstream/dts/` has no sensor dtsi. | Read `/root/ginkgo/linux/arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dts` (and `trinket-sensor.dtsi`) on the device. | expected |
| C5 | Proximity / light sensors also missing (same upstream gaps). | — | Same approach as C1/C2 once the chip list is known. | expected |
| C6 | No sensor **interrupt** wiring, so even a working driver would poll. | — | Depends on C4; the downstream dtsi shows the IRQ mapping. | expected |

## D. Media, radios, camera

| # | Issue | Evidence | Fix path | Status |
|---|-------|----------|----------|--------|
| D1 | **No camera.** No mainline camera driver for SM6125; the reference DTS has the sensor nodes (`trinket-camera-sensor-{idp,qrd}.dtsi`, 8 sensors). | `reference/downstream/dts/qcom/trinket-camera*.dtsi`. | Out of reach: needs a Qualcomm ISP/camera stack port. | carried |
| D2 | **Fingerprint** not supported (Goodix), though the downstream DTS exists. | `reference/downstream/dts/xiaomi/ginkgo/ginkgo-trinket-fingerprint.dtsi`. | Upstream has `drivers/input/fingerprint` but no Goodix driver matching this part. | carried |
| D3 | **NFC** not supported. | `ginkgo-trinket-nfc.dtsi`. | No upstream driver for the NXP PN532/ST chip used. | carried |
| D4 | **IR blaster** not supported. | `ginkgo-trinket-ir.dtsi`. | Possibly a GPIO/pwm LED that needs no kernel work — just a userspace driver. | carried |
| D5 | **Modem / calls**: the `qcom_q6v5_pas` crash loop was seen earlier; at the last check there were **0** fatals in dmesg. | Earlier: `qcom_q6v5_pas ... fatal error without message`; now `dmesg \| grep -c 'qcom_q6v5_pas.*fatal'` → 0. | Keep an eye on it; ModemManager is still running and may be the trigger. | carried |
| D6 | Audio: PipeWire/WirePlumber are present, but the codec/headset path has never been verified end to end. | `trinket-audio.dtsi`, `ginkgo-trinket-audio.dtsi` in the reference DTS. | Test speaker, headset jack, microphone over SSH with `pw-cli` / `pw-play`. | expected |

## E. System services and stability

| # | Issue | Evidence | Fix path | Status |
|---|-------|----------|----------|--------|
| E1 | **Touch firmware is volatile.** The NT36672A has no on-chip flash; panel power rails drop during blanking or suspend and the touch SRAM is lost. | `ginkgo_touch_sync.ko` + `ginkgo-touch-sync.service` reload `novatek_ts_tianma_fw.bin` into SRAM on resume and on unblank. | A permanent fix needs the panel kept powered in suspend (DT) so the firmware survives — then the workaround can go. | verified |
| E2 | `display-unblank.service` fights the compositor (it blanks/unblanks the panel independently of the desktop). | `display-unblank.sh` takes DRM master on `/dev/dri/card0`, conflicting with KWin Wayland and SDDM. | **Fixed**: Added `Conflicts=sddm.service ...`, `ConditionPathExists=!/etc/sddm.conf.d/10-ginkgo.conf`, active compositor detection in `display-unblank.sh`, and disabled in `multi-user.target.wants`. | fixed |
| E3 | The **charger-mode string** in the kernel image is patched (`androidboot.mode=nocharg`) so touch registers when booted with a cable. | Documented in AGENTS.md §1.4. | Keep — it is a deliberate image patch, not a kernel fix. | verified |
| E4 | **Suspend/resume has never been tested** end to end (only the touch workaround implies it). | No `systemctl suspend` test on record. | Test suspend → resume → touch → display → network on battery power (`rtcwake -m mem -s 10`). | expected |
| E5 | **Clock resets on reboot**; `ginkgo-rtc-sync.service` + timer exist to re-sync from the PMIC RTC. | AGENTS.md §1.1; the phone's clock was wrong after reboots until the service ran. | Works, but apt on the phone needs the clock right first — keep the ritual documented. | verified |
| E6 | 23 leftover **GNOME library packages** are still installed after the GNOME purge. | `gnome-settings-daemon` in `$GUARD` caused `apt autoremove --purge` to abort. | **Fixed**: Updated `ginkgo-debloat.sh` to explicitly mark audio/desktop stack manual, purge `gnome-settings-daemon` and `mutter-common`, and run safe `autoremove --purge`. | fixed |
| E7 | The **boot HUD is in Chinese** while the desktop is English. | `initramfs/ginkgo-status.c` defaulted to `lang_en = 0` without configuration in initramfs. | **Fixed**: Set `lang_en = 1` default in `initramfs/ginkgo-status.c`, added `rootfs-overlay/var/lib/ginkgo/hud.conf` (`lang=en`), and rebuilt initramfs and `boot.img`. | fixed |
| E8 | `ddcutil` in powerdevil cannot open `/dev/i2c-0` (EACCES). | `Error EACCES(-13): Permission denied opening /dev/i2c-0` in the powerdevil log. | **Fixed**: Added `POWERDEVIL_NO_DDCUTIL=1` to `rootfs-overlay/etc/environment.d/20-powerdevil.conf` to disable DDC/CI monitor probing on internal phone I2C bus. | fixed |
| E9 | The phone's **Wi-Fi regulatory domain / stable MAC** setup service is not enabled. | AGENTS.md §7: `ginkgo-wifi-setup.service` was disabled and hardcoded to `CN`. | **Fixed**: Changed regulatory domain to `IN` (India) in `ginkgo-wifi-setup.sh`, polled for `wlan0`, enabled service in `multi-user.target.wants`, and documented safe MAC derivation without link bouncing. | fixed |

## F. Repository and tooling

| # | Issue | Evidence | Fix path | Status |
|---|-------|----------|----------|--------|
| F1 | **Chinese documentation and links to it** (the translated README set, the `docs/` translation tree, and translated READMEs under `firmware/`, `reference/` and `backup/`). | — | **Fixed**: all deleted, every language switcher and link removed, `backup/ginkgo/DEBUG.md` translated instead of deleted. | fixed |
| F2 | The repo still pointed at the **China mirror** (Tsinghua TUNA) in the overlay apt sources, the debootstrap default and AGENTS.md — and would have shipped into new images. | `rootfs-overlay/etc/apt/sources.list.d/ubuntu.sources`, `docker.sources`, `scripts/build-rootfs.sh`, AGENTS.md §5. | **Fixed**: `ports.ubuntu.com` + `download.docker.com`; historical audit records keep the story with a dated note. | fixed |
| F3 | The Huaxing panel path was not marked as the **China-market variant**. | — | **Fixed**: driver header, DTS header + `model`, both patch copies, Kconfig help, `config/ginkgo.fragment`, build script, release notes, README, install guide. | fixed |
| F4 | **Stale hunk counts** in `overlays/linux/0002-pmi632-qg-panel-sleep.patch` — the DTS hunk declared `+18` but carried 26 lines, which makes GNU `patch` abort the file. | Pre-existing, not caused by the docs cleanup; all 30 hunks now match their bodies and `git apply --numstat` parses all three patches. | **Fixed**. Worth a CI check. | fixed |
| F5 | **39 dangling relative links** left by the `docs → docs/audit` move. | Link check over all markdown. | **Fixed**: 16 rewritten, 1 dead target turned into plain text, the rest verified. | fixed |
| F6 | `rootfs-overlay/etc/systemd/user/` **cannot be staged on Windows** — the filesystem rejects the symlinks inside it (`error: open(...pipewire-pulse.service): Function not implemented`). | `git add -A` exits 128 there. | Commit from a Linux checkout, or `git update-index --skip-worktree` on Windows. | verified (open) |
| F7 | **Repo ↔ device drift**: the repo and the phone have diverged (services, scripts, `/etc/environment.d`). | AGENTS.md §7 has a diff recipe. | Run the drift check after every hands-on session and commit what is missing. | carried |
| F8 | The staging tree mixes this cleanup with the other agent's in-flight BT/OTG work. | `git status` shows 137 changed files in one index. | Two commits: docs/mirror/Huaxing cleanup, then the BT+OTG work. | open (user asked to leave it staged) |

## G. Host-side workflow

| # | Issue | Evidence | Fix path | Status |
|---|-------|----------|----------|--------|
| G1 | The phone's **only internet path** is the PC's HTTP proxy on `0.0.0.0:3128`, which dies whenever the PC restarts or sleeps. | The proxy is started by hand; it was cancelled when the PC restarted during this session. | Make it a scheduled task / service that starts with Windows, and re-check the phone's `192.168.137.50` route afterwards. | verified |
| G2 | After **every phone reboot** the Windows side must re-point the RNDIS adapter (192.168.7.1) or DHCP fails and the address is flushed. | AGENTS.md §2; the adapter disappeared entirely during this session's reboot. | A small `usb-connect.ps1` equivalent of `scripts/usb-connect.sh` for Windows. | verified |
| G3 | The Windows **"Add device" dialog and WinRT Bluetooth APIs are unreliable** on this PC — they found `B350E` but never the phone, and `BluetoothLEAdvertisementPublisher` throws "Value does not fall within the expected range". | Screenshots and WinRT error during this session. | Do not use the PC as the Bluetooth test peer; use real hardware. | verified |
| G4 | `btmgmt` hangs ~3 s when its stdin is `/dev/null`; use `echo \| btmgmt`. | Every script that stalled. | Keep the fast pattern in all scripts. | verified |

---

## Themes

1. **The biggest cluster of failures is "hardware present, driver missing".** Bluetooth calibration, the charger, the fuel gauge, the sensors, the camera, NFC, fingerprint — all of them are Qualcomm/Qualcomm-partner stacks that do not exist in mainline. The project's out-of-tree `.ko` pattern (built against vermagic `7.0.0-00001-g62f9dac57de4-dirty`) is the only route that avoids a kernel rebuild, and it has already worked for `qcom-pmi632-qg`, `rtc-pm8xxx`, `qcom_usb_vbus_regulator` and `userspace_consumer`.
2. **Anything that needs the full CAF `qpnp-qg` algorithm (B1, B3, B8) needs a kernel rebuild and therefore a flash.** Everything else can ship as modules.
3. **Two of the three "no hardware" complaints were really "no driver" complaints** (sensors), and one was really "no data" (battery).
4. **The remaining Bluetooth failure is the only issue that blocks a core phone function** and it is still undiagnosed — it needs a real peer device, not the PC.
