# Audio isolation recovery, November 15, 2026

The owner reports whole-system freezes when opening the sound applet, opening
the battery applet, unplugging USB, and while USB remains connected. Restoring
the earlier battery module restored percentage reporting but did not stop the
freezes. Audio/ADSP is being isolated; its responsibility is not yet proven.

Recovery build: `scripts/build-audio-recovery.py` uses
`out/boot-before-qg-monitor.img` as its base and the QG module compiled from
repository revision `a68bf9f10f141fee48d1a08da950c73aabe45e3d`.
Module SHA256: `0e9561636df5058bf734d37536871c5804d24d1aa446a002468b9cc0be8774b7`.
The ramdisk audio service is replaced with a no-op, and the DTB ADSP node at
`/soc@0/remoteproc@ab00000` is disabled. Other ramdisk entries, kernel and boot
arguments are preserved. The artifact is `out/boot-audio-recovery.img`, SHA256
`ead35527cb98adec475f093da81a6c442ada1d20e190ed3da91c55343e0cfbac`.

Base partition backup SHA256:
`c8ffdbe42656a778d5030279a2f4e462936069a9e32e67c1150df42400f4bc47`.
The #142 kernel is retained; vermagic is
`7.0.0-00001-g62f9dac57de4-dirty SMP preempt mod_unload aarch64`.

The repacker verifies all 229 archive entries and unpacked image components.
Boot, display, touch, applets and unplug stability require post-flash testing.
Experimental audio source is retained; no audio functionality is expected in
this recovery image. Existing rootfs audio configuration is not removed.
