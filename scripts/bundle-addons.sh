#!/usr/bin/env bash
# Write a single-file bundle of each add-on in repo/, named
# gallery-dl-<slug>-<arch>.flatpak. Bundle the app itself with
# `flatpak build-bundle` as described in docs/development.md.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${APP_ID:=$(sed -n 's/^id: *//p' ./*.yml)}"
: "${FLATPAK_BRANCH:=stable}"
: "${FLATPAK_ARCH:=$(flatpak --default-arch)}"

while read -r suffix slug; do
  flatpak build-bundle --runtime --arch="$FLATPAK_ARCH" \
    repo "gallery-dl-$slug-$FLATPAK_ARCH.flatpak" "$APP_ID.$suffix" "$FLATPAK_BRANCH"
done < <(python3 -c 'import json; [print(a["suffix"], a["slug"]) for a in json.load(open("addons/addons.json"))]')
