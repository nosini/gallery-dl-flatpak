#!/usr/bin/env python3
"""Exercise optional dependencies without external sites or desktop services."""

import argparse
import importlib
from importlib import metadata
import importlib.util
import io
import json
from pathlib import Path
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import types
import wave

ADDONS = json.loads((Path(__file__).resolve().parents[1] / "addons/addons.json").read_text())


def check_base_module(module):
    spec = importlib.util.find_spec(module)
    if spec is None:
        return
    paths = ([spec.origin] if spec.origin else []) + list(spec.submodule_search_locations or ())
    # Dependencies already in the Platform are available without an add-on.
    # Reject anything supplied by the app or a mounted extension instead.
    assert paths and all(Path(path).resolve().is_relative_to("/usr") for path in paths), (
        f"{module} leaked into the base app from {paths}"
    )
    print(f"{module}: supplied by the runtime ({paths[0]}).")


def check_requirements():
    """Check that the requirements of every bundled package are installed.

    The update workflow bumps pinned wheels one by one, so this catches a new
    release that needs a dependency or version the package doesn't bundle.
    """
    def canonical(name):
        return re.sub(r"[-_.]+", "-", name).lower()

    # The Platform has no pip; borrow the packaging module that setuptools
    # vendors, without letting its other vendored packages count as installed.
    paths = list(sys.path)
    setuptools = Path(importlib.util.find_spec("setuptools").origin).parent
    sys.path.insert(0, str(setuptools / "_vendor"))
    try:
        from packaging.requirements import Requirement
    finally:
        sys.path.remove(str(setuptools / "_vendor"))

    installed = {}
    for dist in metadata.distributions(path=paths):
        installed.setdefault(canonical(dist.metadata["Name"]), dist)
    bundled = [dist for dist in installed.values()
               if Path(str(dist.locate_file(""))).resolve().is_relative_to("/app")]
    for dist in bundled:
        for text in dist.requires or ():
            requirement = Requirement(text)
            if requirement.marker and not requirement.marker.evaluate({"extra": ""}):
                continue
            needed = f"{dist.metadata['Name']} needs {requirement}"
            match = installed.get(canonical(requirement.name))
            assert match, f"{needed}, which isn't installed"
            assert requirement.specifier.contains(match.version, prereleases=True), (
                f"{needed}, but {match.version} is installed")
    print(f"The requirements of all {len(bundled)} bundled packages are installed.")


def check_config(kind, text):
    from gallery_dl import config
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / f"config.{kind}"
        path.write_text(text)
        settings = {}
        try:
            config.default(kind)
            config.load([str(path)], strict=True, conf=settings)
            assert settings["extractor"]["timeout"] == 17
        finally:
            config.default("json")


def check_process_name():
    # Waiting for URLs on stdin keeps gallery-dl running while it is inspected.
    process = subprocess.Popen(["gallery-dl", "--config-ignore", "-i", "-"],
                               stdin=subprocess.PIPE, stdout=subprocess.DEVNULL)
    try:
        executable = Path(f"/proc/{process.pid}/exe").readlink()
    finally:
        process.communicate(timeout=30)
    assert executable == Path("/app/bin/gallery-dl-flatpak"), f"gallery-dl runs as {executable}"
    print("gallery-dl runs as gallery-dl-flatpak.")


def check_keyring_fallback():
    import gallery_dl_keyring
    from gallery_dl import config
    from gallery_dl.extractor.common import Extractor
    # main() imported gallery-dl before this, so startup must have patched it.
    assert Extractor.config.__module__ == "gallery_dl_keyring", "Keyring fallback isn't installed"
    extractor = types.SimpleNamespace(category="example", _cfgpath=("extractor", "example", "page"))
    stored = {("example", "username"): "keyring user", ("example", "password"): "keyring secret"}
    real_store = gallery_dl_keyring.store
    gallery_dl_keyring.store = types.SimpleNamespace(
        lookup=lambda category, option: stored.get((category, option), gallery_dl_keyring.MISSING))
    try:
        config.set(("extractor", "example"), "username", "configured user")
        config.set(("extractor", "example"), "api-key", None)
        assert Extractor.config(extractor, "username") == "configured user"
        assert Extractor.config(extractor, "password") == "keyring secret"
        assert Extractor.config(extractor, "api-key", "default") is None
        assert Extractor.config(extractor, "token", "default") == "default"
    finally:
        gallery_dl_keyring.store = real_store
        config.clear()
    # Checks have no keyring access, which must not break option lookups.
    assert Extractor.config(extractor, "password", "default") == "default"


