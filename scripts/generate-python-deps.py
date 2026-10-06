#!/usr/bin/env python3
"""Pin the Python packages of the app and its add-ons as Flatpak modules.

Writes python3-requirements.json from requirements.txt and
addons/python3-<slug>.json from the requirements in addons/addons.json. Each
module installs PyPI wheels for Freedesktop 26.08 (Python 3.14, x86_64),
pinned by URL and SHA-256. Noarch wheels get x-checker-data, so the update
workflow can follow them between regenerations.
"""

import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
MAIN_PACKAGE = "gallery-dl"


def resolve(requirements, constraints=None):
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "report.json"
        requirement_file = Path(tmp) / "requirements.txt"
        requirement_file.write_text("\n".join(requirements) + "\n")
        command = [
            sys.executable, "-m", "pip", "install", "--dry-run",
            "--ignore-installed", "--only-binary=:all:",
            "--implementation=cp", "--python-version=3.14",
            "--platform=manylinux_2_34_x86_64",
            "--platform=manylinux_2_28_x86_64",
            "--platform=manylinux2014_x86_64",
            "--index-url=https://pypi.org/simple",
            "--target", str(Path(tmp) / "target"),
            "--report", str(report), "-r", str(requirement_file),
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


def canonical_name(package):
    return re.sub(r"[-_.]+", "-", package["metadata"]["name"]).lower()


def write_module(packages, path, name, prefix):
    sources = []
    for package in sorted(packages, key=canonical_name):
        url = package["download_info"]["url"]
        source = {
            "type": "file",
            "url": url,
            "sha256": package["download_info"]["archive_info"]["hashes"]["sha256"],
        }
        # flatpak-builder names the download after the URL, and pip reads the
        # version from the file name. Without a dest-filename, the update
        # checker's new URL brings the matching name along.
        filename = urlsplit(url).path.rsplit("/", 1)[1]
        if unquote(filename) != filename:
            source["dest-filename"] = unquote(filename)
        if filename.endswith("-none-any.whl"):
            source["x-checker-data"] = {
                "type": "pypi",
                "name": canonical_name(package),
                "packagetype": "bdist_wheel",
            }
            if canonical_name(package) == MAIN_PACKAGE:
                source["x-checker-data"]["is-main-source"] = True
        sources.append(source)
    # Each name has exactly one wheel in the module's directory, so the
    # command doesn't repeat the versions.
    names = " ".join(canonical_name(p) for p in sorted(packages, key=canonical_name))
    module = {
        "name": name,
        "buildsystem": "simple",
        "build-commands": [
            'pip3 install --no-index --find-links="${PWD}" --only-binary=:all:'
            f' --no-deps --ignore-installed --prefix="{prefix}" {names}',
        ],
        "sources": sources,
    }
    path.write_text(json.dumps(module, indent=2) + "\n")
    print(f"Wrote {path.relative_to(ROOT)}")


def requirement_lines(path):
    lines = (line.split("#", 1)[0].strip() for line in path.read_text().splitlines())
    return [line for line in lines if line]


def main():
    # pip evaluates dependency environment markers against the running Python.
    if sys.version_info[:2] != (3, 14):
        raise SystemExit("Run this script with Python 3.14 (the Flatpak runtime version).")
    base_requirements = requirement_lines(ROOT / "requirements.txt")
    addons = json.loads((ROOT / "addons/addons.json").read_text())
    base = resolve(base_requirements)
    # Resolve together first so independently installed add-ons use compatible
    # versions of overlapping dependencies (for example Brotli and cffi).
    combined = resolve(
        base_requirements + [req for addon in addons for req in addon["requirements"]],
        constraints=base,
    )
    base_names = {canonical_name(package) for package in base}
    write_module(base, ROOT / "python3-requirements.json", "python3-requirements", "${FLATPAK_DEST}")
    for addon in addons:
        if not addon["requirements"]:
            continue
        packages = resolve(addon["requirements"], constraints=combined)
        # Each add-on includes its dependencies except those already required
        # by gallery-dl itself, so every add-on works when installed alone.
        packages = [p for p in packages if canonical_name(p) not in base_names]
        slug = addon["slug"]
        write_module(packages, ROOT / f"addons/python3-{slug}.json", f"python3-{slug}",
                     f"${{FLATPAK_DEST}}/extensions/{slug}")


if __name__ == "__main__":
    main()
