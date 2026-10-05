#!/usr/bin/env bash
# Discard cached catalog refs in the unpublished copy before signed regeneration.
set -euo pipefail
repository=${1:?Pass the unpublished repository directory}
ostree --repo="$repository" refs --delete appstream
ostree --repo="$repository" refs --delete appstream2
