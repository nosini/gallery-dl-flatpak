#!/usr/bin/env python3
"""Copy mkvmerge and its library closure from the official extracted AppImage."""

from pathlib import Path
import re
import shutil
import subprocess
import sys


def main():
    source = Path(sys.argv[1]) / "usr"
    prefix = Path(sys.argv[2])
    lib = prefix / "lib"
    lib.mkdir(parents=True, exist_ok=True)
    binary = prefix / "libexec/mkvmerge"
    binary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source / "bin/mkvmerge", binary)
    queue = [source / "bin/mkvmerge"]
    copied = set()
    # Basic platform libraries are provided by the Freedesktop runtime.
    platform_libraries = {
        "libc.so.6", "libm.so.6", "libpthread.so.0", "libdl.so.2", "librt.so.1",
        "libgcc_s.so.1", "libstdc++.so.6", "ld-linux-x86-64.so.2", "libz.so.1", "libgmp.so.10",
    }
    while queue:
        current = queue.pop()
        dynamic = subprocess.check_output(["readelf", "-d", str(current)], text=True)
        for name in re.findall(r"\(NEEDED\).*\[([^]]+)\]", dynamic):
            if name in copied or name in platform_libraries:
                continue
            if Path(name).name != name:
                raise RuntimeError(f"Unexpected library path: {name}")
            original = source / "lib" / name
            if not original.is_file():
                raise RuntimeError(f"Missing bundled dependency: {name}")
            shutil.copy2(original, lib / name)
            copied.add(name)
            queue.append(original)
    wrapper = prefix / "bin/mkvmerge"
    wrapper.parent.mkdir(parents=True, exist_ok=True)
    wrapper.write_text(
        '#!/bin/sh\n'
        'prefix=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)\n'
        'export LD_LIBRARY_PATH="$prefix/lib${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"\n'
        'exec "$prefix/libexec/mkvmerge" "$@"\n'
    )
    wrapper.chmod(0o755)


if __name__ == "__main__":
    main()
