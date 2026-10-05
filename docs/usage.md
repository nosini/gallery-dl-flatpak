# Using gallery-dl

## A shorter command

Add this alias to your shell configuration to use `gallery-dl` directly:

```sh
alias gallery-dl='flatpak run eu.nosini.GalleryDl'
```

Then view the available options with:

```sh
gallery-dl --help
```

The `-d` option selects a base directory; gallery-dl creates its usual subfolders
underneath it. Pass a destination explicitly: gallery-dl otherwise writes
relative to the current directory, which might not be accessible in the sandbox.

## Choosing a download folder

Download folders require explicit access. To use Downloads for one invocation:

```sh
flatpak run --filesystem=xdg-download:rw eu.nosini.GalleryDl \
  -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

To use another existing directory, grant access and select it as the destination:

```sh
flatpak run --filesystem=/path/to/pictures:rw eu.nosini.GalleryDl \
  -d /path/to/pictures 'URL'
```

Replace `/path/to/pictures` with your destination. This permission applies only
to that invocation. To allow the directory permanently:

```sh
flatpak override --user --filesystem=/path/to/pictures:rw eu.nosini.GalleryDl
```

For permanent access to Downloads instead:

```sh
flatpak override --user --filesystem=xdg-download:rw eu.nosini.GalleryDl
```

The folder must exist when gallery-dl starts; otherwise Flatpak ignores the
permission. Inside the sandbox, folders without access still appear to be
writable, but anything saved there is deleted when gallery-dl exits. This
package therefore makes gallery-dl refuse such a download folder and show the
permission it needs, instead of downloading files that would be lost. This
check is an addition of this package, not part of upstream gallery-dl.

Once you grant permanent access, the shell alias can download with
`gallery-dl -d /path/to/pictures 'URL'` (or your Downloads path).

## Downloading from sites that require login

You can use cookies exported from your browser in Netscape format. Put the
export in `~/.config/gallery-dl/cookies.txt` (or the host's
`$XDG_CONFIG_HOME/gallery-dl` directory), creating the directory if necessary,
then run:

```sh
flatpak run --filesystem=xdg-download:rw eu.nosini.GalleryDl \
  --cookies "${XDG_CONFIG_HOME:-$HOME/.config}/gallery-dl/cookies.txt" \
  -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

To read cookies directly from a browser, grant read access to its profile.
For a native Firefox installation using `~/.mozilla/firefox`:

```sh
flatpak run --filesystem=xdg-download:rw \
  --filesystem="$HOME/.mozilla/firefox:ro" eu.nosini.GalleryDl \
  --cookies-from-browser firefox -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

Other browser installations may store profiles elsewhere. Chromium-based
browsers may additionally require the **Desktop keyring support** add-on and
`--talk-name=org.freedesktop.secrets` to decrypt cookies. Keyring access is opt-in:

```sh
flatpak run --filesystem=xdg-download:rw --filesystem=/path/to/browser/profile:ro \
  --talk-name=org.freedesktop.secrets eu.nosini.GalleryDl \
  --cookies-from-browser chromium -d "$(xdg-user-dir DOWNLOAD)" 'URL'
```

Replace the profile path and browser name with those of your browser.

## Keeping passwords in the desktop keyring

With the **Desktop keyring support** add-on, gallery-dl can read site
usernames, passwords, API keys and tokens from your desktop keyring instead of
its configuration file.

This feature is added by this Flatpak package; upstream gallery-dl doesn't
read credentials from the keyring, and its documentation doesn't cover it.
Report problems with it to this package, not to gallery-dl.

Keyring access is opt-in, so allow it for gallery-dl:

```sh
flatpak override --user --talk-name=org.freedesktop.secrets eu.nosini.GalleryDl
```

This gives gallery-dl access to your whole keyring, not just its own entries.
Instead of the override, you can add `--talk-name=org.freedesktop.secrets`
to each `flatpak run` command.

Store a value with `gallery-dl-keyring set`, giving the site's name as used in
gallery-dl's configuration and the option name. It asks for the value without
showing it:

```sh
flatpak run --command=gallery-dl-keyring eu.nosini.GalleryDl set danbooru username
flatpak run --command=gallery-dl-keyring eu.nosini.GalleryDl set danbooru api-key
```

gallery-dl then uses these values whenever `extractor.danbooru.username` or
`extractor.danbooru.api-key` isn't set in its configuration. A value in the
configuration always takes precedence. Sites that log in with a password need
both `username` and `password`. To see which options are stored, or to remove
one:

```sh
flatpak run --command=gallery-dl-keyring eu.nosini.GalleryDl list
flatpak run --command=gallery-dl-keyring eu.nosini.GalleryDl delete danbooru api-key
```

Entries appear in keyring managers such as Seahorse as
"gallery-dl: *site* *option*". They have the attributes `application`
(`gallery-dl`), `category` (the site) and `option`, so on the host you can also
store one with `secret-tool`:

```sh
secret-tool store --label='gallery-dl: danbooru api-key' \
  application gallery-dl category danbooru option api-key
