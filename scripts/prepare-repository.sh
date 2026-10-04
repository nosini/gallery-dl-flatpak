#!/usr/bin/env bash
# Sign a tested build and generate the files used to install/update it.
set -euo pipefail

: "${GNUPGHOME:?}"
: "${GPG_KEY:?}"
: "${REPO_URL:?}"
: "${GITHUB_REPOSITORY:?}"

flatpak build-export --gpg-sign="$GPG_KEY" --gpg-homedir="$GNUPGHOME" \
  signed-repo build-dir stable
flatpak build-update-repo --gpg-sign="$GPG_KEY" --gpg-homedir="$GNUPGHOME" \
  --title="gallery-dl" --default-branch=stable signed-repo

public_key=$(gpg --batch --export --export-options export-minimal "$GPG_KEY" | base64 -w0)
test -n "$public_key"
cat > signed-repo/gallery-dl.flatpakrepo <<EOF
[Flatpak Repo]
Title=gallery-dl
Url=$REPO_URL
Homepage=https://github.com/$GITHUB_REPOSITORY
GPGKey=$public_key
EOF
cat > signed-repo/gallery-dl.flatpakref <<EOF
[Flatpak Ref]
Name=eu.nosini.GalleryDl
Branch=stable
Title=gallery-dl
Url=$REPO_URL
RuntimeRepo=https://dl.flathub.org/repo/flathub.flatpakrepo
IsRuntime=false
SuggestRemoteName=gallery-dl
GPGKey=$public_key
EOF
# OSTree scratch files must not be published by Pages.
rm -rf signed-repo/tmp
