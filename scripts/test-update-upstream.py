#!/usr/bin/env python3
"""Exercise release updates against canned PyPI metadata."""

import copy
import importlib.util
import json
from pathlib import Path
import shutil
import tempfile
import unittest
import xml.etree.ElementTree as ET

SPEC = importlib.util.spec_from_file_location("update_upstream", Path(__file__).with_name("update-upstream.py"))
updater = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(updater)

FILES = ("requirements.txt", "python-packages.json", "eu.nosini.GalleryDl.metainfo.xml")
REQUIRES = ["requests>=2.11.0", 'yt-dlp; extra == "video"']


def pypi(version, sha256="a" * 64, requires=REQUIRES, requires_python=">=3.8"):
    name = f"gallery_dl-{version}-py3-none-any.whl"
    return {
        "info": {"version": version, "requires_dist": list(requires), "requires_python": requires_python},
        "urls": [
            {"filename": name, "yanked": False, "upload_time_iso_8601": "2026-10-05T12:34:56.789Z",
             "url": f"https://files.pythonhosted.org/packages/00/11/{sha256}/{name}",
             "digests": {"sha256": sha256}},
            {"filename": f"gallery_dl-{version}.tar.gz", "yanked": False, "upload_time_iso_8601": "2026-10-05T12:35:00Z",
             "url": f"https://files.pythonhosted.org/packages/00/11/{sha256}/gallery_dl-{version}.tar.gz",
             "digests": {"sha256": "b" * 64}},
        ],
    }


class UpdateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        flatpak = self.root / "flatpak"
        flatpak.mkdir()
        # Use the real files to also check that unrelated content survives.
        for name in FILES:
            shutil.copy(updater.ROOT / "flatpak" / name, flatpak / name)
        self.current = updater.REQUIREMENT.search((flatpak / "requirements.txt").read_text())["version"]
        major, minor, patch = updater.version(self.current)
        self.new = f"{major}.{minor}.{patch + 1}"
        self.before = self.read()
        self.releases = {None: pypi(self.new, "c" * 64), self.current: pypi(self.current)}

    def read(self):
        return {name: (self.root / "flatpak" / name).read_text() for name in FILES}

    def fetch(self, version=None):
        return copy.deepcopy(self.releases[version])

    def update(self):
        return updater.update(self.root, self.fetch)

    def assert_unchanged(self):
        self.assertEqual(self.before, self.read())

    def test_no_update_for_same_or_older_release(self):
        older = ".".join(map(str, updater.version(self.current)[:2])) + ".0"
        for version in (self.current, older):
            with self.subTest(version=version):
                # The pinned release's dependencies don't need to be fetched.
                self.releases = {None: pypi(version)}
                self.assertEqual(self.update(), (False, self.current))
                self.assert_unchanged()

    def test_wheel_pin_and_release_history_are_updated(self):
        self.assertEqual(self.update(), (True, self.new))
        after = self.read()
        self.assertEqual(after["requirements.txt"], self.before["requirements.txt"].replace(self.current, self.new))
        module, original = json.loads(after["python-packages.json"]), json.loads(self.before["python-packages.json"])
        changed = [(old, new) for old, new in zip(original["sources"], module["sources"]) if old != new]
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0][1], {
            "type": "file", "url": self.fetch()["urls"][0]["url"],
            "dest-filename": f"gallery_dl-{self.new}-py3-none-any.whl", "sha256": "c" * 64,
        })
        self.assertEqual(module["build-commands"], [original["build-commands"][0].replace(
            f"gallery_dl=={self.current} ", f"gallery_dl=={self.new} ")])
        self.assertEqual(after["python-packages.json"], json.dumps(module, indent=2) + "\n")
        releases = ET.parse(self.root / "flatpak/eu.nosini.GalleryDl.metainfo.xml").findall("releases/release")
        self.assertEqual([release.get("version") for release in releases][:2], [self.new, self.current])
        self.assertEqual(releases[0].get("date"), "2026-10-05")
        # The second check must be a no-op, with no duplicate release entry.
        self.assertEqual(self.update(), (False, self.new))
        self.assertEqual(after, self.read())

    def test_dependency_changes_stop_without_editing_packaging(self):
        for change in ({"requires": REQUIRES + ["new-dependency"]}, {"requires": ["requests>=2.32"]},
                       {"requires_python": ">=3.10"}):
            with self.subTest(change=change):
                self.releases[None] = pypi(self.new, **change)
                with self.assertRaisesRegex(ValueError, "declarations changed"):
                    self.update()
                self.assert_unchanged()

    def test_dependency_order_does_not_block_the_update(self):
        self.releases[None] = pypi(self.new, requires=reversed(REQUIRES))
        self.assertTrue(self.update()[0])

    def test_unusable_releases_are_rejected(self):
        def yanked(release):
            release["urls"][0]["yanked"] = True

        def missing_wheel(release):
            del release["urls"][0]

        def foreign_host(release):
            release["urls"][0]["url"] = release["urls"][0]["url"].replace("files.pythonhosted.org", "example.org")

        def missing_digest(release):
            release["urls"][0]["digests"]["sha256"] = ""

        def invalid_date(release):
            release["urls"][0]["upload_time_iso_8601"] = "invalid"

        for change in (yanked, missing_wheel, foreign_host, missing_digest, invalid_date):
            with self.subTest(change=change.__name__):
                release = pypi(self.new)
                change(release)
                self.releases[None] = release
                with self.assertRaises(ValueError):
                    self.update()
                self.assert_unchanged()

    def test_prereleases_and_unsupported_versions_are_rejected(self):
        for version in (f"{self.new}rc1", f"{self.new}.dev0", f"{self.new}\ninjected"):
            with self.subTest(version=version):
                self.releases[None] = pypi(version)
                with self.assertRaises(ValueError):
                    self.update()
                self.assert_unchanged()


if __name__ == "__main__":
    unittest.main()
