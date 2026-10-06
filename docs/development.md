# Development

## Layout

- `eu.nosini.GalleryDl.yml`: the Flatpak manifest.
- `eu.nosini.GalleryDl.metainfo.xml`, `.desktop` and `.svg`: software-center
  metadata, launcher and icon.
- `requirements.txt` and `addons/addons.json`: the Python packages of the app
  and of each add-on, the input of `scripts/generate-python-deps.py`.
- `python3-requirements.json` and `addons/python3-<slug>.json`: the pinned
  Python wheels, generated from those lists.
- `addons/addons.json` also gives each add-on's ID, name, license and
  upstream. The catalog, installers, signing and the checks all read it.
- `addons/keyring/`: the desktop keyring support of the SecretStorage add-on.
- `addons/install-metadata.py`, `addons/package-mkvmerge.py`: build steps for
  the add-ons' catalog entries and for mkvmerge.
- `launcher/`: the `gallery-dl` command and the terminal launcher used by the
  application menu.
- `flathub.json`: limits the build to x86_64.
- `lint-exceptions.json`: linter errors that don't apply to a self-hosted
  repository, each with its reason.
- `tests/check-installed.sh`: checks that run inside the installed app; it
  runs `tests/check-optionals.py`, `tests/smoke-test.py` and
  `tests/test-launcher.py` there.
- `scripts/test-installed.sh`: installs a local build and runs those checks,
  then checks each add-on alone and all of them together.
- `scripts/prepare-repository.sh`: signs tested builds for publishing.
- `scripts/bundle-addons.sh`: writes a single-file bundle of each add-on.

An upstream checkout in `upstream/` is ignored by Git. It is handy for
reading the source.

## How the package works

