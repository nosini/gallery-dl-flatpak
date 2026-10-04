#!/usr/bin/env python3
"""Exercise the installed CLI against a local server, without external sites."""

import base64
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading


def main():
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        source = root / "source"
        source.mkdir()
        payload = base64.b64decode(
            "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1sAAAAASUVORK5CYII="
        )
        (source / "image.png").write_bytes(payload)
        server = ThreadingHTTPServer(
            ("127.0.0.1", 0), partial(SimpleHTTPRequestHandler, directory=source)
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            # Spaces catch accidental argument splitting; -D must override the
            # download destination without changing gallery-dl's CLI semantics.
            output = root / "download with spaces"
            command = [
                "gallery-dl", "--config-ignore", "--no-input",
                "--download-archive", str(root / "archive.sqlite3"),
                "-D", str(output),
                f"http://127.0.0.1:{server.server_port}/image.png",
            ]
            subprocess.run(command, check=True, timeout=30)
            files = list(output.iterdir())
            assert len(files) == 1, files
            assert files[0].read_bytes() == payload
            # Removing the file makes this distinguish archive skipping from
            # merely noticing an existing download.
            files[0].unlink()
            subprocess.run(command, check=True, timeout=30)
            assert not list(output.iterdir()), "Archived download was fetched again"
            print("Download, destination argument, and archive smoke tests passed.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