```

Your keyring might ask to be unlocked when gallery-dl reads a value. Run
gallery-dl with `-v` to see which options came from the keyring; those log
lines are marked `[flatpak-keyring]`. Values are never shown.

## Routing gallery-dl's traffic by process

Proxy clients and firewalls that apply rules per program identify gallery-dl
by its executable, `gallery-dl-flatpak` (path `/app/bin/gallery-dl-flatpak`),
rather than as a generic Python program. Use that name in rules that match
the process name, such as `PROCESS-NAME,gallery-dl-flatpak` in Clash-based
clients. Tools such as `ps`, `top` and `pgrep` still list it as `gallery-dl`.

Downloads made through the yt-dlp add-on run in the same process. Commands
started with `flatpak run --command=...` run under their own names.

## Optional features

Install gallery-dl first, then open its page in GNOME Software and choose the
features you need under **Add-ons**. Each add-on can be installed independently:

| Add-on | Feature | Installer |
| --- | --- | --- |
| yt-dlp support for gallery-dl | HLS/DASH video downloads and yt-dlp integration | [yt-dlp](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-yt-dlp.flatpakref) |
| Accurate Ugoira timecodes | mkvmerge for precise Matroska frame timing | [mkvmerge](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-mkvmerge.flatpakref) |
| SOCKS proxy support | PySocks for SOCKS proxies | [PySocks](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-pysocks.flatpakref) |
| Brotli compression support | Brotli-compressed web responses | [Brotli](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-brotli.flatpakref) |
| YAML configuration support | PyYAML for YAML configuration files | [PyYAML](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-pyyaml.flatpakref) |
| Desktop keyring support | Decrypting browser cookies, and [site passwords in the keyring](#keeping-passwords-in-the-desktop-keyring) (added by this package) | [SecretStorage](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-secretstorage.flatpakref) |
| PostgreSQL archive support | Psycopg for PostgreSQL download archives | [Psycopg](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-psycopg.flatpakref) |
| System certificate support | truststore for the runtime certificate store | [truststore](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-truststore.flatpakref) |
| Jinja template support | Jinja templates | [Jinja](https://nosini.github.io/gallery-dl-flatpak/gallery-dl-jinja.flatpakref) |

Open an installer link with your software center, or use its address with
`flatpak install`. For example:

```sh
flatpak install --user https://nosini.github.io/gallery-dl-flatpak/gallery-dl-yt-dlp.flatpakref
```

gallery-dl detects it automatically; your download commands stay the same.
Add-ons aren't installed automatically with gallery-dl. To update all installed
Flatpaks, run `flatpak update --user`. To update or remove an individual add-on,
use its ID; for example:

```sh
flatpak update --user eu.nosini.GalleryDl.YtDlp
flatpak uninstall --user eu.nosini.GalleryDl.YtDlp
```

The yt-dlp add-on includes its own Brotli dependency, so installing yt-dlp also
provides Brotli support. This package uses yt-dlp and Brotli rather than their
alternative implementations, youtube-dl and brotlicffi.

FFmpeg and ffprobe are supplied by the Flatpak runtime for Ugoira conversion.
Available codecs depend on that runtime. TOML configuration and Zstandard
web responses are supported by Python's built-in modules. These features
don't need add-ons.

Installing an add-on doesn't grant access to browser profiles, the desktop
keyring, or additional folders. Grant those permissions when needed, as shown
above. The PostgreSQL add-on supports connections over TCP using the app's
network access; a database reached through a Unix socket also needs explicit
access to its socket directory. System certificate support uses certificates
inside the sandbox; it doesn't automatically expose custom certificates
installed on the host.

Some features need additional tools that aren't included, such as
a JavaScript runtime for yt-dlp's JavaScript challenges. Programs installed on
your system are not automatically accessible inside the Flatpak, including
commands used by gallery-dl postprocessors.

See the upstream [options](https://gdl-org.github.io/docs/options.html) and
[configuration reference](https://gdl-org.github.io/docs/configuration.html)
for more ways to customize downloads.
