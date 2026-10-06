# shellcheck shell=sh
# Runs inside the installed app's sandbox (see scripts/test-installed.sh), with
# no add-on installed. Its argument is this directory, shared read-only. There
# is no display, keyring or session bus in CI, so keep these checks headless.
set -eu
tests=$1

test -x /app/bin/gallery-dl
test -x /app/bin/gallery-dl-flatpak
test -x /app/bin/gallery-dl-terminal

# The version gallery-dl reports must be the newest release in the metainfo,
# which the update workflow adds together with the new wheel.
release=$(sed -n 's/.*<release version="\([^"]*\)".*/\1/p' \
  "/app/share/metainfo/$FLATPAK_ID.metainfo.xml" | head -n 1)
version=$(gallery-dl --version)
if [ "$version" != "$release" ]; then
  echo "gallery-dl reports $version, but the newest metainfo release is $release." >&2
  exit 1
fi
gallery-dl --help > /dev/null

# Ugoira conversion uses the runtime's FFmpeg.
ffmpeg -version > /dev/null
ffprobe -version > /dev/null

# -P keeps the working directory from shadowing installed modules.
# Dependencies, built-in features, and no optional packages in the base app:
python3 -P "$tests/check-optionals.py" base
# Downloads from a local server, archives and the download folder check:
python3 -P "$tests/smoke-test.py"
python3 -P "$tests/test-launcher.py"

# The wheels install their license files with their metadata.
test -n "$(ls /app/lib/python3.14/site-packages/gallery_dl-*.dist-info/licenses)"

echo 'Installed app checks passed.'