def check(addon):
    for module in addon["imports"]:
        importlib.import_module(module)
    slug = addon["slug"]
    payload = b"gallery-dl optional dependency check" * 100
    if slug == "yt-dlp":
        import yt_dlp
        from gallery_dl import ytdl
        assert ytdl.import_module(None) is yt_dlp
        subprocess.run(["yt-dlp", "--version"], check=True)
    elif slug == "pysocks":
        import socks
        from urllib3.contrib.socks import SOCKSProxyManager
        with socks.socksocket() as sock:
            sock.set_proxy(socks.SOCKS5, "localhost", 1080)
        assert SOCKSProxyManager("socks5h://localhost:1080").proxy_url
    elif slug == "brotli":
        import brotli
        assert brotli.decompress(brotli.compress(payload)) == payload
        from urllib3.response import HTTPResponse
        assert "br" in HTTPResponse.CONTENT_DECODERS
        response = HTTPResponse(body=io.BytesIO(brotli.compress(payload)), headers={"Content-Encoding": "br"})
        assert response.data == payload
    elif slug == "pyyaml":
        check_config("yaml", "extractor:\n  timeout: 17\n")
    elif slug == "secretstorage":
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        aes = AESGCM(b"k" * 16)
        encrypted = aes.encrypt(b"n" * 12, payload, None)
        assert aes.decrypt(b"n" * 12, encrypted, None) == payload
        check_keyring_fallback()
        subprocess.run(["gallery-dl-keyring", "--help"], check=True, stdout=subprocess.DEVNULL)
    elif slug == "psycopg":
        import psycopg
        from psycopg import pq
        assert pq.__impl__ == "binary", "Psycopg must bring its own libpq"
        assert pq.version() > 0
        assert psycopg.sql.Identifier("archive").as_string() == '"archive"'
    elif slug == "truststore":
        import truststore
        context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        assert context.verify_mode == ssl.CERT_REQUIRED
    elif slug == "jinja":
        import jinja2
        assert jinja2.Template("{{ name|upper }}").render(name="gallery-dl") == "GALLERY-DL"
    elif slug == "mkvmerge":
        subprocess.run(["mkvmerge", "--version"], check=True)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audio = root / "audio.wav"
            with wave.open(str(audio), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(8000)
                stream.writeframes(b"\0\0" * 800)
            output = root / "audio.mka"
            subprocess.run(["mkvmerge", "-o", str(output), str(audio)], check=True)
            identified = json.loads(subprocess.check_output(["mkvmerge", "-J", str(output)], text=True))
            assert identified["tracks"][0]["type"] == "audio"
    print(f"{slug}: optional dependency check passed.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("mode", choices=["base", "all"] + [a["slug"] for a in ADDONS])
    mode = parser.parse_args().mode
    import gallery_dl
    import requests
    import tomllib
    from compression import zstd
    from gallery_dl.extractor.common import ZSTD
    from urllib3.response import HTTPResponse
    assert gallery_dl and requests and tomllib.loads("enabled = true")["enabled"]
    check_config("toml", "[extractor]\ntimeout = 17\n")
    check_process_name()
    payload = b"gallery-dl built-in Zstandard check" * 100
    assert zstd.decompress(zstd.compress(payload)) == payload
    assert ZSTD and "zstd" in HTTPResponse.CONTENT_DECODERS
    response = HTTPResponse(body=io.BytesIO(zstd.compress(payload)), headers={"Content-Encoding": "zstd"})
    assert response.data == payload
    check_requirements()
    if mode == "base":
        for addon in ADDONS:
            for module in addon["imports"]:
                check_base_module(module)
        assert shutil.which("mkvmerge") is None, "mkvmerge leaked into the base app"
        assert shutil.which("gallery-dl-keyring") is None, "gallery-dl-keyring leaked into the base app"
        check_base_module("zstandard")
        print("Base app has required dependencies, built-in TOML and Zstandard, without bundled optional packages.")
    else:
        for addon in ADDONS:
            if mode in ("all", addon["slug"]):
                check(addon)


if __name__ == "__main__":
    main()
