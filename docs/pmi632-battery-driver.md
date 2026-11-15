# PMI632 battery telemetry driver

**Deployment update:** the experimental module has been rolled back using
`out/boot-qg-rollback.img`. The phone now runs the repository's earlier driver;
post-boot capacity is 74%, and `qcom-usb` is absent. Staging module slots contain
the rollback, while the source described below remains experimental. Unplug
behavior has not yet been verified after rollback.

**Regression status:** the owner reports that the deployed rewrite still
freezes on USB unplug; the earlier driver reported a percentage and allowed
unplugging. This implementation is experimental and is not validated as a
replacement. `out/boot-qg-rollback.img` has been prepared from the repository's
pre-charging-detection driver, pending physical recovery and installation.

`overlays/linux/drivers/power/supply/qcom-pmi632-qg.c` implements battery
telemetry and charger-state reporting for ginkgo. It uses the PMIC's existing
configuration; it does not program charging limits, JEITA/thermal policy,
USB negotiation, or the full Qualcomm fuel-gauge algorithm.

## Interface

| Supply/property | Source and behavior |
| --- | --- |
| `qcom-battery/present` | QG status `base + 0x08`, bit 0; gauge-ready bit 7 is not battery presence. |
| `qcom-battery/voltage_now` | QG last voltage ADC `base + 0xc0`, little endian, 194.637 microvolts/count. Empty or invalid samples return `ENODATA`. |
| `qcom-battery/current_now` | QG last burst average `base + 0xc6`, signed 16-bit; subtype selects 152.588 or 305.176 microamps/count. Positive means charging. Zero is a valid sample. |
| `qcom-battery/status` | USB input state and charger status `0x1006`; no voltage/current read is needed. |
| `qcom-battery/capacity` | Returns `ENODATA` by default; see the capacity limitation below. |
| `qcom-usb/present` | USBIN real-time status `0x1310`, bit 4. |
| `qcom-usb/online` | USB present **and** power-path status `0x110b` selects USB input (bit 4) with valid input power (bit 0). Presence alone does not imply online. |
| `qcom-usb/usb_type` | `Unknown`: this monitor does not perform charger detection. |

USB current/voltage limits are not advertised because this driver does not
measure or negotiate them. The previous hardcoded 3 A/5 V values were not
evidence of the connected source's capability.

Charger states follow the device's downstream SMB5 definitions:

| Raw state | Meaning | Battery status with online USB |
| --- | --- | --- |
| 0 | Inhibit | Full |
| 1 | Trickle | Charging |
| 2 | Precharge | Charging |
| 3 | Full-on | Charging |
| 4 | Taper | Charging |
| 5 | Terminate | Full |
| 6 | Pause | Not charging |
| 7 | Disabled | Not charging |

With no USB present, status is Discharging. With USB present but input power
offline, states 0/5 remain Full, matching downstream reporting; other states
report Discharging. Register errors are returned to the caller instead of being
translated into a fictitious disconnect or charging state.

## Synchronization and lifetime

A mutex serializes property accesses and polling. Only a current query uses
the documented burst-average HOLD/read/release sequence. It attempts release
on every failure path and reports release errors; it does not substitute
unrelated FIFO entries or undocumented register `0x82` for the current sample.
Status, presence, voltage, and capacity queries do not touch the HOLD bit.

The poller checks USB/charger state and battery presence every two seconds.
State transitions notify the affected supplies. Every 30 seconds it also
notifies battery consumers to refresh telemetry; the power-supply core may
then read the advertised properties to build a uevent. The fast poll itself
does not sample voltage or current. Failed polls preserve the previous
notification state so failed reads do not manufacture transitions.

Notifications happen outside the mutex. Work uses the freezable workqueue;
suspend cancels polling, resume requests an immediate refresh, and shutdown
and managed teardown cancel work before either supply is unregistered.

## Capacity limitation

The downstream `qg_write_monotonic_soc()` **writes** `0xbf` as
`percentage * 255 / 100`. It is neither an autonomous hardware SOC estimate
nor an integer percentage register. Reusing a bootloader/vendor value without
the algorithm that maintains it gives stale, incorrectly scaled readings.

The previous linear 3.4–4.35 V estimate remains available only as an explicit
module option:

```sh
insmod qcom-pmi632-qg.ko estimate_capacity=1
```

This is an approximation from terminal voltage, affected by load and charging.
By default capacity is unavailable, so the desktop may show an unknown battery
percentage. Accurate SOC requires battery identification, the appropriate
4000 mAh profile, temperature and load compensation, and the QG SOC algorithm.
This implementation does not claim those features.

## Validation and artifact

Run the host tests with Linux/WSL Python 3 and a C compiler:

```sh
python3 tools/test-pmi632-qg.py
```

The test runner compiles production function bodies against a fault-injecting
regmap shim. It covers all eight charger states, offline input, failed reads,
both current ranges and signed boundaries, zero current, HOLD cleanup,
property independence, unavailable capacity, and poll notifications. It does
not simulate real PMIC timing or kernel suspend/teardown execution.

On November 15, 2026: 58 host cases passed with undefined-behavior sanitization;
kernel checkpatch reported zero warnings/errors; arm64 compilation with `W=1`
passed. The candidate is `out/qg-monitor/qcom-pmi632-qg.ko`, with vermagic
`7.0.0-00001-g62f9dac57de4-dirty SMP preempt mod_unload aarch64`.

The configured build tree lacks the deployed kernel's `Module.symvers`, so
modpost required `KBUILD_MODPOST_WARN=1`. All 28 resulting module imports were
separately checked against `__ksymtab_*` entries in the running kernel with
zero missing exports. The deployed configuration has `CONFIG_MODVERSIONS`
disabled. These checks do not replace runtime validation.

At the owner's request, the candidate was flashed on November 15, 2026 as
`out/boot-qg-monitor.img`. It was repacked from a backup of the actual boot
partition, replacing only the QG module among 229 ramdisk entries. Kernel,
DTB, boot arguments, and all other ramdisk entries were preserved. The original
64 MiB partition backup is `out/boot-before-qg-monitor.img`.

Post-boot SSH confirmed the #142 kernel, the new telemetry-monitor probe
message, and a deployed module SHA256 matching the build:
`6f2a7855e221bb8f00316b686f2a315a7134feeb3c2fe9c11d481e2bef38618a`.
SDDM and the battery service were active; USB was present/online and the battery
reported Charging, approximately 4.197 V and +237 mA. The module was also staged
in the repository rootfs overlay, initramfs staging area, and `out/` module slot.

`estimate_capacity` remains disabled. UPower currently displays the unavailable
percentage as **0%**, despite no capacity being reported by the kernel; that is
not a measurement of an empty battery. Its plugged-in warning level was None.
The freeze remains unverified; this deployment does not establish that it is
resolved. Keep the deployed #142 core kernel.

## Register references

The implementation follows Xiaomi's device-specific downstream sources:

- [QG register definitions](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/ginkgo-p-oss/drivers/power/supply/qcom/qg-reg.h)
- [QG sampling, conversion, and software SOC storage](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/ginkgo-p-oss/drivers/power/supply/qcom/qg-util.c)
- [SMB5 charger registers](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/ginkgo-p-oss/drivers/power/supply/qcom/smb5-reg.h)
- [SMB5 status and USB online reporting](https://github.com/MiCode/Xiaomi_Kernel_OpenSource/blob/ginkgo-p-oss/drivers/power/supply/qcom/smb5-lib.c)
