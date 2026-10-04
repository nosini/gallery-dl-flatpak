# Using gallery-dl

## A shorter command

Add this alias to your shell configuration to use `gallery-dl` directly:

```sh
alias gallery-dl='flatpak run eu.nosini.GalleryDl'
```

Then download with:

```sh
gallery-dl -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

The `-d` option selects a base directory; gallery-dl creates its usual subfolders
underneath it. Pass a destination explicitly: gallery-dl otherwise writes
relative to the current directory, which might not be accessible in the sandbox.

## Downloading to another folder

Downloads is accessible by default. To save elsewhere, grant access to an
existing directory and select it as the destination:

```sh
flatpak run --filesystem=/path/to/pictures:rw eu.nosini.GalleryDl \
  -d /path/to/pictures 'URL'
```

Replace `/path/to/pictures` with your destination. This permission applies only
to that invocation. To allow the directory permanently:

```sh
flatpak override --user --filesystem=/path/to/pictures:rw eu.nosini.GalleryDl
```

## Downloading from sites that require login

You can use cookies exported from your browser in Netscape format. Put the
export in `~/.var/app/eu.nosini.GalleryDl/config/gallery-dl/cookies.txt`, creating
the directory if necessary, then run:

```sh
flatpak run eu.nosini.GalleryDl \
  --cookies "$HOME/.var/app/eu.nosini.GalleryDl/config/gallery-dl/cookies.txt" \
  -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

To read cookies directly from a browser, grant read access to its profile.
For a native Firefox installation using `~/.mozilla/firefox`:

```sh
flatpak run --filesystem="$HOME/.mozilla/firefox:ro" eu.nosini.GalleryDl \
  --cookies-from-browser firefox -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

Other browser installations may store profiles elsewhere. Chromium-based
browsers may additionally require `--talk-name=org.freedesktop.secrets` to
decrypt cookies. Keyring access is opt-in.

## Video downloads and extra tools

The package includes yt-dlp, and FFmpeg and ffprobe are supplied by the Flatpak
runtime. Available codecs depend on that runtime.

Some features need additional tools that aren't included, such as mkvmerge or
a JavaScript runtime for yt-dlp's JavaScript challenges. Programs installed on
your system are not automatically accessible inside the Flatpak, including
commands used by gallery-dl postprocessors.

See the upstream [options](https://gdl-org.github.io/docs/options.html) and
[configuration reference](https://gdl-org.github.io/docs/configuration.html)
for more ways to customize downloads.
