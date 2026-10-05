"""Start gallery-dl with checks specific to this Flatpak package.

Folders the sandbox hasn't been given access to still appear writable: they
are created on the sandbox's temporary root filesystem, and files saved there
are lost when gallery-dl exits. gallery-dl therefore refuses to download into
them and explains which permission is needed.

This is part of the gallery-dl Flatpak package, not of upstream gallery-dl.
"""

import functools
import os
import re
import sys

APP_ID = "eu.nosini.GalleryDl"


def _unescape(field):
    # mountinfo escapes space, tab, newline and backslash as octal.
    return re.sub(r"\\([0-7]{3})", lambda match: chr(int(match[1], 8)), field)


@functools.cache
def mount_points(mountinfo="/proc/self/mountinfo"):
    with open(mountinfo, encoding="utf-8", errors="surrogateescape") as stream:
        return tuple(_unescape(line.split()[4]) for line in stream)


def is_discarded(path, mounts=None):
    """Return True if files at path end up on the sandbox's root filesystem."""
    path = os.path.realpath(path)
    if mounts is None:
        mounts = mount_points()
    containing = max(
        (mount for mount in mounts
         if mount == "/" or path == mount or path.startswith(mount.rstrip("/") + "/")),
        key=len, default="/",
    )
    return containing == "/"


def _check_directory(job):
    pathfmt = job.pathfmt
    directory = getattr(pathfmt, "realdirectory", None)
    if not directory or not is_discarded(directory):
        return
    from gallery_dl import exception
    base = os.path.abspath(getattr(pathfmt, "basedirectory", None) or directory)
    raise exception.AbortExtraction(
        f"{os.path.abspath(directory)} isn't shared with the Flatpak sandbox, so "
        f"files saved there would be lost when gallery-dl exits. Make sure the "
        f"folder exists, then allow access with "
        f"'flatpak run --filesystem={base}:rw {APP_ID} ...' or "
        f"'flatpak override --user --filesystem={base}:rw {APP_ID}'.")


def install():
    """Check each download folder before gallery-dl writes to it."""
    if not os.path.exists("/.flatpak-info"):
        return
    from gallery_dl import job
    original = job.DownloadJob.handle_directory

    def handle_directory(self, kwdict):
        original(self, kwdict)
        _check_directory(self)

    job.DownloadJob.handle_directory = handle_directory


def main():
    install()
    from gallery_dl import main
    return main()


if __name__ == "__main__":
    sys.exit(main())
