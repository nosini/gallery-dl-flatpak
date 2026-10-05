#!/usr/bin/env python3
"""Test add-on catalogs through real Flatpak exports, without an SDK."""

import gzip
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def main():
    root = Path(__file__).resolve().parents[1]
    addons = json.loads((root / "flatpak/addons.json").read_text())
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        build = work / "build"
        files = build / "files"
        files.mkdir(parents=True)
        shutil.copy(root / "flatpak/addons.json", work / "addons.json")
        # The SDK step must work with Python alone, without host executables.
        env = dict(os.environ, FLATPAK_ID="eu.nosini.GalleryDl", FLATPAK_DEST=str(files),
                   PATH=str(work / "no-external-tools"))
        command = [sys.executable, str(root / "scripts/install-addon-metadata.py")]
        subprocess.run(command, cwd=work, env=env, check=True)
        repo = work / "repo"
        catalogs = {}
        for addon in addons:
            addon_id = f"eu.nosini.GalleryDl.{addon['suffix']}"
            prefix = files / "extensions" / addon["slug"]
            catalog = prefix / "share/app-info/xmls" / f"{addon_id}.xml.gz"
            catalogs[catalog] = catalog.read_bytes()
            component = ET.fromstring(gzip.decompress(catalogs[catalog])).find("component")
            assert component.findtext("id") == addon_id
            assert component.find("metadata_license") is None
            metainfo = prefix / "share/metainfo" / f"{addon_id}.metainfo.xml"
            assert ET.parse(metainfo).findtext("metadata_license") == "CC0-1.0"
            (build / f"metadata.{addon_id}").write_text(
                f"[Runtime]\nname={addon_id}\n\n[ExtensionOf]\n"
                "ref=app/eu.nosini.GalleryDl/x86_64/stable\n"
            )
            subprocess.run([
                "flatpak", "build-export", "--runtime", "--arch=x86_64",
                f"--metadata=metadata.{addon_id}", f"--files=files/extensions/{addon['slug']}",
                str(repo), str(build), "stable",
            ], check=True, stdout=subprocess.DEVNULL)
        subprocess.run(["flatpak", "build-update-repo", str(repo)],
                       check=True, stdout=subprocess.DEVNULL)
        # Catalog content is unchanged by adding signatures to app refs.
        # Flatpak would keep the unsigned catalog commit unless we reset it.
        refs_before = set(subprocess.check_output(
            ["ostree", f"--repo={repo}", "refs"], text=True,
        ).splitlines())
        catalogs_before = {ref: subprocess.check_output(
            ["ostree", f"--repo={repo}", "rev-parse", ref], text=True,
        ).strip() for ref in refs_before if ref.startswith(("appstream/", "appstream2/"))}
        assert {"appstream/x86_64", "appstream2/x86_64"} <= catalogs_before.keys()
        subprocess.run(["flatpak", "build-update-repo", str(repo)],
                       check=True, stdout=subprocess.DEVNULL)
        for ref, commit in catalogs_before.items():
            assert subprocess.check_output(
                ["ostree", f"--repo={repo}", "rev-parse", ref], text=True,
            ).strip() == commit, "Expected an unchanged catalog to reuse its commit"
        subprocess.run(["bash", str(root / "scripts/reset-appstream-refs.sh"), str(repo)], check=True)
        refs_after = set(subprocess.check_output(
            ["ostree", f"--repo={repo}", "refs"], text=True,
        ).splitlines())
        assert refs_after == refs_before - catalogs_before.keys(), "Catalog reset changed package refs"
        subprocess.run(["flatpak", "build-update-repo", str(repo)],
                       check=True, stdout=subprocess.DEVNULL)
        for ref in catalogs_before:
            parent = subprocess.check_output([
                "ostree", f"--repo={repo}", "show", "--raw", ref,
            ], text=True)
            assert ", @ay []," in parent, "Regenerated catalog must have no previous commit"
        published = subprocess.check_output([
            "ostree", f"--repo={repo}", "cat", "appstream/x86_64", "/appstream.xml.gz",
        ])
        catalog = ET.fromstring(gzip.decompress(published))
        components = {c.findtext("id"): c for c in catalog.findall("component")}
        assert len(components) == len(addons)
        for addon in addons:
            addon_id = f"eu.nosini.GalleryDl.{addon['suffix']}"
            component = components[addon_id]
            assert component.get("type") == "addon"
            assert component.findtext("extends") == "eu.nosini.GalleryDl"
            assert component.findtext("bundle[@type='flatpak']") == f"runtime/{addon_id}/x86_64/stable"
        subprocess.run(command, cwd=work, env=env, check=True)
        assert all(path.read_bytes() == data for path, data in catalogs.items()), "Catalogs aren't reproducible"
        print(f"All {len(addons)} add-on catalogs generated without external tools and exported successfully.")


if __name__ == "__main__":
    main()
