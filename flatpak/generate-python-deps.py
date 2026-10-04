#!/usr/bin/env python3
"""Resolve pinned wheels for Freedesktop 26.08, using Python 3.14 and pip."""

import json
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

HERE = Path(__file__).resolve().parent


def main():
    # pip evaluates dependency environment markers against the running Python.
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Run this script with Python 3.14 (the Flatpak runtime version).")
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        subprocess.run([
            sys.executable, "-m", "pip", "install", "--dry-run",
            "--ignore-installed", "--only-binary=:all:",
            "--implementation=cp", "--python-version=3.14",
            "--platform=manylinux_2_34_x86_64",
            "--platform=manylinux_2_28_x86_64",
            "--platform=manylinux2014_x86_64",
            "--index-url=https://pypi.org/simple",
            "--target", str(Path(tmp) / "target"),
            "--report", str(report), "-r", str(HERE / "requirements.txt"),
        ], check=True)
        packages = json.loads(report.read_text())["install"]

    sources = []
    requirements = []
    for package in sorted(packages, key=lambda p: p["metadata"]["name"].lower()):
        download = package["download_info"]
        name = unquote(urlsplit(download["url"]).path.rsplit("/", 1)[1])
        sources.append({
            "type": "file", "url": download["url"], "dest-filename": name,
            "sha256": download["archive_info"]["hashes"]["sha256"],
        })
        meta = package["metadata"]
        requirements.append(shlex.quote(f"{meta['name']}=={meta['version']}"))
    module = {
        "name": "python-packages",
        "buildsystem": "simple",
        "build-commands": [
            'pip3 install --no-index --find-links="${PWD}" --only-binary=:all:'
            ' --no-deps --ignore-installed --prefix="${FLATPAK_DEST}" '
            + " ".join(requirements),
        ],
        "sources": sources,
    }
    (HERE / "python-packages.json").write_text(json.dumps(module, indent=2) + "\n")


if __name__ == "__main__":
    main()
