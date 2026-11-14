#!/bin/sh
# Strip phone-useless cruft: snapd, GNOME session leftovers, CJK fonts and the
# Maliit keyboard stack (the KDE Qt virtual keyboard replaced it).
# Purge and autoremove work offline; nothing here needs the network.
set -eu

LOG=/var/log/ginkgo-debloat.log
exec >>"$LOG" 2>&1
echo "=== $(date -Is 2>/dev/null || date) ==="

if ! command -v apt-get >/dev/null; then
	mkdir -p /var/lib/ginkgo
	touch /var/lib/ginkgo-debloat.done
	exit 0
fi

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

# Protect core desktop, audio, networking and Bluetooth stacks from orphan pruning.
# plasma-nm hard-depends on Qt WebEngine libraries.
apt-mark manual \
	libqt6webenginecore6 libqt6webengine6-data libqt6webenginewidgets6 \
	plasma-desktop plasma-workspace plasma-nm plasma-pa \
	kwin-wayland kwin-common sddm sddm-theme-breeze \
	powerdevil kscreenlocker kde-cli-tools \
	pipewire pipewire-audio pipewire-pulse pipewire-bin libpipewire-0.3-modules \
	pipewire-alsa wireplumber libwireplumber-0.5-0 libcanberra-pulse \
	libspa-0.2-bluetooth libspa-0.2-modules \
	bluez bluedevil \
	network-manager wpasupplicant iw rfkill \
	openssh-server \
	2>/dev/null || true

# Packages that must never end up in a removal set.
# Using 'plasma-' guards plasma-desktop, plasma-workspace, plasma-nm, plasma-pa, etc.
# gnome-settings-daemon is intentionally excluded so GNOME leftovers can be purged.
GUARD='bluedevil|bluez|plasma-|kwin|sddm|network-manager|pipewire|wireplumber|plasma-pa|libspa|apparmor|systemd|openssh'

purge_set() {
	out=$(apt-get -s purge "$@" 2>&1) || true
	set_=$(echo "$out" | grep -E '^(Purg|Remv)' | awk '{printf "%s ", $2}')
	if echo "$set_" | grep -qE "$GUARD"; then
		echo "SKIP $*: would remove $set_"
		return 0
	fi
	echo "PURGE $* -> $set_"
	nice -n 19 ionice -c3 apt-get purge -y "$@" 2>/dev/null || true
}

# 1. Snap stack
purge_set snapd chromium-browser plasma-discover-backend-snap libsnapd-qt-2-1

# 2. GNOME control center, online accounts, docs, and CJK fonts / Maliit
purge_set \
	gnome-control-center gnome-control-center-data gnome-control-center-faces \
	gnome-online-accounts kaccounts-providers gnome-remote-desktop \
	ubuntu-docs gnome-user-docs khelpcenter khelpcenter-data \
	fonts-noto-cjk \
	maliit-keyboard maliit-framework maliit-server-qt5 \
	maliit-inputcontext-qt6 maliit-inputcontext-qt5 maliit-inputcontext-gtk3

# 3. Explicitly purge GNOME settings daemon and window manager leftovers
purge_set \
	gnome-settings-daemon gnome-settings-daemon-common \
	mutter-common mutter-common-bin \
	gnome-desktop3-data gnome-desktop-common \
	gnome-session-bin gnome-session-common \
	gnome-startup-applications \
	libgnome-autoar-0-0

# 4. Safe autoremove for all remaining orphaned GNOME libraries (libgnome-*, etc.)
out=$(apt-get -s autoremove --purge 2>&1) || true
if echo "$out" | grep -E '^(Purg|Remv)' | grep -qE "$GUARD"; then
	echo "SKIP autoremove: would remove $(echo "$out" | grep -E '^(Purg|Remv)' | grep -E "$GUARD")"
else
	echo "AUTOREMOVE $(echo "$out" | grep -cE '^(Purg|Remv)') packages"
	nice -n 19 ionice -c3 apt-get autoremove -y --purge 2>/dev/null || true
fi

# Do not start heavy helpers at login
DISABLE_AT_STARTUP="
kaccess
org.kde.discover.notifier
org.gnome.Evolution-alarm-notify
ubuntu-advantage-notification
update-notifier
snap-userd-autostart
im-launch
geoclue-demo-agent
gmenudbusmenuproxy
user-dirs-update-gtk
xembedsniproxy
kup-daemon
"

for d in $DISABLE_AT_STARTUP; do
	src=/etc/xdg/autostart/$d.desktop
	[ -f "$src" ] || continue
	for home in /home/*; do
		[ -d "$home" ] || continue
		user=$(stat -c '%U' "$home")
		[ "$user" = root ] && continue
		mkdir -p "$home/.config/autostart"
		cp "$src" "$home/.config/autostart/$d.desktop"
		if grep -q '^Hidden=' "$home/.config/autostart/$d.desktop"; then
			sed -i 's/^Hidden=.*/Hidden=true/' "$home/.config/autostart/$d.desktop"
		else
			printf 'Hidden=true\n' >> "$home/.config/autostart/$d.desktop"
		fi
		chown -R "$user:$user" "$home/.config/autostart"
	done
done

# Baloo indexes every file for search; on a phone it only burns battery.
for home in /home/*; do
	[ -d "$home" ] || continue
	user=$(stat -c '%U' "$home")
	[ "$user" = root ] && continue
	mkdir -p "$home/.config"
	printf '[General]\nenabled=false\n' > "$home/.config/baloofilerc"
	chown "$user:$user" "$home/.config/baloofilerc"
done

mkdir -p /var/lib/ginkgo
touch /var/lib/ginkgo-debloat.done
echo "done"
