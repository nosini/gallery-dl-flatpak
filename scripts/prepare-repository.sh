#!/usr/bin/env bash
# Sign a tested build and generate the files used to install/update it.
set -euo pipefail

: "${GNUPGHOME:?}"
: "${GPG_KEY:?}"
: "${REPO_URL:?}"
: "${GITHUB_REPOSITORY:?}"

# Copy the exported refs, not the build directory: flatpak-builder excludes
# the add-on files from the app ref and exports them as a separate runtime ref.
cp -a repo signed-repo
flatpak build-sign --gpg-sign="$GPG_KEY" --gpg-homedir="$GNUPGHOME" \
  signed-repo eu.nosini.GalleryDl stable
while read -r suffix; do
  flatpak build-sign --runtime --gpg-sign="$GPG_KEY" --gpg-homedir="$GNUPGHOME" \
    signed-repo "eu.nosini.GalleryDl.$suffix" stable
done < <(python3 -c 'import json; [print(a["suffix"]) for a in json.load(open("flatpak/addons.json"))]')
# Flatpak skips catalog commits whose content hasn't changed, including their
# signatures. The test repo's catalogs are unsigned, so regenerate them here.
bash scripts/reset-appstream-refs.sh signed-repo
flatpak build-update-repo --gpg-sign="$GPG_KEY" --gpg-homedir="$GNUPGHOME" \
  --title="gallery-dl" --default-branch=stable signed-repo

PUBLIC_KEY=$(gpg --batch --export --export-options export-minimal "$GPG_KEY" | base64 -w0)
test -n "$PUBLIC_KEY"
export PUBLIC_KEY
python3 scripts/write-repository-files.py
# OSTree scratch files must not be published by Pages.
rm -rf signed-repo/tmp
