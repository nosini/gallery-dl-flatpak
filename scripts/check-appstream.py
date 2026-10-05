#!/usr/bin/env python3
"""Check the exported catalog consumed by software centers."""

import gzip
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def main():
    catalog_dir = Path(sys.argv[1])
    compressed = catalog_dir / "appstream.xml.gz"
    if compressed.exists():
        with gzip.open(compressed, "rb") as stream:
            catalog = ET.parse(stream)
    else:
        catalog = ET.parse(catalog_dir / "appstream.xml")

    components = {c.findtext("id"): c for c in catalog.findall("component")}
    app = components["eu.nosini.GalleryDl"]
    assert app.get("type") == "desktop-application", "GNOME Software hides console apps"
    assert app.findtext("launchable[@type='desktop-id']") == "eu.nosini.GalleryDl.desktop"
    assert app.find("icon") is not None, "App icon is missing from the catalog"
    assert app.findtext("bundle[@type='flatpak']") == "app/eu.nosini.GalleryDl/x86_64/stable"

    addons = json.loads((Path(__file__).resolve().parents[1] / "flatpak/addons.json").read_text())
    for entry in addons:
        addon_id = f"eu.nosini.GalleryDl.{entry['suffix']}"
        addon = components[addon_id]
        assert addon.get("type") == "addon", f"{addon_id} must be an add-on"
        assert addon.findtext("extends") == "eu.nosini.GalleryDl", f"{addon_id}: parent is missing"
        assert addon.findtext("bundle[@type='flatpak']") == f"runtime/{addon_id}/x86_64/stable"
    print(f"Published app and all {len(addons)} add-on catalog relationships passed.")


if __name__ == "__main__":
    main()
