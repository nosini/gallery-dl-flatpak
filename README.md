# gallery-dl Flatpak

An unofficial Flatpak package of [gallery-dl](https://codeberg.org/mikf/gallery-dl),
which downloads image galleries and collections from
[hundreds of websites](https://codeberg.org/mikf/gallery-dl/src/branch/master/docs/supportedsites.md)
in a terminal. Optional add-ons provide video downloads, SOCKS proxies, extra
configuration formats and more. The package is for x86_64 Linux.

This repository only contains the packaging. gallery-dl itself, its
documentation and its issue tracker live upstream.

## Installing

Install [Flatpak](https://flatpak.org/setup/) if you don't already have it,
then:

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user https://nosini.github.io/gallery-dl-flatpak/gallery-dl.flatpakref
```

This adds a remote named `gallery-dl`. Updates come through it like any other
Flatpak, from your software center or with:

```sh
flatpak update --user eu.nosini.GalleryDl
```

To add optional features, open gallery-dl's page in GNOME Software and choose
them under **Add-ons**. For example, to add yt-dlp video support from the
terminal instead:

```sh
flatpak install --user https://nosini.github.io/gallery-dl-flatpak/gallery-dl-yt-dlp.flatpakref
```

The [usage guide](docs/usage.md#optional-features) lists all add-ons.

gallery-dl is also available from the shared
[nosini remote](https://github.com/nosini/flatpak-repo), together with the
other packages published there.

## Using it

Replace `URL` with the address of a gallery or post:

```sh
flatpak run --filesystem=xdg-download:rw eu.nosini.GalleryDl \
  -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

This allows gallery-dl to use your Downloads folder for this one run and saves
the files in subfolders there. For the full list of options:

```sh
flatpak run eu.nosini.GalleryDl --help
```

To customize file names, download locations or site settings, create a
configuration file:

```sh
flatpak run eu.nosini.GalleryDl --config-create
```

Then edit `~/.config/gallery-dl/config.json`. The settings are described in
the [configuration reference](https://gdl-org.github.io/docs/configuration.html).

The [usage guide](docs/usage.md) explains how to download to other folders,
use browser cookies, keep passwords in the desktop keyring and set up a
shorter command.

### Differences from a regular install

- gallery-dl uses the same configuration as a regular install:
  `~/.config/gallery-dl` (or `gallery-dl` in the host's `XDG_CONFIG_HOME`)
  and the legacy `~/.gallery-dl.conf`.
- It can only save files in folders you give it access to. Other folders
  look writable inside the sandbox, but anything saved there would be lost
  when gallery-dl exits, so this package makes gallery-dl refuse them and
  name the permission it needs.
- Programs installed on your system, such as those used by postprocessors,
  aren't available inside the sandbox. FFmpeg comes with the Flatpak runtime.
- With the **Desktop keyring support** add-on, gallery-dl can read site
  passwords and API keys from the desktop keyring. This is an addition of
  this package, not an upstream gallery-dl feature.
- Firewalls and proxy clients that apply rules per program see gallery-dl as
  `gallery-dl-flatpak` rather than as a generic Python program.

## Permissions

gallery-dl has network access to download from the websites you choose. It
can read and write its configuration folder, `~/.config/gallery-dl`, and read
the legacy `~/.gallery-dl.conf` file. Links it opens, such as OAuth logins, go
to your browser through the desktop's portal.

It has no access to your download folders, browser profiles or desktop
keyring until you grant it, either for one run or permanently, as the
[usage guide](docs/usage.md) shows.

## License

The packaging files in this repository are licensed under the GNU Affero
General Public License, version 3 or later (see [LICENSE](LICENSE)).
gallery-dl itself is licensed under GPL-2.0-only, and the bundled
dependencies and add-ons keep their own licenses.

Building it yourself, publishing, and how the package works are described
in [docs/development.md](docs/development.md).
