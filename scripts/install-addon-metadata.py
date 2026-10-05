#!/usr/bin/env python3
"""Install and compose metadata for all optional extensions in the build."""

import json
import os
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET


def main():
    addons = json.loads(Path("addons.json").read_text())
    app_id = os.environ["FLATPAK_ID"]
    for addon in addons:
        addon_id = f"{app_id}.{addon['suffix']}"
        prefix = Path(os.environ["FLATPAK_DEST"]) / "extensions" / addon["slug"]
        component = ET.Element("component", type="addon")
        for tag, value in [
            ("id", addon_id), ("extends", app_id), ("metadata_license", "CC0-1.0"),
            ("project_license", addon["license"]), ("name", addon["name"]), ("summary", addon["summary"]),
        ]:
            ET.SubElement(component, tag).text = value
        description = ET.SubElement(component, "description")
        ET.SubElement(description, "p").text = addon["summary"] + ". This optional add-on is for gallery-dl."
        ET.SubElement(component, "url", type="homepage").text = addon["homepage"]
        ET.SubElement(ET.SubElement(component, "developer", id="eu.nosini"), "name").text = "nosini"
        metadata = prefix / "share/metainfo" / f"{addon_id}.metainfo.xml"
        metadata.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(component)
        ET.ElementTree(component).write(metadata, encoding="utf-8", xml_declaration=True)
        subprocess.run([
            "appstreamcli", "compose", f"--components={addon_id}", "--prefix=/", f"--origin={addon_id}",
            f"--result-root={prefix}", f"--data-dir={prefix}/share/app-info/xmls", str(prefix),
        ], check=True)


if __name__ == "__main__":
    main()
