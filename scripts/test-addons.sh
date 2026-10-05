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

# Without the remote, flatpak reports "No remote refs found for 'local-test'".
if ! flatpak --user remotes --columns=name | grep -qx local-test; then
  echo "Add the local-test remote first:" >&2
  echo "  flatpak --user remote-add --if-not-exists --no-gpg-verify local-test \"\$PWD/repo\"" >&2
  exit 1
fi
url=$(flatpak --user remotes --columns=name,url | awk '$1 == "local-test" { print $2 }')
if [[ "$url" != "file://$PWD/repo" ]]; then
  echo "local-test points to $url instead of this build's repository. Re-add it:" >&2
  echo "  flatpak --user remote-delete local-test" >&2
  echo "  flatpak --user remote-add --no-gpg-verify local-test \"\$PWD/repo\"" >&2
  exit 1
fi
installed=$(flatpak --user list --columns=application | grep -E '^eu\.nosini\.GalleryDl(\.|$)' | sort -u | tr '\n' ' ' || true)
if [[ -n "$installed" ]]; then
  echo "These tests need a fresh installation. Uninstall first (your data is kept):" >&2
  echo "  flatpak --user uninstall --noninteractive $installed" >&2
  exit 1
fi

# flatpak-builder exports refs without always refreshing the repository summary,
# which installing from the remote needs.
flatpak build-update-repo repo >/dev/null
flatpak --user install --noninteractive local-test eu.nosini.GalleryDl
flatpak run eu.nosini.GalleryDl --version
flatpak run eu.nosini.GalleryDl --help
flatpak run --command=ffmpeg eu.nosini.GalleryDl -version
flatpak run --command=ffprobe eu.nosini.GalleryDl -version
run_check base
run_download
flatpak run --filesystem="$PWD/scripts:ro" --filesystem="$PWD/flatpak:ro" --command=python3 \
  eu.nosini.GalleryDl "$PWD/scripts/test-launcher.py"

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
