# Plasma Keyboard fallback appearance: confirmed fix

Date: November 15, 2026. Device: ginkgo, Ubuntu 26.04, Plasma Wayland.

## Symptom and evidence

Tapping a KDE text field displayed a large Qt-style keyboard instead of the
expected Plasma keyboard. The owner supplied a photograph and confirmed that
the appearance was corrected after the final changes below.

Plasma Keyboard was already installed (`plasma-keyboard 6.6.4-0ubuntu1`), running,
and selected in `~/.config/kwinrc`:

```ini
[Wayland]
InputMethod[$e]=/usr/share/applications/org.kde.plasma.keyboard.desktop
VirtualKeyboardEnabled=true
```

The Breeze QML style plugin was also installed and loaded in plasma-keyboard.
This was not a missing keyboard package or missing Breeze theme.

The legacy `/etc/environment.d/99-ginkgo-keyboard.conf` globally forced both
`QT_IM_MODULE=qtvirtualkeyboard` and `QT_IM_MODULES=qtvirtualkeyboard`. These
values were present in the running KWin and plasmashell environments.

## Change that worked

Remove both forced engine assignments from their original file. The repository
version now contains only explanatory comments and:

```ini
QT_VIRTUALKEYBOARD_LOCALE=en_US
```

Then restart the **entire** Plasma user session, not just its display manager
or compositor. These commands close the user's desktop applications; run them
over root SSH when a session restart is intended:

```sh
systemctl stop sddm
loginctl terminate-user ginkgo
systemctl start sddm
```

Afterward, `/proc/<kwin-pid>/environ` and `/proc/<plasmashell-pid>/environ`
no longer contained the forced Qt engine values, and a new plasma-keyboard
process was running. The owner confirmed that the unwanted keyboard appearance
was gone. Additional typing/layout coverage was not explicitly reported.

Source checkpoint: `2346394` (`fix: remove forced Qt keyboard engine at its source`).
Original live settings were backed up as `out/keyboard-environment-before.conf`
and `out/kwinrc-before-keyboard-fix`.

## Earlier attempts and persistence

Adding empty assignments in `zz-ginkgo-plasma-keyboard.conf`, clearing the user
manager environment, restarting SDDM, and restarting KWin individually did not
resolve the owner's visible symptom. Some existing processes retained the old
environment. A startup cleanup script was also installed at
`/etc/xdg/plasma-workspace/env/ginkgo-input-method.sh`; do not mistake that
supporting change for the independently confirmed fix.

The corrected original file is installed live and saved in `rootfs-overlay/`.
Older boot ramdisks reapply their embedded overlay on every boot, so the old
`boot-audio-recovery.img` can restore the bad file.

## Persistent deployment verified

The corrected config was embedded in `out/boot-audio-keyboard.img`, built using
checkpoint `5cc0682` and the existing audio-recovery image as its base. Verification
of all 229 ramdisk entries showed that only
`overlay/etc/environment.d/99-ginkgo-keyboard.conf` changed. The kernel, disabled
ADSP/audio, prior battery module, DTB and boot arguments were preserved.

Image SHA256:
`e553d982e97ee428a18a62a70281b414e2279eab78c466bf63183ce067afa0f4`.
Rollback image retained: `out/boot-audio-recovery.img`, SHA256
`ead35527cb98adec475f093da81a6c442ada1d20e190ed3da91c55343e0cfbac`.

`fastboot flash boot out/boot-audio-keyboard.img` and `fastboot reboot` succeeded.
The phone booted normally without a temporary `fastboot boot` command. Post-boot
SSH verified the corrected config, a running plasma-keyboard process, no forced
Qt input-engine variables in KWin or plasmashell, and ADSP still disabled.
Configuration persistence across this reboot is verified; the owner has not yet
repeated the visual typing check on this particular boot.
