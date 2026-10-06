#!/usr/bin/env python3
"""Exercise the installed CLI against a local server, without external sites."""

import base64
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--with-yt-dlp", action="store_true")
    args = parser.parse_args()
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
            # The sandbox's home folder is temporary unless it is shared, so
            # gallery-dl must refuse to download there instead of losing files.
            import gallery_dl_flatpak
            unshared = Path.home() / "gallery-dl unshared check"
            if gallery_dl_flatpak.is_discarded(unshared):
                result = subprocess.run(
                    ["gallery-dl", "--config-ignore", "--no-input", "-D", str(unshared),
                     f"http://127.0.0.1:{server.server_port}/image.png"],
                    capture_output=True, text=True, timeout=30,
                )
                assert result.returncode != 0, "Download to an unshared folder succeeded"
                assert not unshared.exists(), "gallery-dl wrote to an unshared folder"
                assert f"--filesystem={unshared}:rw" in result.stderr, result.stderr
                print("Download to a folder that isn't shared was refused.")
            else:
                print("Skipped the unshared folder check: the home folder is shared.")
            if args.with_yt_dlp:
                # Use an actual audio file so yt-dlp's generic extractor can
                # download it locally through gallery-dl's ytdl integration.
                import wave
                with wave.open(str(source / "audio.wav"), "wb") as audio:
                    audio.setnchannels(1)
                    audio.setsampwidth(2)
                    audio.setframerate(8000)
                    audio.writeframes(b"\0\0" * 800)
                video_output = root / "yt-dlp download"
                subprocess.run([
                    "gallery-dl", "--config-ignore", "--no-input",
                    "-D", str(video_output),
                    f"ytdl:http://127.0.0.1:{server.server_port}/audio.wav",
                ], check=True, timeout=30)
                media = list(video_output.iterdir())
                assert len(media) == 1, media
                assert media[0].read_bytes() == (source / "audio.wav").read_bytes()
                print("gallery-dl's yt-dlp download integration passed.")
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    main()
