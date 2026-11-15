# Redmi Note 8 (ginkgo) Agent Interaction Index & Operational Reference

> Device: Xiaomi Redmi Note 8 · codename **ginkgo** · SoC **SM6125 (trinket)** · serial `<serial>`  
> System: mainline Linux 7.0 + Ubuntu 26.04 LTS arm64 (`resolute`), rootfs on `userdata`  
> Panel on this unit: **Tianma** NT36672A video-mode DSI (`androidboot.dsi_display0=dsi_nt36672a_tianma_vid_display`)  
> Purpose of this page: operational index and reference for AI agents and developers interacting with the phone — how to reach it, execute commands, configure networking, sideload packages, inspect system state, and build/flash.  
> Status and history live in [ginkgo-mainline-bringup-chronicle.md](docs/audit/ginkgo-mainline-bringup-chronicle.md).

**Related docs & scripts**

| Document / Script | Content |
|-------------------|---------|
| [docs/ginkgo-journey-to-remote-ssh.md](docs/audit/ginkgo-journey-to-remote-ssh.md) | How the RNDIS + SSH channel came to be |
| [docs/ginkgo-usb-ttl-uart.md](docs/audit/ginkgo-usb-ttl-uart.md) | 1.8 V UART wiring (never the EDL pads) |
| [docs/flash-guide.md](docs/flash-guide.md) | Flashing a release `boot.img` + empty dtbo |
| [docs/mainline-ginkgo-porting-guide.md](docs/audit/mainline-ginkgo-porting-guide.md) | Hardware map and staged plan |
| [scripts/usb-connect.sh](scripts/usb-connect.sh) | Host-side RNDIS setup after every reboot |
| [scripts/ssh-run.sh](scripts/ssh-run.sh) | One remote command, Linux host |
| [scripts/ssh_cmd.py](scripts/ssh_cmd.py) | Preferred direct SSH command helper for agents |

---

## 0. One-sentence conclusion

The phone is only ever reachable over **one USB cable that carries a virtual network card (RNDIS)**: `192.168.7.2` is the SSH/debug address, `192.168.137.50` is a *second* address on the same interface that only reaches the internet if Windows Internet Connection Sharing is switched on — and when it is off, which is the normal state, everything (packages, kernels, configs) is installed by hand from the host.

### Git checkpoints and recoverable deployments (agent directive)

- Before changing drivers, boot configuration, or deployment scripts, inspect `git status --short` and the relevant diffs, and record the branch and commit SHA. Preserve existing work, including untracked files. Use explicit paths when staging; never sweep unrelated changes into a commit with `git add .` or `git add -A`.
- Preserve the working baseline **before** experimenting. Make focused local checkpoint commits for task-related source/configuration changes unless the owner has instructed otherwise. Preserve pre-existing changes outside the task separately without modifying them. If a relevant uncommitted baseline cannot be committed cleanly, save its exact diff and untracked files in a named backup and record where they are. Do not rely on memory or an ignored `out/` file as the only record of source changes.
- Before flashing, checkpoint the exact source, configuration, and build/repack scripts used for the candidate. Record that commit SHA, artifact paths and SHA256 hashes, kernel release/vermagic, and the checks performed in the handoff. If the build includes uncommitted changes, explicitly mark it dirty and preserve those exact changes; do not describe it as a reproducible build of HEAD.
- Keep the previous boot image and deployed modules under distinct backup names before replacing them. Verify backups completed and record their hashes. Git records source history; it does not back up the phone's partitions or ignored build artifacts. Keep binary backups out of ordinary source commits.
- Call a revision **known good** only for behavior actually tested on that revision/artifact. Record checks such as boot, display, touch, USB unplug, and percentage reporting individually as passed, failed, or untested. Neither HEAD nor a successful build proves the running phone matches that source or that unplugging works.
- On regression, prepare a targeted rollback from the recorded baseline, preserving unrelated work and the deployed core kernel. Prefer a focused `git revert` for committed changes, or a separate worktree/build of the baseline when appropriate. Never use `git reset --hard`, `git clean`, broad checkout/restore, or an unreviewed stash operation to discard the owner's work. Identify the exact image/module being restored and verify the restored behavior before declaring recovery.
- Local checkpoints do not authorize pushing, force-pushing, rewriting shared history, or flashing additional partitions. Follow the owner's deployment instructions and existing scope; do not ask again for an action already authorized.

---

## 1. Device identity and storage layout

| Item | Value |
|------|-------|
| Kernel | `Linux ginkgo 7.0.0-00001-g62f9dac57de4-dirty`, `#142 SMP PREEMPT`, aarch64 |
| Distro | Ubuntu 26.04 LTS (`resolute`), arm64 |
| Root device | `/dev/mmcblk0p87` (`userdata`, 48.9 GB, ext4 `noatime`), mounted by the initramfs at `/` |
| Boot slots | `boot` = `mmcblk0p72`, `bootbak` = `mmcblk0p73` (64 MB each) |
| Persist | `/dev/mmcblk0p69` → `/persist`, mounted **read-only**, late, by `persist-mount.service` |
| Users | `root` (uid 0, `/bin/bash`), `ginkgo` (uid 1000, `/bin/bash`) |
| RAM | 3564 MB, **2 GB ZRAM swap (LZ4)** enabled via `zram-setup.service` (`/dev/zram0`, priority 100) |
| Kernel cmdline essentials | `console=ttyMSM0,115200n8 earlycon=qcom_geni,0x4a90000 quiet loglevel=4 mitigations=off root=/dev/disk/by-partlabel/userdata rootwait rw init=/init skip_initramfs clk_ignore_unused fw_devlink.sync_state=disabled` — `DEBUG_BOOT=1 scripts/build-bootimg.sh` builds the verbose `out/boot-debug.img` (`keep_bootcon ignore_loglevel loglevel=8 initcall_debug debug`) for bringup |

`androidboot.verifiedbootstate=orange` — the bootloader is unlocked, so `fastboot flash` works, and a `fastboot boot` (no flash) is the normal test loop.

### 1.1 Clock: PM6125 RTC (`/dev/rtc0`)

The primary PMIC PM6125 provides hardware RTC (`rtc@6000`). It is driven by `rtc-pm8xxx.ko` and managed by `ginkgo-rtc.service` (`/usr/local/sbin/ginkgo-rtc-sync.sh`).

