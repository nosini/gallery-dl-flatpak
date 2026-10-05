#!/usr/bin/env bash
set -euo pipefail

flatpak build-bundle --arch=x86_64 \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
  repo gallery-dl-x86_64.flatpak eu.nosini.GalleryDl stable
while read -r suffix slug; do
  flatpak build-bundle --runtime --arch=x86_64 \
    repo "gallery-dl-$slug-x86_64.flatpak" "eu.nosini.GalleryDl.$suffix" stable
done < <(python3 -c 'import json; [print(a["suffix"], a["slug"]) for a in json.load(open("flatpak/addons.json"))]')