The manifest installs gallery-dl's release wheel and its dependencies from
PyPI, pinned by URL and SHA-256. It exports the app `eu.nosini.GalleryDl` and
nine optional add-ons, each a separate runtime ref. The
[bundled-extension mechanism](https://docs.flatpak.org/en/latest/extension.html#bundled-extensions)
builds them together with the app but leaves their files out of the app's
ref, and `no-autodownload` keeps them optional. Installed add-ons are mounted
under `/app/extensions/<slug>`. `PYTHONPATH` includes their Python packages,
and `PATH` includes yt-dlp, mkvmerge and `gallery-dl-keyring`. Both refer to
Python 3.14 and have to change with the runtime's Python version.

Each Python add-on contains its own dependencies, except those gallery-dl
itself needs. Shared dependencies are pinned at the same version in every
add-on, so add-ons work on their own and together. mkvmerge is extracted
from the official x86_64 AppImage without FUSE; only the program and the
private libraries it needs are kept, and a wrapper sets its library path. The
source archive of the same version supplies its license and README. FFmpeg
comes from the runtime, and TOML and Zstandard support from Python itself.

The `launcher` module replaces pip's `gallery-dl` script with
`launcher/gallery-dl`, which runs through a copy of the runtime's Python
launcher at `/app/bin/gallery-dl-flatpak`. Programs that identify processes
by their executable can therefore tell gallery-dl apart from other Python
programs. The copy is only a small wrapper around the runtime's libpython, so
it keeps working across runtime updates on the same branch.

Before gallery-dl starts, `launcher/gallery_dl_flatpak.py` wraps
`DownloadJob.handle_directory()`. Each download folder is looked up in
`/proc/self/mountinfo`; a folder on the sandbox's temporary root filesystem
isn't shared with the host, so gallery-dl stops with the permission to grant
instead of saving files that would be lost.

The SecretStorage add-on also lets gallery-dl read site options from the
desktop keyring. This feature belongs to this package, not to upstream
gallery-dl, and doesn't change gallery-dl itself. Python imports
`usercustomize` from the add-on's site-packages at startup. It adds an import
hook that wraps `Extractor.config()` once gallery-dl loads
`gallery_dl.extractor.common`, so options missing from the configuration are
looked up in the keyring. The add-on doesn't use `sitecustomize`, because the
runtime's own `sitecustomize` adds `/app`'s site-packages and must not be
shadowed. The wrapper relies on gallery-dl internals, so CI tests it against
a real Secret Service with every gallery-dl version (see
[Checking](#checking)).

GNOME Software hides AppStream console applications, so the app is described
as a desktop application with a terminal launcher. The launcher shows
gallery-dl's help and waits for Enter before closing. The metadata module
writes each add-on's metainfo and a compressed catalog entry with Python,
since `appstreamcli` isn't available inside the SDK. Each entry `extends` the
app's ID; Flatpak adds the add-on's ref when it merges the entries into the
repository's catalog, and software centers then list the add-ons on the
app's page.

## Building

The simplest way to build is with `org.flatpak.Builder` from Flathub. It
contains flatpak-builder and the linter in the versions Flathub uses:

```sh
flatpak install --user flathub org.flatpak.Builder
flatpak run org.flatpak.Builder --user --install --install-deps-from=flathub \
  --default-branch=stable --force-clean --repo=repo build-dir eu.nosini.GalleryDl.yml
```

The build downloads the pinned sources, so it needs a network connection.
Building from a checkout installs the app from a local remote named
`eu.nosini.GalleryDl-origin`. Once the build directories are gone,
`flatpak update` warns that it can't reach it. Switch to the published
remote as the README describes, or disable it with
`flatpak remote-modify --user --disable eu.nosini.GalleryDl-origin`.

To get single-file bundles of the app and the add-ons instead of installing:

```sh
flatpak build-bundle --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
  repo gallery-dl.flatpak eu.nosini.GalleryDl stable
bash scripts/bundle-addons.sh
```

A bundle or local installation can later be moved to the published
repository: install its `.flatpakref` to add the `gallery-dl` remote, then
run `flatpak install --user --reinstall gallery-dl eu.nosini.GalleryDl`.

## Checking

CI runs the same linter checks as Flathub. Run them locally with:

```sh
alias lint='flatpak run --command=flatpak-builder-lint org.flatpak.Builder'
lint --exceptions --user-exceptions lint-exceptions.json manifest eu.nosini.GalleryDl.yml
lint appstream eu.nosini.GalleryDl.metainfo.xml
lint --exceptions --user-exceptions lint-exceptions.json repo repo
```

Only add an exception when the rule doesn't apply to a package published
outside Flathub, and say why in `lint-exceptions.json`.

To run the checks inside the installed app, build without `--install` (but
with `--repo=repo`), then run:

```sh
bash scripts/test-installed.sh
```

The script adds a `local-test` remote for `repo/`, installs the app from it
and runs `tests/check-installed.sh` with `flatpak run`, so the checks see the
Platform runtime the app runs with, not the SDK. They check that gallery-dl
reports the version of the newest metainfo release, that the requirements of
every bundled package are installed, and that no add-on's packages are in
the app. Python packages that the Platform itself provides, such as
MarkupSafe, are allowed. The smoke test downloads from a local HTTP server,
checks the download archive and checks that unshared folders are refused.
The script then installs each add-on alone, exercises it, removes it and
checks the app again, and finally checks all add-ons together. It refuses
to replace an existing installation. Afterwards, remove the test installation
with `flatpak --user uninstall eu.nosini.GalleryDl` and its add-ons, and the
remote with `flatpak --user remote-delete local-test`.

Some tests run without a Flatpak build. `tests/test-launcher.py` tests the
download folder check against gallery-dl with simulated mounts, and needs a
Python 3.14 with the pinned gallery-dl. `tests/test-addon-metadata.py`
generates the add-on catalog entries and exports them into a repository; it
needs Flatpak and the OSTree CLI. `tests/test-optionals-check.py` tests the
check for packages leaking into the app.

`tests/test-keyring.py` tests the keyring support against a real Secret
Service. It starts its own D-Bus bus and a temporary GNOME Keyring, so it
needs `dbus-daemon` and `gnome-keyring-daemon` but doesn't touch your
keyring. Install the pinned wheels into a Python 3.14 environment first:

```sh
python3.14 -m venv .venv
python3 -c 'import json, sys; [print(s["url"]) for f in sys.argv[1:] for s in json.load(open(f))["sources"]]' \
  python3-requirements.json addons/python3-secretstorage.json > .venv/wheels.txt
.venv/bin/pip install --no-deps -r .venv/wheels.txt
.venv/bin/python tests/test-keyring.py
```

## GitHub Actions

`.github/workflows/flatpak.yml` runs for pushes to `main`, pull requests and
manual runs. It lints the manifest and metainfo, builds with
[flatpak-github-actions](https://github.com/flatpak/flatpak-github-actions),
lints the exported build and runs `scripts/test-installed.sh`. It checks that
the exported software catalog links all add-ons to the app, and uploads an
installable bundle of the app and one of the add-ons as artifacts. A
separate job runs `tests/test-keyring.py` with the pinned wheels. Install a
downloaded artifact with `flatpak install --user gallery-dl-x86_64.flatpak`
and, for add-ons, for example `gallery-dl-yt-dlp-x86_64.flatpak`. Bundles are
unsigned and don't update; the published repository does.

The build is limited to x86_64 by `flathub.json`: mkvmerge comes from an
x86_64-only AppImage, and the generator pins x86_64 wheels.

### Publishing

On `main`, when the repository variable `PUBLISH_FLATPAK` is `true`, the
workflow also publishes a signed Flatpak repository to GitHub Pages. A
separate job, which never runs upstream build code, combines the tested
builds, signs the app and every add-on ref, generates and signs the software
catalog and summary, and writes `gallery-dl.flatpakrepo`,
`gallery-dl.flatpakref` and a `gallery-dl-<slug>.flatpakref` for each add-on,
with the public key embedded. Before deploying, a fresh remote that only
knows the public key must accept the result, including the catalog's links
between the app and its add-ons.

Each deployment contains only the latest build. The repository URL defaults
to `https://OWNER.github.io/REPOSITORY/`. For a custom domain, set the
`FLATPAK_REPO_URL` variable to the real URL, including the trailing slash.

To set publishing up:

1. In **Settings → Pages**, select **GitHub Actions** as the source.
2. Store the signing key as the secret `FLATPAK_GPG_PRIVATE_KEY` (see
   below).
3. Set the variable:
   `gh variable set PUBLISH_FLATPAK --body true --repo nosini/gallery-dl-flatpak`.
4. Run the workflow on `main`, or push to it.

### Signing key

The key has to be an ASCII-armored GnuPG private key without a passphrase.
An existing Flatpak signing key can be reused. To make a new one, generate
it on your own machine, outside the source checkout, in a separate GnuPG
directory:

```sh
mkdir -p -m 700 "$HOME/.gnupg-flatpak/private-keys-v1.d"
gpgconf --homedir "$HOME/.gnupg-flatpak" --create-socketdir
gpg --homedir "$HOME/.gnupg-flatpak" --batch --pinentry-mode loopback \
  --passphrase '' --quick-generate-key 'Nosini Flatpak signing' ed25519 sign 0
```

Upload it through a private temporary file, so a failed export can't upload
an empty secret:

```sh
(
  set -eu
  umask 077
  key_file=$(mktemp "$HOME/.gnupg-flatpak/export.XXXXXX")
  trap 'rm -f "$key_file"' EXIT
  gpg --homedir "$HOME/.gnupg-flatpak" --armor \
    --export-secret-keys 'Nosini Flatpak signing' > "$key_file"
  test -s "$key_file"
  gh secret set FLATPAK_GPG_PRIVATE_KEY --repo nosini/gallery-dl-flatpak < "$key_file"
)
```

Keep a backup of the key. Installed copies trust the public key from the
`.flatpakref` they were installed with, so replacing the key breaks their
updates.

### Shared remote

[flatpak-repo](https://github.com/nosini/flatpak-repo) collects the
published packages into the shared `nosini` remote. Its `apps.json` lists
gallery-dl with all nine add-ons; add new add-ons there too.

## Updating

`.github/workflows/update.yml` runs
[flatpak-external-data-checker](https://github.com/flathub-infra/flatpak-external-data-checker)
every Monday at 05:17 UTC, and on manual runs. It follows the
`x-checker-data` of the sources: every pure-Python wheel through PyPI, with
gallery-dl as the main source, and the mkvmerge AppImage and source archive
through the download pages. Wheels with native code have no checker; they
are updated by regenerating the Python modules (below). If anything is
newer, the workflow updates the pins, adds a release to the metainfo file
when gallery-dl changed, pushes the change to the `update/upstream` branch,
opens a pull request and starts the Flatpak build of that branch. Its result
shows on the pull request. Merging the pull request publishes the update.

The workflow needs **Allow GitHub Actions to create and approve pull
requests** under **Settings → Actions → General**.

To merge updates without review, set the variable `AUTO_MERGE_UPDATES` to
`true`. The workflow then waits for the build, merges the pull request when
the build, the installed-app checks and the keyring test pass, and starts
the publishing build on `main`. A failed build leaves the pull request open.

GitHub disables scheduled workflows in public repositories after 60 days
without activity. Re-enable the workflow under **Actions** if that happens.

The checker updates each wheel on its own. If a new release needs a package
or version that isn't bundled, the installed-app checks fail on the pull
request. Then regenerate the Python modules on the update branch. Add a
description to the new metainfo release when it is worth more than the
version number.

## Python dependencies

`requirements.txt` lists gallery-dl, and `addons/addons.json` the packages of
each add-on, without versions; the generated modules hold the pins. After
changing either, or to update every package including those with native
code, regenerate the modules with Python 3.14, the runtime's version:

```sh
python3.14 -m venv .venv
.venv/bin/python scripts/generate-python-deps.py
```

The script resolves the newest versions with pip for Python 3.14 on x86_64,
using wheels only. It resolves gallery-dl first, then everything together
with gallery-dl's versions fixed, then each add-on against those versions,
leaving out what gallery-dl already brings. It gives every pure-Python wheel
`x-checker-data`. If gallery-dl's version changes, add a release to the
metainfo file, or the installed-app checks fail.

This package doesn't use flatpak-pip-generator: the generator always
installs into `/app`, while the add-ons need their own prefix, and it can't
keep shared dependencies at the same version across add-ons. The script
installs prebuilt wheels for every package, also for those with native code,
which would otherwise need Rust or C toolchains to build.

To add an add-on, add it to `addons/addons.json`, and in the manifest
declare its extension, include its module and add its directories to
`PYTHONPATH` or `PATH`. Then give it a functional check in
`tests/check-optionals.py`. The catalog, installers, signing and bundles
follow the list.

## Moving to a newer runtime

Change `runtime-version` in the manifest and the image tag in
`.github/workflows/flatpak.yml` (`freedesktop-26.08`). If the new runtime
has a different Python version, change the `python3.14` paths in the
manifest and in `tests/check-installed.sh`, and the version in
`scripts/generate-python-deps.py`, then regenerate the Python modules.
mkvmerge's library list in `addons/package-mkvmerge.py` assumes what the
Freedesktop runtime provides; check it against the new runtime.
