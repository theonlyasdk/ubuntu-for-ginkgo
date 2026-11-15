#!/usr/bin/env python3
"""Repack the recovery image with verified, targeted ramdisk replacements."""
import gzip
import argparse
import hashlib
from pathlib import Path
import subprocess
import tempfile

OUT = Path(__file__).resolve().parents[1] / "out"
TARGET = b"overlay/lib/modules/ginkgo-extra/qcom-pmi632-qg.ko"
UNIT = b"overlay/etc/systemd/system/ginkgo-audio.service"
KEYBOARD = b"overlay/etc/environment.d/99-ginkgo-keyboard.conf"
SAFE_UNIT = b"[Unit]\nDescription=Experimental audio disabled for recovery\n[Service]\nType=oneshot\nExecStart=/bin/true\nRemainAfterExit=yes\n"


def entries(archive):
    offset = 0
    while True:
        start = offset
        header = archive[offset:offset + 110]
        assert header[:6] in (b"070701", b"070702"), (offset, header[:6])
        fields = [int(header[i:i + 8], 16) for i in range(6, 110, 8)]
        size, namesize = fields[6], fields[11]
        name = archive[offset + 110:offset + 110 + namesize - 1]
        data_start = (offset + 110 + namesize + 3) & ~3
        end = (data_start + size + 3) & ~3
        yield name, header, archive[data_start:data_start + size], archive[start:end]
        offset = end
        if name == b"TRAILER!!!":
            break


parser = argparse.ArgumentParser()
parser.add_argument('--base', type=Path, default=OUT / 'boot-before-qg-monitor.img')
parser.add_argument('--keyboard-config', type=Path)
parser.add_argument('--module', type=Path, default=OUT / 'qg-rollback/qcom-pmi632-qg.ko')
parser.add_argument('--output', type=Path, default=OUT / 'boot-audio-recovery.img')
options = parser.parse_args()
module = options.module.read_bytes()
replacements = {TARGET: module, UNIT: SAFE_UNIT}
if options.keyboard_config:
    keyboard = options.keyboard_config.read_bytes()
    assert b'QT_IM_MODULE=' not in keyboard and b'QT_IM_MODULES=' not in keyboard
    replacements[KEYBOARD] = keyboard
with tempfile.TemporaryDirectory(prefix="ginkgo-qg-pack-") as temp:
    work = Path(temp)
    args = subprocess.check_output([
        "unpack_bootimg", "--boot_img", str(options.base),
        "--out", str(work / "original"), "--format", "mkbootimg", "-0",
    ]).decode().rstrip("\0").split("\0")
    original = work / "original"
    archive = gzip.decompress((original / "ramdisk").read_bytes())
    before = list(entries(archive))
    for target in replacements:
        assert sum(name.removeprefix(b"./") == target for name, *_ in before) == 1
    rebuilt = bytearray()
    for name, header, data, raw in before:
        if name.removeprefix(b"./") not in replacements:
            rebuilt.extend(raw)
            continue
        replacement = replacements[name.removeprefix(b"./")]
        updated_header = bytearray(header)
        updated_header[54:62] = f"{len(replacement):08x}".encode()
        if header[:6] == b"070702":
            updated_header[102:110] = f"{sum(replacement) & 0xffffffff:08x}".encode()
        rebuilt.extend(updated_header)
        rebuilt.extend(name + b"\0")
        rebuilt.extend(b"\0" * (-len(rebuilt) % 4))
        rebuilt.extend(replacement)
        rebuilt.extend(b"\0" * (-len(rebuilt) % 4))
    rebuilt.extend(b"\0" * (-len(rebuilt) % 512))
    after = list(entries(rebuilt))
    assert len(before) == len(after)
    for old, new in zip(before, after):
        assert old[0] == new[0]
        if old[0].removeprefix(b"./") in replacements:
            assert new[2] == replacements[old[0].removeprefix(b"./")]
        else:
            assert old == new, old[0]
    (original / "ramdisk").write_bytes(gzip.compress(rebuilt, mtime=0))
    subprocess.run(["fdtput", "-t", "s", str(original / "dtb"),
                    "/soc@0/remoteproc@ab00000", "status", "disabled"], check=True)
    image = options.output
    subprocess.run(["mkbootimg", *args, "-o", str(image)], check=True)
    subprocess.run([
        "unpack_bootimg", "--boot_img", str(image), "--out", str(work / "verify"),
    ], check=True, stdout=subprocess.DEVNULL)
    verify = work / "verify"
    for path in original.iterdir():
        assert path.read_bytes() == (verify / path.name).read_bytes(), path.name
    verify_args = subprocess.check_output([
        "unpack_bootimg", "--boot_img", str(image), "--out", str(original),
        "--format", "mkbootimg", "-0",
    ]).decode().rstrip("\0").split("\0")
    assert args == verify_args
    changed = [old[0].decode() for old, new in zip(before, after) if old != new]
    print(f"Verified {len(before)} ramdisk entries; changed: {changed}")
    print("Kernel and boot arguments preserved; ADSP disabled in DTB.")
    print(f"Image: {image} ({image.stat().st_size} bytes)")
    print(f"SHA256: {hashlib.sha256(image.read_bytes()).hexdigest()}")
