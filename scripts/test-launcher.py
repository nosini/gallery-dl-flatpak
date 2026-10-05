#!/usr/bin/env python3
"""Test the launcher's download folder check without Flatpak.

Needs a Python with the pinned gallery_dl package. The sandbox's mounts are
simulated, so this runs on the host or in CI.
"""

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import io
import logging
from pathlib import Path
import sys
import tempfile
import threading
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flatpak/launcher"))
import gallery_dl_flatpak  # noqa: E402


class DiscardedPaths(unittest.TestCase):
    MOUNTS = ("/", "/usr", "/app", "/home/user/.var/app/eu.nosini.GalleryDl",
              "/home/user/Downloads", "/home/user/My Pictures", "/tmp")

    def test_paths(self):
        cases = {
            "/home/user/mnt/vault/gallery-dl": True,
            "/home/user/gallery-dl": True,
            "/home/user/Downloads": False,
            "/home/user/Downloads/gallery-dl/site": False,
            "/home/user/Downloads-other": True,
            "/home/user/My Pictures/site": False,
            "/tmp/download": False,
            "/": True,
        }
        for path, discarded in cases.items():
            with self.subTest(path=path):
                self.assertIs(gallery_dl_flatpak.is_discarded(path, self.MOUNTS), discarded)

    def test_mountinfo_escapes(self):
        # The kernel escapes space, tab, newline and backslash as octal and
        # writes other characters, including UTF-8, unchanged.
        lines = ("101 90 0:52 / /home/user/My\\040Pictures rw - fuse x rw\n"
                 "102 90 0:53 / /home/user/back\\134slash rw - fuse y rw\n"
                 "103 90 0:54 / /home/user/café rw - fuse z rw\n")
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as stream:
            stream.write(lines)
        try:
            mounts = gallery_dl_flatpak.mount_points.__wrapped__(stream.name)
        finally:
            Path(stream.name).unlink()
        self.assertEqual(mounts, ("/home/user/My Pictures", "/home/user/back\\slash",
                                  "/home/user/café"))


class DownloadGuard(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from gallery_dl import config, job, output
        cls.config, cls.job = config, job
        output.initialize_logging(logging.ERROR)
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        (cls.root / "source").mkdir()
        (cls.root / "source/image.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        cls.server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=cls.root / "source"))
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        original = job.DownloadJob.handle_directory
        with mock.patch("os.path.exists", side_effect=lambda path: path == "/.flatpak-info"):
            gallery_dl_flatpak.install()
        cls.addClassCleanup(setattr, job.DownloadJob, "handle_directory", original)

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.tmp.cleanup()

    def download(self, target, mounts):
        url = f"http://127.0.0.1:{self.server.server_port}/image.png"
        self.config.clear()
        self.config.set((), "directory", [])
        self.config.set((), "base-directory", str(target))
        log = io.StringIO()
        handler = logging.StreamHandler(log)
        logging.getLogger().addHandler(handler)
        try:
            with mock.patch.object(gallery_dl_flatpak, "mount_points", return_value=mounts):
                status = self.job.DownloadJob(url).run()
        finally:
            logging.getLogger().removeHandler(handler)
            self.config.clear()
        return status, log.getvalue()

    def test_unshared_folder_is_refused(self):
        target = self.root / "unshared"
        status, log = self.download(target, ("/",))
        self.assertNotEqual(status, 0)
        self.assertFalse(target.exists(), "nothing may be written")
        self.assertIn(f"--filesystem={target}:rw", log)

    def test_shared_folder_downloads(self):
        target = self.root / "shared"
        status, log = self.download(target, ("/", str(self.root)))
        self.assertEqual(status, 0, log)
        files = list(target.iterdir())
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0].read_bytes(), b"\x89PNG\r\n\x1a\n")

    def test_simulation_is_not_affected(self):
        url = f"http://127.0.0.1:{self.server.server_port}/image.png"
        with mock.patch.object(gallery_dl_flatpak, "mount_points", return_value=("/",)):
            self.assertEqual(self.job.SimulationJob(url).run(), 0)

    def test_outside_flatpak_does_nothing(self):
        with mock.patch("os.path.exists", return_value=False), \
                mock.patch.object(self.job.DownloadJob, "handle_directory", "unchanged"):
            gallery_dl_flatpak.install()
            self.assertEqual(self.job.DownloadJob.handle_directory, "unchanged")


if __name__ == "__main__":
    unittest.main()
