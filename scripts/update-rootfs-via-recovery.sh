#!/usr/bin/env bash
# Push rootfs-overlay into running userdata via recovery adb (incremental update).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OVERLAY="$ROOT/rootfs-overlay"
MNT=/tmp/ginkgo-rootfs-mnt
TARBALL=/tmp/ginkgo-rootfs-overlay.tar.gz

adb devices | grep -q recovery || { echo "error: need recovery adb" >&2; exit 1; }
[[ -d "$OVERLAY" ]] || { echo "missing $OVERLAY" >&2; exit 1; }

echo "==> Pack overlay"
tar -C "$OVERLAY" -czf "$TARBALL" .

echo "==> Mount userdata"
adb shell "mkdir -p $MNT && mount -t ext4 /dev/block/mmcblk0p87 $MNT"

echo "==> Extract overlay"
adb push "$TARBALL" /tmp/ginkgo-rootfs-overlay.tar.gz
adb shell "tar -xzf /tmp/ginkgo-rootfs-overlay.tar.gz -C $MNT && \
	chmod 755 $MNT/usr/local/sbin/usb-gadget-rndis.sh $MNT/usr/local/sbin/mount-persist.sh $MNT/usr/local/sbin/ensure-root-password.sh \
		$MNT/usr/local/sbin/ginkgo-debloat.sh $MNT/usr/local/sbin/ginkgo-ics-inet.sh $MNT/usr/local/sbin/bt-set-addr.sh $MNT/usr/local/bin/ginkgo-full-performance.sh \
		$MNT/usr/local/sbin/ginkgo-power-mode.sh \
		$MNT/usr/local/sbin/ginkgo-usb-host.sh $MNT/usr/local/sbin/ginkgo-usb-gadget.sh $MNT/usr/local/sbin/ginkgo-rtc-sync.sh \
		$MNT/usr/local/sbin/ginkgo-zram.sh && \
	chmod 644 $MNT/lib/modules/ginkgo-extra/*.ko 2>/dev/null || true && \
	chmod 755 $MNT/etc/NetworkManager/dispatcher.d/99-ginkgo-rtc-sync 2>/dev/null || true && \
	chmod 600 $MNT/etc/ginkgo-root-password && \
	rm /tmp/ginkgo-rootfs-overlay.tar.gz"

echo "==> Enable services + fix fstab"
adb shell "
	mkdir -p $MNT/etc/systemd/system/{sysinit.target.wants,basic.target.wants,multi-user.target.wants,timers.target.wants}
	ln -sf ../ginkgo-otg.service $MNT/etc/systemd/system/multi-user.target.wants/ginkgo-otg.service
	ln -sf ../ginkgo-rtc.service $MNT/etc/systemd/system/sysinit.target.wants/ginkgo-rtc.service
	ln -sf ../ginkgo-rtc-sync.timer $MNT/etc/systemd/system/timers.target.wants/ginkgo-rtc-sync.timer
	ln -sf /lib/systemd/system/systemd-timesyncd.service $MNT/etc/systemd/system/sysinit.target.wants/systemd-timesyncd.service
	ln -sf ../usb-gadget-rndis.service $MNT/etc/systemd/system/sysinit.target.wants/usb-gadget-rndis.service
	ln -sf ../ginkgo-ics-inet.service $MNT/etc/systemd/system/sysinit.target.wants/ginkgo-ics-inet.service
	ln -sf ../ensure-root-password.service $MNT/etc/systemd/system/sysinit.target.wants/ensure-root-password.service
	ln -sf /lib/systemd/system/ssh.service $MNT/etc/systemd/system/multi-user.target.wants/ssh.service
	ln -sf ../persist-mount.service $MNT/etc/systemd/system/multi-user.target.wants/persist-mount.service
	ln -sf ../ginkgo-power-mode.service $MNT/etc/systemd/system/basic.target.wants/ginkgo-power-mode.service
	rm -f $MNT/etc/systemd/system/basic.target.wants/ginkgo-performance.service
	ln -sf ../zram-setup.service $MNT/etc/systemd/system/basic.target.wants/zram-setup.service
	ln -sf ../ginkgo-bt-modules.service $MNT/etc/systemd/system/multi-user.target.wants/ginkgo-bt-modules.service
	ln -sf ../ginkgo-wifi-setup.service $MNT/etc/systemd/system/multi-user.target.wants/ginkgo-wifi-setup.service
	ln -sf /dev/null $MNT/etc/systemd/system/pd-mapper.service
	ln -sf /dev/null $MNT/etc/systemd/system/smartmontools.service
	sync
"

adb shell "umount $MNT"
rm -f "$TARBALL"
echo "==> Done. Reboot phone: adb reboot"
