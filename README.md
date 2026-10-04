# gallery-dl Flatpak

A community Flatpak package of [gallery-dl](https://codeberg.org/mikf/gallery-dl),
the command-line image gallery downloader. Includes gallery-dl 1.32.15, yt-dlp,
SOCKS proxy support, YAML configuration, and Jinja templates. Currently builds
for x86_64 Linux.

## Install

Download the `gallery-dl-x86_64` artifact from a successful **Flatpak** run in
this repository's GitHub Actions tab. Extract the archive, then install:

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user ./gallery-dl-x86_64.flatpak
```

If the maintainer has enabled the signed update repository on GitHub Pages,
install its `gallery-dl.flatpakref` instead. Its URL has the form
`https://OWNER.github.io/REPOSITORY/gallery-dl.flatpakref`:

```sh
flatpak install --user https://OWNER.github.io/REPOSITORY/gallery-dl.flatpakref
flatpak update --user eu.nosini.GalleryDl
```

Replace `OWNER` and `REPOSITORY` with the GitHub account and repository name.
Bundles from Actions are unsigned and need to be downloaded and installed again
for each update. The Pages installation verifies signatures and supports
`flatpak update`.

## Download galleries

Run gallery-dl in a terminal, with a URL from a
[supported site](https://codeberg.org/mikf/gallery-dl/src/branch/master/docs/supportedsites.md):

```sh
flatpak run eu.nosini.GalleryDl -d "$(xdg-user-dir DOWNLOAD)" 'URL'
flatpak run eu.nosini.GalleryDl --help
```

The `-d` option selects a base directory; gallery-dl creates its usual subfolders
underneath it. Pass a destination explicitly: gallery-dl otherwise writes
relative to the current directory, which might not be accessible in the sandbox.
You can add this alias to your shell configuration:

```sh
alias gallery-dl='flatpak run eu.nosini.GalleryDl'
```

## Configuration and permissions

Create the private configuration file with:

```sh
flatpak run eu.nosini.GalleryDl --config-create
```

It lives at `~/.var/app/eu.nosini.GalleryDl/config/gallery-dl/config.json`.
An existing gallery-dl JSON configuration can be copied there. See the upstream
[configuration reference](https://gdl-org.github.io/docs/configuration.html).

By default, the app can use the network, its private storage, and your Downloads
directory. Grant access to another destination for one invocation with:

```sh
flatpak run --filesystem=/path/to/pictures:rw eu.nosini.GalleryDl \
  -d /path/to/pictures 'URL'
```

For a permanent grant, use
`flatpak override --user --filesystem=/path/to/pictures:rw eu.nosini.GalleryDl`.
Replace example paths with existing directories.

For authentication, put a Netscape-format cookie export in the app's private
configuration directory and reference it with `--cookies`:

```sh
flatpak run eu.nosini.GalleryDl \
  --cookies "$HOME/.var/app/eu.nosini.GalleryDl/config/gallery-dl/cookies.txt" \
  -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

`--cookies-from-browser` requires access to the browser profile. For example,
for a native Firefox installation using `~/.mozilla/firefox`:

```sh
flatpak run --filesystem="$HOME/.mozilla/firefox:ro" eu.nosini.GalleryDl \
  --cookies-from-browser firefox -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

Other browser installations may store profiles elsewhere. Chromium-based
browsers may additionally require `--talk-name=org.freedesktop.secrets` to
decrypt cookies. SecretStorage is included, but keyring access is opt-in.

FFmpeg and ffprobe come from the Freedesktop runtime; available codecs depend
on that runtime. Extra programs such as mkvmerge, a JavaScript runtime for
yt-dlp's JavaScript challenges, and host-side postprocessing commands are not
included. Host executables are not automatically accessible inside the sandbox.

## Building and publishing

See [the development guide](docs/development.md) for local builds, dependency
updates, GitHub Actions, and signing-key setup.

This packaging is licensed under [GNU AGPLv3](LICENSE). Upstream gallery-dl is
licensed under GPL-2.0-only, and bundled dependencies retain their own licenses.
This package is maintained separately from upstream gallery-dl.
