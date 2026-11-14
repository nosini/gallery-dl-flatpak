#!/usr/bin/env python3
"""Test the requirement parsing of scripts/generate-python-deps.py offline."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

from packaging.requirements import Requirement


SCRIPT = Path(__file__).resolve().parents[1] / "generate-python-deps.py"


def load_script():
    spec = importlib.util.spec_from_file_location("generate_python_deps", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RequirementLinesTest(unittest.TestCase):
    def setUp(self):
        self.module = load_script()
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.path = Path(self.scratch.name) / "requirements.txt"

    def parse(self, *lines):
        self.path.write_text("\n".join(lines) + "\n")
        return self.module.requirement_lines(self.path)

    def test_hash_fragments_are_kept(self):
        url = "pkg @ https://host/pkg-1.0.tar.gz#sha256=0123"
        kept = self.parse(
            f'{url} ; python_version >= "3.11"',
            "other==1.0  # pinned by hand",
            "# whole-line comment",
        )
        # packaging versions differ in the spacing around `@`, so compare the
        # parsed requirement rather than the text.
        requirement = Requirement(kept[0])
        self.assertEqual(requirement.name, "pkg")
        self.assertEqual(requirement.url, "https://host/pkg-1.0.tar.gz#sha256=0123")
        self.assertEqual(str(requirement.marker), 'python_version >= "3.11"')
        self.assertEqual(kept[1:], ["other==1.0"])

    def test_plain_requirements_are_unchanged(self):
        self.assertEqual(
            self.parse("gallery-dl", "requests>=2  # for the API"),
            ["gallery-dl", "requests>=2"],
        )


if __name__ == "__main__":
    unittest.main()