On boot, `/dev/rtc0` initializes and systemd-timesyncd maintains synchronization whenever Wi-Fi is active. The hardware RTC retains ticking seconds continuously even across reboots and power cycles.

Manual clock inspection and sync:
```sh
timedatectl               # verify NTP active and RTC time
hwclock -r                # read hardware clock
hwclock -w                # write system time to hardware clock
```

### 1.2 Performance, Boot Speed, and Security Mitigations

> **WARNING: SPECTRE AND MELTDOWN HARDWARE MITIGATIONS ARE DELIBERATELY DISABLED (mitigations=off).**
> **THIS SYSTEM IS NOT A MULTI-USER OR MISSION-CRITICAL ENVIRONMENT. IT RUNS ON A DIRECT ISOLATED USB LINK.**
> **SPECULATIVE STORE BYPASS, BRANCH PREDICTOR HARDENING, AND USER POINTER SANITIZATION ARE TURNED OFF TO MAXIMIZE CPU PIPELINE THROUGHPUT ON KRYO 260 CORES.**

> **AGENT DIRECTIVE — DO NOT RE-ENABLE THESE. The owner disabled them on purpose for extra performance and wants them kept off. This is a decision, not a bug to fix.**
> - **Keep `mitigations=off`** on the kernel cmdline. Never add `mitigations=auto`, `spectre_v2=...`, `spec_store_bypass_disable=...`, `l1tf=...`, or any other hardening flag.
> - **Keep AppArmor disabled** (`/sys/module/apparmor/parameters/enabled = N`, `apparmor.service` inactive). Do not enable or start it.
> - Do not "harden", audit, or re-enable any security mitigation on this image. Nothing sensitive runs here; the priority is speed and a clean, debloated system.

Key Performance Characteristics:
- Kernel Boot Cmdline: `quiet loglevel=4 mitigations=off` (eliminates the slow 115200 baud UART printing bottleneck that previously stalled boot by over 6 seconds).
- Boot Times: Userspace boot dropped from 41.8s to 11.1s (74% faster). `graphical.target` reached in only 7.2s.
- CPU Governor: `ginkgo-power-mode.service` runs early before `basic.target` and applies the profile in `/etc/ginkgo-power-mode.conf` (default `balanced`: `schedutil` on every cpufreq policy, `schedutil`/`simple` on the Adreno 610 devfreq, deep cpuidle states allowed). `sudo ginkgo-power-mode.sh performance` reproduces the old behaviour (all 8 cores pinned at 1.80/2.02 GHz, GPU at max) and `eco` pins everything to its minimum. Pinning everything at maximum drained the 4000 mAh cell in hours and idled the SoC at ~40 °C, so it is no longer the default.
- Power Management: `~/.config/powerdevilrc` disables dim/blank on idle for every profile (`[AC]`, `[Battery]`, `[LowBattery]` → `[Display]`), so the panel never sleeps. `kscreenlockerrc` has `Autolock=false`. Both cost battery; `/usr/local/sbin/ginkgo-power-mode.sh` is the other half of that trade-off.
- Disabled Daemons: Masked `fwupd.service`, `fwupd-refresh.service`, `apport.service`, `pd-mapper.service`, `smartmontools.service`, and `maliit-server.service` to prevent background CPU burns and infinite crash loops.
- Memory Tuning: `vm.swappiness = 100`, `vm.page-cluster = 0` (zero readahead latency), `vm.watermark_boost_factor = 0`, and `vm.vfs_cache_pressure = 50`.


---

## 2. The three physical access paths

| Path | When it works | What you get |
|------|---------------|--------------|
| **USB RNDIS** (`usb-gadget-rndis.service`) | after `boot.img` reaches systemd | full SSH/root shell — the primary channel |
| **1.8 V UART** on `ttyMSM0`, 115200 8N1 | from the first kernel line onward | `scripts/capture-uart.sh /dev/ttyUSB0` (picocom, `Ctrl-A Ctrl-X` to quit). **1.8 V logic only**; see the wiring doc before probing the EDL pads |
| **fastboot** | Vol− + Power from power off, or `reboot-fastboot` / `reboot bootloader` from Ubuntu | `scripts/flash-boot.sh`, `make-vbmeta.sh`, `make-empty-dtbo.sh`; `scripts/reboot-fastboot.sh` gets there from SSH and waits for the device |
| **USB host mode** (OTG keyboard/mouse) | on demand, one command | `ginkgo-usb-host.sh` flips the Type-C port away from the gadget — **SSH drops and does not come back until the phone reboots** |

