#!/usr/bin/env python3
"""Host tests of production PMI632 functions with a fault-injecting regmap.

Run under Linux/WSL with Python 3 and a C compiler. This compiles the actual
function bodies, not a Python reimplementation. Kernel integration still needs
an arm64 module build and hardware validation.
"""
import os
from pathlib import Path
import re
import subprocess
import tempfile


def function(source, name):
    start = re.search(r"^static (?:int|void) " + name + r"\(", source, re.M).start()
    opening = source.index("{", start)
    depth = 1
    end = opening + 1
    while depth:
        depth += (source[end] == "{") - (source[end] == "}")
        end += 1
    return source[start:end]


def main():
    root = Path(__file__).resolve().parents[1]
    source = (root / "overlays/linux/drivers/power/supply/qcom-pmi632-qg.c").read_text()
    defines = "\n".join(re.findall(r"^#define .+$", source, re.M))
    names = ["qg_read16", "qg_read_present", "qg_read_voltage", "qg_read_current",
             "pmi632_read_usb", "pmi632_read_status", "qg_get_property",
             "qg_usb_get_property", "pmi632_poll_work"]
    with tempfile.TemporaryDirectory(prefix="pmi632-test-") as temp:
        test_dir = Path(temp)
        (test_dir / "production.h").write_text(
            defines + "\n" + "\n".join(function(source, name) for name in names))
        binary = test_dir / "test"
        subprocess.run([os.environ.get("CC", "cc"), "-std=gnu11", "-Wall", "-Wextra",
                        "-Werror", "-fsanitize=undefined", "-I", temp,
                        str(root / "tools/tests/pmi632-qg.c"), "-o", str(binary)], check=True)
        subprocess.run([str(binary)], check=True)


if __name__ == "__main__":
    main()
