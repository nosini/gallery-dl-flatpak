#!/usr/bin/env python3
"""Check the exported catalog consumed by software centers.

Usage: check-appstream.py CATALOG [ARCH]

CATALOG is an appstream.xml or appstream.xml.gz file, or a directory with
one, such as Flatpak's appstream/REMOTE/ARCH/active. ARCH defaults to x86_64.
"""

import gzip
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

APP_ID = "eu.nosini.GalleryDl"
BRANCH = "stable"


def load(path):
    if path.is_dir():
        path = next(p for p in (path / "appstream.xml.gz", path / "appstream.xml") if p.exists())
    if path.suffix == ".gz":
        with gzip.open(path, "rb") as stream:
            return ET.parse(stream)
    return ET.parse(path)


def main():
    catalog = load(Path(sys.argv[1]))
    arch = sys.argv[2] if len(sys.argv) > 2 else "x86_64"

    components = {c.findtext("id"): c for c in catalog.findall("component")}
    app = components[APP_ID]
    assert app.get("type") == "desktop-application", "GNOME Software hides console apps"
    assert app.findtext("launchable[@type='desktop-id']") == f"{APP_ID}.desktop"
    assert app.find("icon") is not None, "App icon is missing from the catalog"
    assert app.findtext("bundle[@type='flatpak']") == f"app/{APP_ID}/{arch}/{BRANCH}"

    addons = json.loads((Path(__file__).resolve().parents[1] / "addons/addons.json").read_text())
    for entry in addons:
        addon_id = f"{APP_ID}.{entry['suffix']}"
        addon = components[addon_id]
        assert addon.get("type") == "addon", f"{addon_id} must be an add-on"
        assert addon.findtext("extends") == APP_ID, f"{addon_id}: parent is missing"
        assert addon.findtext("bundle[@type='flatpak']") == f"runtime/{addon_id}/{arch}/{BRANCH}"
    print(f"The app and all {len(addons)} add-ons are in the {arch} catalog.")


if __name__ == "__main__":
    main()
