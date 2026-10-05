#!/usr/bin/env python3
"""Ensure runtime dependencies are allowed without hiding bundled add-ons."""

from contextlib import redirect_stdout
from importlib.machinery import ModuleSpec
import io
from pathlib import Path
import runpy
import unittest
from unittest.mock import patch

CHECK_BASE_MODULE = runpy.run_path(Path(__file__).with_name("check-optionals.py"))["check_base_module"]


class BaseModuleCheck(unittest.TestCase):
    def test_module_origins(self):
        cases = [
            (None, None, True),
            ("/usr/lib/python3.14/site-packages/markupsafe/__init__.py",
             ["/usr/lib/python3.14/site-packages/markupsafe"], True),
            ("/app/lib/python3.14/site-packages/markupsafe/__init__.py",
             ["/app/lib/python3.14/site-packages/markupsafe"], False),
            ("/app/extensions/jinja/lib/python3.14/site-packages/markupsafe/__init__.py",
             None, False),
            (None, ["/usr/lib/python3.14/site-packages/namespace"], True),
            (None, ["/usr/lib/python3.14/site-packages/namespace",
                    "/app/lib/python3.14/site-packages/namespace"], False),
            (None, [], False),
        ]
        for origin, locations, allowed in cases:
            spec = None
            if origin is not None or locations is not None:
                spec = ModuleSpec("markupsafe", loader=None, origin=origin)
                spec.submodule_search_locations = locations
            with self.subTest(origin=origin, locations=locations), \
                    patch("importlib.util.find_spec", return_value=spec), \
                    redirect_stdout(io.StringIO()):
                if allowed:
                    CHECK_BASE_MODULE("markupsafe")
                else:
                    with self.assertRaisesRegex(AssertionError, "leaked into the base app"):
                        CHECK_BASE_MODULE("markupsafe")


if __name__ == "__main__":
    unittest.main()
