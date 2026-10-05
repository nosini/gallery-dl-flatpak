#!/usr/bin/env python3
"""Write installer links for the signed app and every add-on."""

import json
import os
from pathlib import Path


def main():
    repo = Path("signed-repo")
    url = os.environ["REPO_URL"]
    key = os.environ["PUBLIC_KEY"]
    repository = os.environ["GITHUB_REPOSITORY"]
    addons = json.loads(Path("flatpak/addons.json").read_text())
    (repo / "gallery-dl.flatpakrepo").write_text(
        f"[Flatpak Repo]\nTitle=gallery-dl\nUrl={url}\n"
        f"Homepage=https://github.com/{repository}\nGPGKey={key}\n"
    )
    entries = [{"slug": "", "suffix": "", "name": "gallery-dl"}] + addons
    for entry in entries:
        suffix = f".{entry['suffix']}" if entry["suffix"] else ""
        slug = f"-{entry['slug']}" if entry["slug"] else ""
        is_runtime = bool(suffix)
        runtime_repo = "" if is_runtime else "RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo\n"
        (repo / f"gallery-dl{slug}.flatpakref").write_text(
            f"[Flatpak Ref]\nName=eu.nosini.GalleryDl{suffix}\nBranch=stable\n"
            f"Title={entry['name']}\nUrl={url}\n{runtime_repo}"
            f"IsRuntime={str(is_runtime).lower()}\nSuggestRemoteName=gallery-dl\nGPGKey={key}\n"
        )


if __name__ == "__main__":
    main()
