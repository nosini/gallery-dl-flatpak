#!/usr/bin/env python3
"""Test the keyring add-on against a throwaway Secret Service.

Needs dbus-daemon and gnome-keyring-daemon, and a Python with the pinned
gallery_dl and SecretStorage packages. A private bus and a temporary keyring
are started, so the desktop's own keyring is never touched.
"""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

KEYRING_DIR = Path(__file__).resolve().parents[1] / "addons/keyring"
BUS_CONFIG = """<busconfig>
  <type>session</type>
  <listen>unix:dir={dir}</listen>
  <auth>EXTERNAL</auth>
  <policy context="default">
    <allow send_destination="*" eavesdrop="true"/>
    <allow eavesdrop="true"/>
    <allow own="*"/>
  </policy>
</busconfig>
"""
# Runs in a fresh process each time, like a gallery-dl invocation.
LOOKUP = """
import json, sys
import usercustomize
from gallery_dl import config, extractor
for option, value in json.loads(sys.argv[2]).items():
    config.set(("extractor", "danbooru"), option, value)
extr = extractor.find(sys.argv[1])
try:
    auth = list(extr._get_auth_info())
except extr.exc.AbortExtraction as exc:
    auth = str(exc)
print(json.dumps({
    "category": extr.category,
    "auth": auth,
    "api-key": extr.config("api-key", "default"),
    "token": extr.config("token", "default"),
}))
"""
URL = "https://danbooru.donmai.us/posts/1"


class KeyringTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        for program in ("dbus-daemon", "gnome-keyring-daemon"):
            if not shutil.which(program):
                raise unittest.SkipTest(f"{program} is not installed")
        cls.tmp = tempfile.TemporaryDirectory()
        root = Path(cls.tmp.name)
        (root / "bus").mkdir()
        (root / "runtime").mkdir(mode=0o700)
        config = root / "bus.conf"
        config.write_text(BUS_CONFIG.format(dir=root / "bus"))
        cls.processes = []
        address = cls.start_bus(config)
        # Inside Flatpak, a bus without the keyring is what the sandbox sees
        # unless it is granted --talk-name=org.freedesktop.secrets.
        cls.empty_bus = cls.start_bus(config)
        env = {key: value for key, value in os.environ.items()
               if not key.startswith(("GNOME_KEYRING", "DBUS_", "XDG_"))}
        env.update(DBUS_SESSION_BUS_ADDRESS=address, XDG_RUNTIME_DIR=str(root / "runtime"),
                   XDG_DATA_HOME=str(root / "data"), XDG_CONFIG_HOME=str(root / "config"),
                   PYTHONPATH=str(KEYRING_DIR))
        cls.env = env
        keyring = subprocess.Popen(
            ["gnome-keyring-daemon", "--foreground", "--components=secrets", "--unlock"],
            stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, env=env,
        )
        cls.processes.append(keyring)
        keyring.stdin.write(b"test password")
        keyring.stdin.close()
        cls.wait_for_service()

    @classmethod
    def start_bus(cls, config):
        bus = subprocess.Popen(
            ["dbus-daemon", f"--config-file={config}", "--nofork", "--print-address=1"],
            stdout=subprocess.PIPE, text=True,
        )
        cls.processes.append(bus)
        return bus.stdout.readline().strip()

    @classmethod
    def wait_for_service(cls):
        check = ("import secretstorage; "
                 "c = secretstorage.dbus_init(); "
                 "assert secretstorage.check_service_availability(c); "
                 "assert not secretstorage.get_default_collection(c).is_locked()")
        for _ in range(100):
            if subprocess.run([sys.executable, "-c", check], env=cls.env,
                              capture_output=True).returncode == 0:
                return
            time.sleep(0.1)
        raise RuntimeError("gnome-keyring-daemon did not provide an unlocked keyring")

    @classmethod
    def tearDownClass(cls):
        for process in reversed(cls.processes):
            process.terminate()
            process.wait(timeout=10)
        cls.tmp.cleanup()

    def setUp(self):
        for category, option in self.listed():
            self.command("delete", category, option)

    def command(self, *args, value=None, env=None, check=True):
        return subprocess.run(
            [sys.executable, "-m", "gallery_dl_keyring", *args], input=value,
            env=env or self.env, capture_output=True, text=True, check=check,
        )

    def listed(self):
        output = self.command("list").stdout
        return [tuple(line.split("\t")) for line in output.splitlines()]

    def lookup(self, configured=None, env=None):
        output = subprocess.run(
            [sys.executable, "-c", LOOKUP, URL, json.dumps(configured or {})],
            env=env or self.env, capture_output=True, text=True, check=True,
        ).stdout
        return json.loads(output)

    def test_stored_options_are_used(self):
        self.command("set", "danbooru", "username", value="keyring user\n")
        self.command("set", "danbooru", "password", value="pass word\n")
        self.command("set", "danbooru", "api-key", value="key with\nnewline\n")
        self.assertEqual(self.listed(), [("danbooru", "api-key"), ("danbooru", "password"),
                                         ("danbooru", "username")])
        result = self.lookup()
        self.assertEqual(result["category"], "danbooru")
        self.assertEqual(result["auth"], ["keyring user", "pass word"])
        self.assertEqual(result["api-key"], "key with\nnewline")
        self.assertEqual(result["token"], "default")

    def test_configuration_takes_precedence(self):
        self.command("set", "danbooru", "username", value="keyring user")
        self.command("set", "danbooru", "password", value="keyring password")
        self.command("set", "danbooru", "api-key", value="keyring key")
        result = self.lookup({"username": "configured user", "api-key": None})
        self.assertEqual(result["auth"], ["configured user", "keyring password"])
        self.assertIsNone(result["api-key"])

    def test_set_replaces_and_delete_removes(self):
        self.command("set", "danbooru", "username", value="old")
        self.command("set", "danbooru", "username", value="new")
        self.assertEqual(self.listed(), [("danbooru", "username")])
        self.assertEqual(self.lookup()["auth"], "User input required (password)")
        self.command("delete", "danbooru", "username")
        self.assertEqual(self.listed(), [])
        self.assertEqual(self.lookup()["auth"], [None, None])
        result = self.command("delete", "danbooru", "username", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertIn("No 'username' stored for danbooru", result.stderr)

    def test_empty_value_is_rejected(self):
        result = self.command("set", "danbooru", "password", value="\n", check=False)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.listed(), [])

    def test_unavailable_keyring(self):
        self.command("set", "danbooru", "username", value="keyring user")
        for address in (self.empty_bus, f"unix:path={self.tmp.name}/missing"):
            with self.subTest(address=address):
                env = dict(self.env, DBUS_SESSION_BUS_ADDRESS=address)
                self.assertEqual(self.lookup(env=env)["auth"], [None, None])
                result = self.command("list", env=env, check=False)
                self.assertEqual(result.returncode, 1)
                self.assertIn("--talk-name=org.freedesktop.secrets", result.stderr)
                self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
