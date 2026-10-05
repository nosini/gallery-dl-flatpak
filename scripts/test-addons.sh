#!/usr/bin/env bash
# Test the app against its runtime, then every extension alone and together.
set -euo pipefail

run_check() {
  flatpak run --filesystem="$PWD/scripts:ro" --filesystem="$PWD/flatpak:ro" \
    --command=python3 eu.nosini.GalleryDl "$PWD/scripts/check-optionals.py" "$1"
}
run_download() {
  flatpak run --filesystem="$PWD/scripts:ro" --command=python3 \
    eu.nosini.GalleryDl "$PWD/scripts/smoke-test.py" "$@"
}

flatpak --user install --noninteractive local-test eu.nosini.GalleryDl
flatpak run eu.nosini.GalleryDl --version
flatpak run eu.nosini.GalleryDl --help
flatpak run --command=ffmpeg eu.nosini.GalleryDl -version
flatpak run --command=ffprobe eu.nosini.GalleryDl -version
run_check base
run_download

while read -r suffix slug; do
  flatpak --user install --noninteractive local-test "eu.nosini.GalleryDl.$suffix//stable"
  run_check "$slug"
  if [[ "$slug" == yt-dlp ]]; then
    run_download --with-yt-dlp
  fi
  flatpak --user uninstall --noninteractive "eu.nosini.GalleryDl.$suffix//stable"
  run_check base
done < <(python3 -c 'import json; [print(a["suffix"], a["slug"]) for a in json.load(open("flatpak/addons.json"))]')

while read -r suffix; do
  flatpak --user install --noninteractive local-test "eu.nosini.GalleryDl.$suffix//stable"
done < <(python3 -c 'import json; [print(a["suffix"]) for a in json.load(open("flatpak/addons.json"))]')
run_check all
run_download --with-yt-dlp
