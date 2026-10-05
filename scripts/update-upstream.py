#!/usr/bin/env python3
"""Update the pinned gallery-dl wheel and AppStream entry for a stable release."""

from datetime import datetime
import json
import os
from pathlib import Path
import re
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parent.parent
PYPI = "https://pypi.org/pypi/gallery-dl"
REQUIREMENT = re.compile(r"gallery-dl==(?P<version>\S+)")


def fetch(version=None):
    """Return PyPI's metadata for a release, or for the latest stable one."""
    url = f"{PYPI}/{quote(version)}/json" if version else f"{PYPI}/json"
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "gallery-dl-flatpak"})
    with urlopen(request, timeout=30) as response:
        return json.load(response)


def version(text):
    if not re.fullmatch(r"\d+\.\d+\.\d+", text):
        raise ValueError(f"Unsupported stable release version: {text!r}")
    return tuple(int(part) for part in text.split("."))


def dependencies(release):
    """Stop unattended updates when upstream changes its dependency declarations."""
    info = release["info"]
    return sorted(info["requires_dist"] or []), info["requires_python"]


def wheel(release):
    tag = release["info"]["version"]
    name = f"gallery_dl-{tag}-py3-none-any.whl"
    files = [entry for entry in release["urls"] if entry["filename"] == name]
    if len(files) != 1 or files[0]["yanked"]:
        raise ValueError(f"Expected one available {name} on PyPI")
    entry = files[0]
    url = urlsplit(entry["url"])
    if url.scheme != "https" or url.hostname != "files.pythonhosted.org" or not url.path.endswith(f"/{name}"):
        raise ValueError(f"Unexpected download URL for {name}: {entry['url']!r}")
    if not re.fullmatch(r"[0-9a-f]{64}", entry["digests"]["sha256"]):
        raise ValueError(f"Missing SHA-256 digest for {name}")
    return entry


def update(root, fetch=fetch):
    requirements = root / "flatpak/requirements.txt"
    module = root / "flatpak/python-packages.json"
    metadata = root / "flatpak/eu.nosini.GalleryDl.metainfo.xml"
    pins = REQUIREMENT.findall(requirements.read_text())
    if len(pins) != 1:
        raise ValueError("Expected exactly one pinned gallery-dl requirement")
    current = pins[0]
    release = fetch()
    tag = release["info"]["version"]
    if version(tag) <= version(current):
        print(f"Already packaged {current}; no newer stable release.")
        return False, current
    entry = wheel(release)
    date = datetime.fromisoformat(entry["upload_time_iso_8601"].replace("Z", "+00:00")).date().isoformat()
    if dependencies(fetch(current)) != dependencies(release):
        raise ValueError("Upstream dependency declarations changed; review them and regenerate the Python modules manually")

    packages = json.loads(module.read_text())
    sources = [s for s in packages["sources"] if s["dest-filename"].startswith("gallery_dl-")]
    command = f" gallery_dl=={current} "
    if len(sources) != 1 or len(packages["build-commands"]) != 1 or packages["build-commands"][0].count(command) != 1:
        raise ValueError("Expected exactly one pinned gallery-dl wheel in python-packages.json")
    sources[0].update({"url": entry["url"], "dest-filename": entry["filename"], "sha256": entry["digests"]["sha256"]})
    packages["build-commands"][0] = packages["build-commands"][0].replace(command, f" gallery_dl=={tag} ")

    xml = metadata.read_text()
    releases = ET.fromstring(xml).find("releases")
    if releases is None or xml.count("  <releases>\n") != 1:
        raise ValueError("Expected an AppStream releases section")
    if not any(release.get("version") == tag for release in releases):
        xml = xml.replace("  <releases>\n", f'  <releases>\n    <release version="{tag}" date="{date}"/>\n', 1)
    requirements.write_text(REQUIREMENT.sub(f"gallery-dl=={tag}", requirements.read_text()))
    module.write_text(json.dumps(packages, indent=2) + "\n")
    metadata.write_text(xml)
    print(f"Updated gallery-dl to {tag}.")
    return True, tag


def main():
    changed, tag = update(ROOT)
    if output := os.environ.get("GITHUB_OUTPUT"):
        with open(output, "a") as stream:
            stream.write(f"changed={str(changed).lower()}\ntag={tag}\n")


if __name__ == "__main__":
    main()
