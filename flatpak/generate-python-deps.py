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


def resolve(requirements, constraints=None):
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        command = [
            sys.executable, "-m", "pip", "install", "--dry-run",
            "--ignore-installed", "--only-binary=:all:",
            "--implementation=cp", "--python-version=3.14",
            "--platform=manylinux_2_34_x86_64",
            "--platform=manylinux_2_28_x86_64",
            "--platform=manylinux2014_x86_64",
            "--index-url=https://pypi.org/simple",
            "--target", str(Path(tmp) / "target"),
            "--report", str(report), "-r", str(requirements),
        ]
        if constraints:
            constraint_file = Path(tmp) / "constraints.txt"
            constraint_file.write_text("\n".join(
                f"{p['metadata']['name']}=={p['metadata']['version']}"
                for p in constraints
            ) + "\n")
            command += ["--constraint", str(constraint_file)]
        subprocess.run(command, check=True)
        return json.loads(report.read_text())["install"]


def write_module(packages, name, prefix):
    sources = []
    requirements = []
    for package in sorted(packages, key=lambda p: p["metadata"]["name"].lower()):
        download = package["download_info"]
        filename = unquote(urlsplit(download["url"]).path.rsplit("/", 1)[1])
        sources.append({
            "type": "file", "url": download["url"], "dest-filename": filename,
            "sha256": download["archive_info"]["hashes"]["sha256"],
        })
        meta = package["metadata"]
        requirements.append(shlex.quote(f"{meta['name']}=={meta['version']}"))
    module = {
        "name": name,
        "buildsystem": "simple",
        "build-commands": [
            'pip3 install --no-index --find-links="${PWD}" --only-binary=:all:'
            f' --no-deps --ignore-installed --prefix="{prefix}" '
            + " ".join(requirements),
        ],
        "sources": sources,
    }
    (HERE / f"{name}.json").write_text(json.dumps(module, indent=2) + "\n")


def canonical_name(package):
    return package["metadata"]["name"].lower().replace("_", "-").replace(".", "-")


def main():
    # pip evaluates dependency environment markers against the running Python.
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Run this script with Python 3.14 (the Flatpak runtime version).")
    base = resolve(HERE / "requirements.txt")
    addon = resolve(HERE / "yt-dlp-requirements.txt", constraints=base)
    base_names = {canonical_name(package) for package in base}
    # Shared dependencies (Requests, certificates, SOCKS) come from the app.
    addon = [package for package in addon if canonical_name(package) not in base_names]
    write_module(base, "python-packages", "${FLATPAK_DEST}")
    write_module(addon, "yt-dlp-packages", "${FLATPAK_DEST}/extensions/yt-dlp")


if __name__ == "__main__":
    main()