There is **no adb** on this device any more (mainline does not run Android's adbd). `scripts/capture-logs.sh` and `scripts/backup-device.sh` still talk adb because they are also used while dual-booting or in recovery.

The host side must be re-pointed after **every phone reboot** — the host NIC is a new `enx*`/`rndis` interface each time and NetworkManager will otherwise DHCP-fail and flush the static address:

```sh
sudo scripts/usb-connect.sh          # Linux host: finds iface, sets 192.168.7.1/24, pings, probes SSH
```

The `nmcli device set <iface> managed no` step inside that script is not cosmetic: without it NM deletes the address you just added.

---

## 3. SSH methods

### Preferred agent command helper

Use `python scripts/ssh_cmd.py "<command>"` for routine remote commands. It requires Python and Paramiko, defaults to USB at `192.168.7.2`, prints only the remote output, and returns the remote command's exit status. Keep commands focused and limit verbose logs (for example, `journalctl -n 100`) to conserve context. The helper executes commands only; use SSH/SCP separately for stdin scripts or file transfers.

```powershell
python scripts/ssh_cmd.py 'uname -a'
$env:GINKGO_IP = '10.220.61.7'  # example only: use the phone's current Wi-Fi address
python scripts/ssh_cmd.py 'ip -br addr'
Remove-Item Env:GINKGO_IP       # return to USB
```

`GINKGO_ROOT_PASSWORD` optionally overrides the documented default password. The helper does not configure the host USB interface or automatically switch between USB and Wi-Fi. On Linux, run `scripts/usb-connect.sh` first when needed. The methods below remain available for transfers and other SSH workflows.

### 3.1 Linux host (the scripted way)

```sh
scripts/ssh-run.sh 'uname -a'        # runs usb-connect.sh first, then one command
ssh -b 192.168.7.1 root@192.168.7.2 # after usb-connect.sh; -b pins the source address
```

`ssh-run.sh` needs `sshpass`. It reads the password through `scripts/lib-ginkgo-pass.sh`, which takes `$GINKGO_ROOT_PASSWORD` or the gitignored file `rootfs-overlay/etc/ginkgo-root-password`.

### 3.2 Windows / Git Bash (no sshpass installed)

For commands, prefer `scripts/ssh_cmd.py` above. For OpenSSH/SCP without an interactive password prompt, set up an askpass helper:

```sh
printf '#!/bin/sh\necho <root password>\n' > /c/Users/<user>/AppData/Local/Temp/gk-askpass.sh
chmod 700 /c/Users/<user>/AppData/Local/Temp/gk-askpass.sh   # 0700, contains the password
```

Then every call carries three variables — `SSH_ASKPASS`, `SSH_ASKPASS_REQUIRE=force` and an **empty** `DISPLAY=` (without them ssh silently waits for a terminal prompt):

```sh
SSH_ASKPASS=/c/Users/<user>/AppData/Local/Temp/gk-askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY= \
  ssh -o StrictHostKeyChecking=accept-new -o ConnectTimeout=10 root@192.168.7.2 'uname -a'

SSH_ASKPASS=/c/Users/<user>/AppData/Local/Temp/gk-askpass.sh SSH_ASKPASS_REQUIRE=force DISPLAY= \
  scp -q somefile root@192.168.7.2:/tmp/
```

Reachability probe (Windows `ping` flags, not the Unix ones): `ping -n 1 -W 1500 192.168.7.2`.

### 3.3 Quoting rules that actually save time

Nested quotes over `ssh '... awk "{print \$2}" ...'` break on `$`, on `'` and on unmatched brackets. For anything longer than one command, keep the script local and pipe it into a shell:

```sh
ssh root@192.168.7.2 'bash -s' < ./local-probe.sh      # no escaping needed at all
ssh root@192.168.7.2 'sh -s'   < ./local-probe-posix.sh
```

Keep remote commands short and finite: long `while`/`sleep` polling loops over this link get killed when the RNDIS interface flaps, and a lost session mid-command is how a driver `unbind` was once left without its matching `bind` (only a reboot recovered it).

### 3.4 Password policy

- **Logins (intentionally trivial — isolated single-user hobby device on a direct USB cable):**
  - `root` → password **`password`**
  - `ginkgo` (uid 1000, the autologin desktop user, member of `sudo`) → password **`ginkgo`** (the username itself)
- The root password is baked into the image by `ensure-root-password.service` from `/etc/ginkgo-root-password`, staged from the gitignored `rootfs-overlay/etc/ginkgo-root-password` (or `$GINKGO_ROOT_PASSWORD`). That file holds `password`. These credentials are documented here on purpose; do not treat them as a secret to rotate.
- `sshd` on this image is `PermitRootLogin yes` + `PasswordAuthentication yes` (see `rootfs-overlay/etc/ssh/sshd_config.d/99-ginkgo.conf`) — acceptable only because the link is a direct USB cable.
- Delete the askpass helper when a session ends; it is a plaintext copy of the password.

---

## 4. What the USB link actually carries

`usb0` on the phone holds **two** IPv4 addresses, from two different services:

| Address | Set by | Purpose |
|---------|--------|---------|
| `192.168.7.2/24` | `usb-gadget-rndis.sh` | management: SSH/SCP from host `192.168.7.1` |
| `192.168.137.50/24` + default route via `192.168.137.1` | `ginkgo-ics-inet.sh` | internet, through Windows ICS |

NetworkManager is told to leave both alone (`rootfs-overlay/etc/NetworkManager/conf.d/99-usb-gadget.conf` unmanages `usb0`/`rndis0`), so nothing DHCP-rewrites them.

On the Windows side the same adapter (shown as `Local Area Connection` in `netsh interface show interface`) carries the static pair `192.168.7.1` and `192.168.137.1`.

Re-check from the host:

```sh
ip -br addr; ip route; cat /etc/resolv.conf     # on the phone
systemctl restart ginkgo-ics-inet.service       # re-apply ICS address/route/DNS after a host change
```

---

## 5. Network Connectivity: Dual-Path Access (USB RNDIS + Wi-Fi)

The device supports dual-path networking:
1. **USB RNDIS (`usb0`)**: The primary high-speed management link (`192.168.7.2`). Always available after boot.
2. **Wi-Fi (`wlan0`)**: Driven by `ath10k_snoc` on WCN3990. Requires modem subsystem boot (`ginkgo-mpss.service` starting `/lib/firmware/qcom/sm6125/modem.*`). When connected to a local hotspot or router, `wlan0` provides direct internet access and allows wireless SSH (`scripts/ssh_cmd.py` uses `$env:GINKGO_IP` when set).

When Wi-Fi is disconnected, internet traffic over USB can use Windows ICS or Linux NAT.

### 5.1 Option A: Windows Internet Connection Sharing (over USB)

The phone half is already done (`ginkgo-ics-inet.service`, enabled at `sysinit.target`, adds `192.168.137.50/24`, the default route and `nameserver 8.8.8.8 / 1.1.1.1`).

Host side, once per session:

1. `Control Panel → Network Connections` (or Settings → Advanced network → More network options).
2. Right-click the adapter that **has** internet (Wi-Fi or Ethernet) → Properties → **Sharing**.
3. Tick *Allow other network users to connect through this computer's Internet connection*, pick the RNDIS adapter (`Local Area Connection`, the one holding 192.168.7.x) as the home network. Windows then pins `192.168.137.1` on it.
4. On the phone: `systemctl restart ginkgo-ics-inet.service`, then fix the clock (§1.1) before using apt.

Verify with HTTP, **not ping** — Windows Firewall normally drops ICMP echo replies on that interface, so a working link still looks dead to `ping 192.168.137.1`:

```sh
ssh root@192.168.7.2 'wget -S -T 10 -O /dev/null http://ports.ubuntu.com/ubuntu-ports/dists/resolute/InRelease'
```

`curl` is **not installed** on the device; `wget` is.

### 5.2 Option B — Linux host NAT

```sh
sudo scripts/usb-connect.sh
sudo sysctl -w net.ipv4.ip_forward=1
UPLINK=$(ip route show default | awk '{print $3; exit}')      # the PC's own internet iface
PHONE_IF=enxPH                                                # name from usb-connect.sh output
sudo iptables -t nat -A POSTROUTING -o "$UPLINK" -j MASQUERADE
sudo iptables -A FORWARD -i "$PHONE_IF" -o "$UPLINK" -j ACCEPT
sudo iptables -A FORWARD -m state --state RELATED,ESTABLISHED -j ACCEPT
```

Then on the phone the `192.168.7.1` gateway works as-is; add DNS with `systemctl restart ginkgo-ics-inet.service` (it writes `/etc/resolv.conf`) or point it at the host's `192.168.7.1`.

### 5.3 Option C — no internet at all (what the project normally does)

Sideloading is the reliable route, and the trick is that **the phone already knows the exact deb path and hash** from its cached apt index. Five steps:

```sh
# 1. Ask the phone which file it wants, with the mirror path and SHA256.
ssh root@192.168.7.2 'zgrep -h -A20 "^Package: grim$" /var/lib/apt/lists/*Packages* |
  grep -E "^(Filename|Size|SHA256):"'

# 2. Download it on the host (official ports archive; %2b = the literal '+' in the filename).
curl -fsSLO 'http://ports.ubuntu.com/ubuntu-ports/pool/universe/g/grim/grim_1.4.0%2bds-2build3_arm64.deb'

# 3. Compare the hash against the phone's index before transferring anything.
sha256sum grim_1.4.0+ds-2build3_arm64.deb

# 4. Copy and install.
scp -q grim_*.deb root@192.168.7.2:/tmp/
ssh root@192.168.7.2 'dpkg -i /tmp/grim_*.deb && rm /tmp/grim_*.deb'
```

`apt-get install --print-uris` on the phone gives the same URL list without touching the network. Anything the phone does **not** have in its index cannot be installed offline — its dependency closure has to be walked by hand, which is why small tools with no new deps are preferred.

### 5.4 Mirror facts worth keeping

- Archive: `http://ports.ubuntu.com/ubuntu-ports`, suites `resolute`, `-updates`, `-backports`, `-security` (`rootfs-overlay/etc/apt/sources.list.d/ubuntu.sources`).
- **No China mirrors.** The operator is in India; Tsinghua TUNA and the other Chinese mirrors are slow or unreachable from this network, so every suite (`-security` included) comes from `ports.ubuntu.com`.
- HTTPS works once `ca-certificates` is installed; the earlier "CA verify error" was the missing CA store, not the archive.
- Purges and `dpkg` operations never need the network; a broken link does not block removals.

---

## 6. Desktop session on the device

| Aspect | Value |
|--------|-------|
| Display manager | SDDM, `Autologin User=ginkgo`, `Session=plasma` (`/etc/sddm.conf.d/10-ginkgo.conf`, theme `breeze`) |
| Session | KDE Plasma **Wayland** — `kwin_wayland` + `plasmashell`, Xwayland for X clients |
| Where the greeter lives | SDDM's own greeter runs as user `sddm` (uid 109); the Plasma lock screen is `kscreenlocker_greet` inside the user's session |
| Restart the session | `systemctl restart sddm` (kills Plasma, autologin brings it back; SSH is unaffected) |
| Lock it for testing | `loginctl lock-session` as `ginkgo` |

Anything user-session related has to be run as the session user with the right bus, otherwise you query root's empty D-Bus and get `Name not provided by any .service files`:

```sh
uid=$(id -u ginkgo)
sudo -u ginkgo XDG_RUNTIME_DIR=/run/user/$uid \
     DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/$uid/bus \
     busctl --user get-property org.kde.KWin /VirtualKeyboard org.kde.KWin.VirtualKeyboard available
```

Environment for the session comes from `~/.config/environment.d/*.conf` (user) and `/etc/environment.d/*.conf` (all users, including the greeter); `/etc/profile.d/im-config_wayland.sh` is deliberately neutered by Ubuntu (`if false`), so input-method variables are **not** set from the profile — check the file that sets them before blaming the desktop.

**Screenshots from the shell do not work on this build**: `grim` needs `wlr-screencopy-unstable-v1` (KWin does not advertise it) and KWin exposes no `/Screenshots` D-Bus object, so `busctl --user tree org.kde.KWin` is as close as it gets. Visual confirmation has to come from a person looking at the panel.

**Xwayland needs `/tmp/.X11-unix` to pre-exist**: kwin is launched with `--xwayland`, but if that directory is missing `kwin_xwl` aborts with `/tmp/.X11-unix does not exist` → `Failed to establish X11 socket`, and the X11-only Plasma helpers (`plasma-kaccess`, `plasma-ksmserver`, `plasma-xembedsniproxy`, `plasma-gmenudbusmenuproxy`) fail because they cannot reach an X server. `/tmp` is a tmpfs that systemd mounts **late**: an ordering cycle (`tmp.mount → swap.target → zram-setup.service → local-fs.target → tmp.mount`) makes systemd defer `tmp.mount` past `systemd-tmpfiles-setup.service`, so a tmpfiles-created `/tmp/.X11-unix` lands on the rootfs and is then shadowed by the late tmpfs mount. `ginkgo-x11-dir.service` (`After=tmp.mount`, `Before=sddm.service`) creates the directory on the mounted tmpfs and fixes Xwayland persistently (`/tmp/.X11-unix/X0`, `DISPLAY=:0`). Do not try to fix this by editing `zram-setup.service` alone — its `After=local-fs.target` is re-added as an implicit dependency, and the boot.img ramdisk re-applies `rootfs-overlay/` over the rootfs every boot (overwriting existing files, keeping new ones), so edits to existing units need a boot.img rebuild while new files like this service survive. The Flatpak `xdg-document-portal.service` fails because the kernel has no `fuse.ko` (`CONFIG_FUSE_FS=m` but the module is not deployed); that is pre-existing and harmless without flatpak. **Do not mask it** — `xdg-desktop-portal.service` requires it and fails when it is masked.

---

## 7. Units the phone runs (and which are in the repo)

| Unit | Enabled | What it does | In overlay |
|------|---------|--------------|------------|
| `usb-gadget-rndis.service` | yes | Brings up the RNDIS gadget and `192.168.7.2` | yes |
| `ginkgo-ics-inet.service` | yes | Second IP + default route + DNS for ICS internet | yes |
| `ensure-root-password.service` | yes | Applies the root password from `/etc/ginkgo-root-password` | yes |
| `persist-mount.service` | yes | Late read-only mount of `persist` (avoids a 90 s udev stall) | yes |
| `display-unblank.service` | no | Blanks/turns the panel on without the desktop (disabled when SDDM is present to avoid DRM collision) | yes |
| `ginkgo-mpss.service` | yes | Starts the modem (MPSS) — a prerequisite for WCN3990 Wi-Fi | yes |
| `ginkgo-wifi-setup.service` | yes | IN regulatory domain + stable MAC once `wlan0` exists | yes |
| `ginkgo-battery.service` | yes | `insmod /lib/modules/ginkgo-extra/qcom-pmi632-qg.ko` to make the gauge appear | **no** — the repo compiles that driver in |
| `ginkgo-power-mode.service` | yes | applies the CPU/GPU power profile (`/etc/ginkgo-power-mode.conf`, default `balanced`) | yes |
| `ginkgo-performance.service` | no | pins CPU/GPU at maximum for the whole session — superseded by `ginkgo-power-mode.sh performance` | yes |
| `ginkgo-debloat.service` | no | one-shot package/autostart trim, `ConditionPathExists=!/var/lib/ginkgo-debloat.done` | yes |
| `ginkgo-remove-desktop.service` | no | historical GNOME removal (repo was GNOME-first) | yes |
| `npc.service` | no | `npc` tunnel client, config from `/etc/npc/npc.env` | yes |
| `serial-getty@ttyMSM0.service` | yes | UART login | yes |
| `ssh.service` (+ drop-in) | yes | root SSH over the gadget link | yes |
| `ginkgo-bt-modules.service` | yes | Loads Bluetooth crypto (ECC, ECDH) and profile modules (RFCOMM, BNEP, HIDP) | yes |
| `zram-setup.service` | yes | Configures 2GB LZ4 compressed RAM swap device (`/dev/zram0`, priority 100) | yes |

Also on the phone and now in the overlay: `bluetooth.service.d/bdaddr.conf` → `/usr/local/sbin/bt-set-addr.sh`, which programs a stable locally-administered BD address before `bluetoothd` starts (the WCN3990 ROM ships without a valid one, and the kernel loses it on every power cycle — that is why Bluetooth looks like a different device after each reboot). `ginkgo-full-performance.sh` online's all eight cores, forces `performance` on every `cpufreq` policy and pins the Adreno 610 devfreq to `max_freq`.

Battery: `/sys/class/power_supply/qcom-battery` is driven by `CONFIG_BATTERY_QCOM_PMI632_QG=y` and `overlays/linux/drivers/power/supply/qcom-pmi632-qg.c`. The DT node `qgauge@4800` is defined under `pmic@2` beside `usb-vbus-regulator@1100` via `overlays/linux/0002-pmi632-qg-panel-sleep.patch` for `arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dts`. Verify with `dtc -I dtb -O dts arch/arm64/boot/dts/qcom/sm6125-xiaomi-ginkgo.dtb | grep qgauge`.

### 1.3 Kernel Binary vs Raw Upstream Build Warning

> **CRITICAL ARCHITECTURAL WARNING FOR AGENTS: DO NOT REPLACE DEPLOYED KERNEL WITH RAW UPSTREAM v7.0**
>
> 1. The baseline kernel at `out/deployed-unpack/kernel` (`Linux ginkgo 7.0.0-00001-g62f9dac57de4-dirty #142 SMP PREEMPT`) contains downstream SM6125 DPU/DSI patches and calibration code (e.g. `msm_dsi_manager_host_enable`, `dsi_phy_clamp`) necessary for the Tianma NT36672A video-mode DSI display panel.
> 2. Compiling a raw vanilla kernel from `torvalds/linux.git v7.0` lacks these patches. Booting such a raw kernel results in a hardware failure to initialize DSI video pixel clocks, presenting as an **empty black screen with only backlight illuminated** (no fbcon, no boot logs, no userspace).
> 3. **Rule for adding hardware drivers**: Always build extra drivers (such as `qcom-pmi632-qg.ko`, `rtc-pm8xxx.ko`, `qcom_usb_vbus-regulator.ko`, `userspace-consumer.ko`) as out-of-tree `.ko` kernel modules matching vermagic `7.0.0-00001-g62f9dac57de4-dirty`, place them in `overlay/lib/modules/ginkgo-extra/` inside the ramdisk, and keep `out/deployed-unpack/kernel` as the core kernel binary.

Note that `make` here always needs `ARCH=arm64 CROSS_COMPILE=aarch64-linux-gnu-`; a bare `make olddefconfig` rewrites `.config` for the host, and the next thing you see is `No rule to make target 'Image.gz'`. The config that actually ships is recoverable from any good kernel image with `scripts/extract-ikconfig`.

### 1.4 Touchscreen Architecture, Charger-Mode Fix & Sleep/Wake Sync

The Tianma NT36672A touchscreen controller shares power with the LCD panel via the PMIC LCDB regulator (`qpnp-lcdb@ec00`).
It has two critical operating requirements:
1. **Charger Mode Detection**: When booted with a USB cable connected, Little Kernel appends `androidboot.mode=charger`. The downstream touch driver checked `strstr(saved_command_line, "androidboot.mode=charger")` and aborted registration (`return -ENODEV`). The needle in the kernel image is patched to `androidboot.mode=nocharg` so touch registers regardless of boot mode.
2. **Volatile SRAM Firmware**: NT36672A has no on-chip flash memory. When the panel power rails (`vsp`/`vsn`) drop during display blanking or system suspend, touch SRAM is cleared.
3. **Resume Sync Module (`ginkgo_touch_sync.ko`)**:
   - `ginkgo-touch-sync.service` loads `/lib/modules/ginkgo-extra/ginkgo_touch_sync.ko` with exact resolved symbols from `/proc/kallsyms`.
   - Exposes `/sys/kernel/ginkgo_touch/resume`. Writing `1` reloads `novatek_ts_tianma_fw.bin` into SRAM (< 300 ms), checks `RESET_STATE_REK`, and re-enables IRQ 135.
   - Automatically triggered on system resume via `/lib/systemd/system-sleep/touch-wake.sh` and on display unblank via `ginkgo-touch-monitor.service`.

### 1.5 Bluetooth (WCN3990), Crypto Modules, Firmware Partition & Headset Pairing

#### 1. Hardware Architecture & ROM Mode
- **Controller**: Qualcomm WCN3990 combo chip (Wi-Fi + Bluetooth) integrated with SM6125.
- **HCI Interface**: Communicates via `qup_uart9` (`ttyMSM1`) driven by `hci_qca.ko`.
- **ROM Mode Operation**: Under `#142` kernel with `0003-wcn3990-bt-rom-mode-fix.patch`, the driver operates with `qca_skip_fw = true` and `qca_skip_oper_speed = true`, keeping the controller in ROM mode at 115200 baud.
- **BD Address Assignment**: In ROM mode, the controller powers on with an unassigned or invalid hardware address. `bluetooth.service.d/bdaddr.conf` executes `/usr/local/sbin/bt-set-addr.sh` prior to `bluetoothd`, programming a persistent address (`86:D2:39:0F:1E:EE`), enabling Secure Simple Pairing (`ssp`) and Secure Connections (`sc`), and powering up the radio.

#### 2. Mandatory Out-of-Tree Kernel Modules (`ginkgo-bt-modules.service`)
Standard upstream BlueZ fails to establish SMP (Security Manager Protocol) or profile sockets without specific crypto and transport drivers. Because the baseline `#142` kernel did not build these into the core image, they must be compiled matching vermagic `7.0.0-00001-g62f9dac57de4-dirty` and loaded from `/lib/modules/ginkgo-extra/`:
- `ecc.ko` and `ecdh_generic.ko`: Kernel crypto primitives required by BlueZ for Elliptic Curve Diffie-Hellman pairing and Bluetooth 4.2+ LE Secure Connections.
- `rfcomm.ko`: Serial port emulation protocol for headset control, serial profiles, and AT commands.
- `bnep.ko`: Bluetooth Network Encapsulation Protocol for PAN / tethering.
- `hidp.ko`: Human Interface Device Profile for Bluetooth mice, keyboards, and input devices.

#### 3. EMMC Factory Firmware Partition (`/dev/mmcblk0p36`)
The phone stores Qualcomm reference and factory Bluetooth rampatches on raw EMMC partition 36:
- **Device node**: `/dev/mmcblk0p36` (vfat, labeled `bluetooth`, size 2MB).
- **Contents**: `/image/` directory containing all hardware revisions: `crbtfw11.tlv`, `crbtfw20.tlv`, `crbtfw21.tlv`, `crnv11.bin`, `crnv20.bin`, `crnv21.bin`, `cmbtfw12.tlv`, `cmnv12.bin`.
- **System path**: Files in `/lib/firmware/qca/` (`crbtfw12.tlv` 44955 bytes, `crnv12.bin` 2590 bytes) are byte-for-byte identical to the onboard factory partition.

#### 4. Dual-Mode Audio Headsets & Pairing Mechanics (e.g. OnePlus Bullets Wireless Z2)
Modern wireless headsets exhibit distinct behavioral states that must be accounted for during automation:
- **Separated Earbuds vs Button Pairing**:
  - Pulling magnetic earbuds apart puts the headset in *reconnection mode* for ~30 seconds, actively paging its bonded master (e.g. host Windows PC) and ignoring all unknown MACs (`Page Timeout 0x04`).
  - To pair with a new device, hold the physical pairing button for 3 seconds until the LED pulses white.
- **LE Advertisement vs BR/EDR Audio**:
  - In pairing mode, the headset advertises over BLE (`ADV_IND`, RSSI approx -47 dBm) including Google Fast Pair Service (`0xFE2C`).
  - A2DP high-definition audio and AVRCP controls operate over classic BR/EDR.
  - If BlueZ records `LastUsedBearer=le` without completing SMP or cross-transport derivation, subsequent connections stall. Ensure device profile sets `SupportedTechnologies=BR/EDR;LE;` or force connection across classic bearer once bonded.
- **Interactive Authentication Agent**: BlueZ requires an active D-Bus agent (`DisplayYesNo` or `KeyboardDisplay`) to confirm the pairing prompt. Running an automated agent (`pair_agent.py` or `bluetoothctl default-agent`) is required during pairing to prevent `org.bluez.Error.ConnectionAttemptFailed` timeouts.

#### 5. USB Type-C OTG Host vs Device Gadget Switching
The Type-C port on SM6125 uses dual-role controller switching:
- **Gadget Mode (Default RNDIS Network)**:
  - Role: `device` (`/sys/class/usb_role/4e00000.usb-role-switch/role`).
  - VBUS 5V Boost: `disabled` (`/sys/bus/platform/devices/otg-vbus/state`).
  - UDC Binding: `4e00000.usb` bound to `/sys/kernel/config/usb_gadget/ginkgo/UDC`.
- **Host Mode (OTG Peripherals: Keyboard, Mouse, Flash Drives)**:
  - Activated by `/usr/local/sbin/ginkgo-usb-host.sh`.
  - Turns on 5V VBUS boost regulator: `echo enabled > /sys/bus/platform/devices/otg-vbus/state`.
  - Switches role to host: `echo host > /sys/class/usb_role/4e00000.usb-role-switch/role`.
  - Unbinds UDC gadget, terminating USB RNDIS network and host SSH link.
- **Restoring Gadget Mode without Full Reboot**:
  - Turn off VBUS boost: `echo disabled > /sys/bus/platform/devices/otg-vbus/state`.
  - Switch role back: `echo device > /sys/class/usb_role/4e00000.usb-role-switch/role`.
  - Re-bind UDC: `echo 4e00000.usb > /sys/kernel/config/usb_gadget/ginkgo/UDC`.
  - In `usb-gadget-rndis.sh`, `setup_gadget()` explicitly validates and re-binds `$GADGET/UDC` if directory structure already exists.

#### 6. CRLF Line Endings Trap & Boot Autoconnection Failure (status=203/EXEC)
- When shell scripts in `rootfs-overlay/usr/local/sbin/` are edited or checked out on Windows without LF enforcement, Windows CRLF line endings (`\r\n`) are introduced into the shebang line (`#!/bin/bash\r`).
- The Linux kernel shebang interpreter parses the target path as `/bin/bash\r`, which does not exist (`ENOENT`).
- Systemd reports this as `Failed at step EXEC spawning /usr/local/sbin/usb-gadget-rndis.sh: No such file or directory` with error code `status=203/EXEC`.
- When this happens, `usb-gadget-rndis.service` fails on boot, the RNDIS USB network never initializes, and Windows never detects the USB connection or plays the connection chime.
- **Prevention**: Enforce `eol=lf` across the repository via `.gitattributes` (`*.sh text eol=lf`, `*.service text eol=lf`), and run `sed -i 's/\r$//' /usr/local/sbin/*` on any newly deployed scripts.

### 1.6 Compressed RAM Swap (ZRAM, LZ4, 2GB)

#### 1. Architecture and Missing In-Tree Driver
- **Kernel Config in #142**: The baseline `#142` kernel had `# CONFIG_ZRAM is not set` and `# CONFIG_ZSMALLOC is not set`.
- **Out-of-Tree Modules**: In accordance with Rule 1.3 (never replacing the working DPU/DSI Tianma kernel with raw upstream), ZRAM support is provided via three kernel modules matching vermagic `7.0.0-00001-g62f9dac57de4-dirty`:
  - `lz4_compress.ko`: Fast compression backend for zram block compression.
  - `zsmalloc.ko`: Dynamic memory slab allocator designed specifically for compressed pages.
  - `zram.ko`: Compressed RAM block device driver with LZ4 and ZSTD backend support.
- **Symbol Resolution**: Verified against `Module.symvers` with 0 missing symbols. All required kernel symbols (`zs_create_pool`, `zs_destroy_pool`, `zs_malloc`, `zs_free`, `LZ4_compress_fast`, `zcomp_*`, etc.) are natively exported by the mainline kernel.
- **Staging Location**: Pre-built in `out/` and staged in `rootfs-overlay/lib/modules/ginkgo-extra/` and ramdisk `overlay/lib/modules/ginkgo-extra/`.

#### 2. Lifecycle & Service Management (`zram-setup.service`)
- **Unit**: `/etc/systemd/system/zram-setup.service`, ordered `Before=swap.target basic.target shutdown.target` and enabled via `basic.target.wants/zram-setup.service`.
- **Script**: `/usr/local/sbin/ginkgo-zram.sh` handles `start`, `stop`, `restart`, and `status`.
  - **Module Loading**: Checks `/sys/module/` and `/proc/modules`, tries `modprobe`, and falls back to scanning `/lib/modules/ginkgo-extra/` with `insmod` in dependency order (`lz4_compress` -> `zsmalloc` -> `zram num_devices=1`).
  - **Device Hot-Add**: Automatically queries `/sys/class/zram-control/hotadd` if `/sys/block/zram0` was not pre-instantiated.
  - **State Reset**: Issues `echo 1 > /sys/block/zram0/reset` if a previous partial initialization left the device busy.
  - **Algorithm & Size**: Selects `lz4` compression backend, dynamically targets 2 GB (50% of available RAM on 4 GB models), formats with `mkswap -L zram0 /dev/zram0`, and activates with `swapon -p 100 /dev/zram0`.
  - **Kernel VM Tuning**: Applies `vm.swappiness = 100`, `vm.page-cluster = 0` (zero readahead latency for compressed RAM), `vm.watermark_boost_factor = 0`, and `vm.vfs_cache_pressure = 50`.
  - **Teardown**: Executed on system shutdown (`swapoff /dev/zram0` and reset) to cleanly release memory pages before filesystem unmounts.

The one piece of stale config still on the device is `/etc/environment.d/99-ginkgo-gnome.conf` (`GSK_RENDERER=gl`) — a GNOME-era variable that does nothing for Plasma. It is **not** in the repo; either delete it on the phone or move the comment into a KDE-specific drop-in, but do not expect it to affect the desktop.

Spot drift between the image and the repo after any hands-on debugging session:

```sh
ssh root@192.168.7.2 'ls -1 /etc/systemd/system/*.service /etc/systemd/system/*/*.conf \
    /usr/local/sbin/* /usr/local/bin/* 2>/dev/null' | xargs -r -n1 basename | sort -u > /tmp/device-units.txt
{ cd rootfs-overlay
  ls -1 etc/systemd/system/*.service etc/systemd/system/*/*.conf \
    usr/local/sbin/* usr/local/bin/* 2>/dev/null; } | xargs -r -n1 basename | sort -u > /tmp/repo-units.txt
diff -u /tmp/repo-units.txt /tmp/device-units.txt
```

The globs are there so `ls` never prints `dirname:` headers. `>` lines are on the phone but not in the repo — commit them or delete them; `<` lines are repo work that never got flashed. Expect a few benign `>` lines for symlinks that `systemctl enable` creates for stock Debian/Ubuntu units (`ssh.service` and friends). This list does not cover `/etc/environment.d`, so check the stale GNOME drop-in above by hand.

---

## 8. Repo map

| Path | Content |
|------|---------|
| `scripts/build-all.sh` | kernel → `boot.img` → rootfs image in one go |
| `scripts/build-kernel.sh`, `setup-kernel.sh` | kernel build against `linux/` + `config/ginkgo.fragment` |
| `scripts/build-initramfs.sh` | static `/init` cpio; `initramfs/ginkgo-status.c` is the GLES boot HUD inside it |
| `scripts/build-bootimg.sh`, `make-vbmeta.sh`, `make-empty-dtbo.sh` | Android boot image v2 packing, disabled-verification vbmeta, zero dtbo |
| `scripts/flash-boot.sh`, `flash-mainline-test.sh`, `flash-linux-boot.sh` | fastboot flashing (the last one can also write the userdata rootfs) |
| `scripts/update-rootfs-via-recovery.sh` | push `rootfs-overlay/` into a running device through recovery adb |
| `scripts/build-rootfs.sh`, `configure-rootfs.sh`, `build-rootfs-image.sh` | debootstrap minbase → firmware/fstab/hostname/units → ext4 image |
| `scripts/usb-connect.sh`, `host-usb-connect.sh`, `ssh-run.sh`, `lib-ginkgo-pass.sh` | host-side link + one-shot SSH + password loading |
| `scripts/capture-uart.sh`, `capture-logs.sh`, `backup-device.sh`, `restore-android.sh`, `reboot-fastboot.sh` | debugging and escape hatches |
| `scripts/ginkgo-touch-test.sh` / `.py`, `dsi-*.py`, `dpu-*.py` | touch and DSI/DPU register probes |
| `rootfs-overlay/` | everything that lands in the image: units (incl. `bluetooth.service.d/bdaddr.conf`), scripts in `usr/local/sbin` (`ginkgo-debloat.sh`, `ginkgo-ics-inet.sh`, `bt-set-addr.sh`) and `usr/local/bin` (`ginkgo-full-performance.sh`), apt sources, NM/ssh/sysctl/udev config, `etc/environment.d/99-ginkgo-keyboard.conf` |
| `config/ginkgo.fragment` | kernel config fragment (~255 lines; battery PMI632 QG, HZ=1000, and SDHCI MSM are in) |
| `reference/downstream/dts/qcom/trinket.dtsi` | vendor DT for comparison (e.g. the WCN3990 `bt_wcn3990` node with its `pm6125_l9/l16/l17/l23` supplies) |
| `docs/` | milestone write-ups, one per date (user guides at the top level, engineering audits under `docs/audit/`) |

`scripts/configure-rootfs.sh` copies the whole overlay with `cp -a "$OVERLAY/." "$ROOTFS/"`, then `chmod 755` the `usr/local/sbin` and `usr/local/bin` helpers it expects and `systemctl enable` the units it wants. `scripts/update-rootfs-via-recovery.sh` keeps its own copy of both lists (one `chmod` line, one `ln -sf` per unit). A new overlay script needs a `chmod` line in both or it lands non-executable — this checkout has `core.fileMode=false`, so git does not carry the executable bit and the build scripts are the only thing that sets it.

---

## 9. Package-management rules on this image

Debloating is safe only with a guard, because Ubuntu's dependency graph has two traps that are invisible until you simulate:

1. **`plasma-nm` (the Wi-Fi applet) hard-depends on the Qt WebEngine libraries** — they cannot be removed while networking UI is wanted.
2. **Purging snapd's GLib binding (`libsnapd-glib-2-1`) cascades** into `gir1.2-snapd-2` → `update-manager`/`gnome-settings-daemon` → the *entire PipeWire/WirePlumber audio stack*. Purging `snapd`, the chromium snap stub, the Discover snap backend and `libsnapd-qt-2-1` is clean; `apt-mark manual` the audio set first anyway.
3. Removing **`evolution-data-server`** uninstalls **`bluedevil`**, KDE's Bluetooth settings — keep it while Bluetooth work is live.

The enforced procedure, inside `ginkgo-debloat.sh`: `apt-mark manual` the protected list → simulate each purge group (`apt-get -s purge`) → grep the removal set against a deny-list (`bluedevil|bluez|plasma-desktop|plasma-workspace|plasma-nm|kwin|sddm|network-manager|pipewire|wireplumber|plasma-pa|apparmor|gnome-settings-daemon`) → only then `apt-get purge`, and the same check before `apt-get autoremove --purge`.

Login trim is done the KDE-native way: per-user `~/.config/autostart/*.desktop` copies with `Hidden=true` (exactly what System Settings → Autostart writes), plus `enabled=false` in `~/.config/baloofilerc` for the file indexer. Nothing is edited in `/etc/xdg/autostart`, so packages keep their own files intact.

Keyboard: KWin selects `/usr/share/applications/org.kde.plasma.keyboard.desktop` as its Wayland input method. Do not globally force `QT_IM_MODULE` or `QT_IM_MODULES` to `qtvirtualkeyboard`. The confirmed appearance fix removed both assignments from the original `99-ginkgo-keyboard.conf`, then stopped SDDM, terminated the entire ginkgo user session, and started SDDM again. Empty overrides or restarting only SDDM/KWin were insufficient. The owner confirmed the resulting appearance. Older ramdisks can restore the bad file on reboot; include the corrected original file in future images. See [the keyboard fix and persistence limits](docs/audit/plasma-keyboard-fallback-fix.md).

---

## 10. Verification commands you will actually reuse

```sh
# link and boot
ssh root@192.168.7.2 'uname -a; systemctl get-default'
ssh root@192.168.7.2 'systemctl --failed --no-pager'
ssh root@192.168.7.2 'journalctl -b -p 3 --no-pager | tail -40'

# display / backlight / panel
ssh root@192.168.7.2 'cat /sys/class/drm/card0-DSI-1/status; cat /sys/class/backlight/ktd3136-backlight/{brightness,max_brightness}'

# touch: which input devices exist, then live events (evtest is NOT installed)
ssh root@192.168.7.2 'grep -H . /sys/class/input/input*/name; hexdump -C /dev/input/eventN'
ssh root@192.168.7.2 '/usr/local/sbin/ginkgo-touch-test.py'

# kernel driver binding (SPI touch, remoteproc)
ssh root@192.168.7.2 'ls -l /sys/bus/spi/devices/spi0.0/driver 2>/dev/null; cat /sys/class/remoteproc/remoteproc*/state'

# battery / thermal
ssh root@192.168.7.2 'ls /sys/class/power_supply/; for f in /sys/class/power_supply/*/uevent; do echo "== $f"; cat $f; done'

# session state, as the session user (see §6 for the env prefix)
busctl --user introspect org.kde.KWin /VirtualKeyboard
loginctl show-session <id> -p LockedHint -p Active -p Type
```

Two standing cautions: unbinding a driver over SSH can lose the session before the matching `bind` runs (reboot is the only recovery), and Wi-Fi absence cannot be diagnosed with `rfkill` or `iw` on this image — `rfkill` is not installed at all and `iw dev` prints nothing without an interface, so check `/sys/class/net`, `journalctl -b | grep ath10k` and the MPSS remoteproc state instead.
