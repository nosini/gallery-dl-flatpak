#!/usr/bin/env python3
"""Install metainfo and Flatpak catalogs for the optional extensions."""

import copy
import gzip
import json
import os
from pathlib import Path
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
        paragraphs = addon.get("description", [addon["summary"] + ". This optional add-on is for gallery-dl."])
        for paragraph in paragraphs:
            ET.SubElement(description, "p").text = paragraph
        ET.SubElement(component, "url", type="homepage").text = addon["homepage"]
        developer = ET.SubElement(component, "developer", id=addon["developer"]["id"])
        ET.SubElement(developer, "name").text = addon["developer"]["name"]
        metadata = prefix / "share/metainfo" / f"{addon_id}.metainfo.xml"
        metadata.parent.mkdir(parents=True, exist_ok=True)
        ET.indent(component)
        ET.ElementTree(component).write(metadata, encoding="utf-8", xml_declaration=True)
        # These text-only add-ons need no icon or desktop-file processing.
        # appstreamcli is a builder-host tool, not part of the SDK sandbox.
        # Write their catalog XML directly; Flatpak attaches the exported ref
        # when it merges this file into the repository's AppStream catalog.
        catalog = ET.Element("components", version="1.0", origin=addon_id)
        entry = copy.deepcopy(component)
        entry.remove(entry.find("metadata_license"))  # metainfo-only field
        catalog.append(entry)
        ET.indent(catalog)
        data = ET.tostring(catalog, encoding="utf-8", xml_declaration=True)
        catalog_dir = prefix / "share/app-info/xmls"
        catalog_dir.mkdir(parents=True, exist_ok=True)
        (catalog_dir / f"{addon_id}.xml.gz").write_bytes(gzip.compress(data, mtime=0))


if __name__ == "__main__":
    main()
