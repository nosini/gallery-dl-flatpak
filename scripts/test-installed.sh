#!/usr/bin/env bash
# Install the build exported to repo/ and run the checks inside the installed
# app's sandbox, so they run against the Platform runtime rather than the SDK:
# tests/check-installed.sh for the app alone, then tests/check-optionals.py
# with each add-on installed by itself, and with all of them together. Run
# from anywhere after building with --repo=repo.
set -euo pipefail
cd "$(dirname "$0")/.."

: "${APP_ID:=$(sed -n 's/^id: *//p' ./*.yml)}"
: "${FLATPAK_BRANCH:=stable}"
: "${FLATPAK_ARCH:=$(flatpak --default-arch)}"
ref="app/$APP_ID/$FLATPAK_ARCH/$FLATPAK_BRANCH"

if ! flatpak --user remotes --columns=name | grep -qx local-test; then
  flatpak --user remote-add --no-gpg-verify local-test "$PWD/repo"
fi
url=$(flatpak --user remotes --columns=name,url | awk '$1 == "local-test" { print $2 }')
if [[ "$url" != "file://$PWD/repo" ]]; then
  echo "The local-test remote points to $url, not this checkout's repo/." >&2
  echo 'Remove it with: flatpak --user remote-delete local-test' >&2
  exit 1
fi

# Don't replace an existing installation when running locally. The add-on
# checks also need to start without any add-on installed.
installed=$(flatpak --user list --columns=application | grep -E "^${APP_ID//./\\.}(\\.|\$)" | sort -u | tr '\n' ' ' || true)
if [[ -n "$installed" ]]; then
  echo "These checks need a fresh installation; remove $APP_ID and its add-ons with:" >&2
  echo "  flatpak --user uninstall $installed" >&2
  exit 1
fi

run() {
  flatpak run --user --arch="$FLATPAK_ARCH" --branch="$FLATPAK_BRANCH" \
    --filesystem="$PWD/tests:ro" --filesystem="$PWD/addons:ro" "$@"
}
check_optionals() {
  run --command=python3 "$APP_ID" -P "$PWD/tests/check-optionals.py" "$1"
}
install_addon() {
  flatpak --user install --noninteractive local-test "runtime/$APP_ID.$1/$FLATPAK_ARCH/$FLATPAK_BRANCH"
}
uninstall_addon() {
  flatpak --user uninstall --noninteractive "runtime/$APP_ID.$1/$FLATPAK_ARCH/$FLATPAK_BRANCH"
}
mapfile -t addons < <(python3 -c 'import json; [print(a["suffix"], a["slug"]) for a in json.load(open("addons/addons.json"))]')

# flatpak-builder doesn't always refresh the summary of an existing repo.
flatpak build-update-repo repo
flatpak --user install --noninteractive --no-related local-test "$ref"
run --command=sh "$APP_ID" -s "$PWD/tests" < tests/check-installed.sh

# Each add-on must work on its own, and leave nothing behind when removed.
for addon in "${addons[@]}"; do
  read -r suffix slug <<< "$addon"
  install_addon "$suffix"
  check_optionals "$slug"
  if [[ "$slug" == yt-dlp ]]; then
    run --command=python3 "$APP_ID" -P "$PWD/tests/smoke-test.py" --with-yt-dlp
  fi
  uninstall_addon "$suffix"
  check_optionals base
done

for addon in "${addons[@]}"; do
  read -r suffix _ <<< "$addon"
  install_addon "$suffix"
done
check_optionals all
run --command=python3 "$APP_ID" -P "$PWD/tests/smoke-test.py" --with-yt-dlp
