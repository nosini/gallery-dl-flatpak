# gallery-dl Flatpak

Download image galleries and collections from
[hundreds of websites](https://codeberg.org/mikf/gallery-dl/src/branch/master/docs/supportedsites.md)
using [gallery-dl](https://codeberg.org/mikf/gallery-dl) in a terminal.
This community Flatpak package is for x86_64 Linux. Optional add-ons provide
video downloads, SOCKS proxies, extra configuration formats, and more.

## Install

Install [Flatpak](https://flatpak.org/setup/) if you don't already have it.

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user https://nosini.github.io/gallery-dl-flatpak/gallery-dl.flatpakref
```

To update:

```sh
flatpak update --user eu.nosini.GalleryDl
```

Open gallery-dl's page in GNOME Software to choose optional features under
**Add-ons**. For example, to add yt-dlp video support from the terminal:

```sh
flatpak install --user https://nosini.github.io/gallery-dl-flatpak/gallery-dl-yt-dlp.flatpakref
```

See [optional features](docs/usage.md#optional-features) for the full list.

## Download galleries

Replace `URL` with the address of a gallery or post:

```sh
flatpak run --filesystem=xdg-download:rw eu.nosini.GalleryDl \
  -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

This grants access to Downloads for this invocation and saves files in
subfolders there.
For the full list of options:

```sh
flatpak run eu.nosini.GalleryDl --help
```

## Configuration

To customize filenames, download locations, or site settings, create a
configuration file:

```sh
flatpak run eu.nosini.GalleryDl --config-create
```

Edit `~/.config/gallery-dl/config.json`, or use your existing gallery-dl
configuration there. If you set `XDG_CONFIG_HOME` on the host, its `gallery-dl`
directory is used instead. The legacy `~/.gallery-dl.conf` file is also readable.
Available settings are described
in the [configuration reference](https://gdl-org.github.io/docs/configuration.html).

See [the usage guide](docs/usage.md) for downloading to other folders, using
browser cookies, and setting up a shorter command.

## Privacy and access

The app connects to the websites you download from. By default, it can access
your gallery-dl configuration directory, the legacy `~/.gallery-dl.conf` file,
and its own private storage. Access to download folders, browser profiles, and
your desktop keyring requires additional permission.

## License

This packaging is licensed under [GNU AGPLv3](LICENSE). Upstream gallery-dl is
licensed under GPL-2.0-only, and bundled dependencies retain their own licenses.
This package is maintained separately from upstream gallery-dl.

For contributors: [building and publishing](docs/development.md).
