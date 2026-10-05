# Building and publishing

The packaging lives at the repository root. A local `gallery-dl/` checkout is
ignored and is not used by the build. The manifest installs release wheels
from PyPI, pinned by URL and SHA-256 in `flatpak/python-packages.json` and the
`flatpak/*-packages.json` add-on modules. `flatpak/addons.json` lists the add-ons,
package requirements, names, and IDs used by the build and publishing scripts.

The manifest exports the application `eu.nosini.GalleryDl` and nine optional
runtime extensions on branch `stable`. The
[bundled-extension mechanism](https://docs.flatpak.org/en/latest/extension.html#bundled-extensions)
builds them together but excludes each extension's files from the application
ref. `no-autodownload` keeps extensions optional. Their files mount under
`/app/extensions/<slug>` when installed. Python search paths include the Python
extensions, and the executable search path includes yt-dlp and mkvmerge. The
Python 3.14 path must be updated when changing the runtime's Python version.

Each Python add-on includes its own dependency closure, excluding only the
packages required by the base app. Overlapping dependencies use the same pinned
versions, so add-ons can work independently and coexist. mkvmerge is extracted
without FUSE from the pinned upstream x86_64 AppImage. Only its executable and
required private libraries are packaged; the wrapper sets its library path for
that process. The pinned source archive supplies the tool's license and README.
FFmpeg comes from the runtime. TOML and Zstandard support come from Python;
the pinned urllib3 uses the standard-library Zstandard decoder.

The application has a terminal desktop launcher and icon so it can appear in
GNOME Software, which filters out AppStream console applications. The launcher
shows gallery-dl's CLI help and waits before closing. Each add-on's AppStream
`extends` field links it to the main app's ID. All catalog entries and Flatpak
bundle refs must be present in the repository's exported AppStream catalog for
software centers to offer the add-ons under the parent app.

The metadata module writes each add-on's metainfo and a compressed AppStream
catalog using Python. These text-only entries don't need icon or desktop-file
processing. Catalog generation runs inside the SDK sandbox without calling
`appstreamcli`, which is a builder-host tool. Flatpak adds each extension's
bundle ref when merging the catalogs into the repository. The main app's
desktop metadata is still composed by flatpak-builder on the build host.

To check add-on catalog generation and real repository exports without installing
the SDK, run `python3 scripts/test-addon-metadata.py`. This needs Python, Flatpak,
and the OSTree CLI. It also checks that generation works without external tools
in its search path and produces reproducible compressed catalogs.

## Local build

Install Flatpak and flatpak-builder through your distribution. Then, on x86_64:

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak-builder --user --install-deps-from=flathub --force-clean \
  --repo=repo --install build-dir flatpak/eu.nosini.GalleryDl.yml
flatpak run eu.nosini.GalleryDl --version
flatpak run --filesystem="$PWD/scripts:ro" --command=python3 \
  eu.nosini.GalleryDl "$PWD/scripts/smoke-test.py"
```

To test the base app and every add-on independently and together:

```sh
flatpak --user remote-add --if-not-exists --no-gpg-verify local-test "$PWD/repo"
bash scripts/test-addons.sh
```

The tests require a fresh installation with no add-ons already installed. They
install and remove each add-on, then leave all add-ons installed after the final
combined check. The repository catalog can also be checked after refreshing it:

```sh
flatpak build-update-repo repo
flatpak --user update --appstream local-test
python3 scripts/check-appstream.py \
  "${XDG_DATA_HOME:-$HOME/.local/share}/flatpak/appstream/local-test/x86_64/active"
```

The manifest uses Freedesktop 26.08 and Python 3.14. Builds need network access
to fetch the runtime and the pinned sources; pip installation itself is offline.
The native wheels target x86_64. Adding another architecture requires generating
matching wheels and extending the workflow.

To produce portable installers for the app and every optional add-on:

```sh
bash scripts/create-bundles.sh
```

Local `--install` builds use a temporary build repository as their update origin.
Once that repository is removed, disable its remote to avoid update errors:

```sh
flatpak remote-modify --user --disable "$(flatpak info --user --show-origin eu.nosini.GalleryDl)"
```

To switch an existing bundle or local installation to a published repository,
first install its `.flatpakref` to add the remote, then explicitly switch origins:

```sh
flatpak install --user --reinstall gallery-dl eu.nosini.GalleryDl
```

## GitHub Actions

`.github/workflows/flatpak.yml` builds on pushes to `main`, pull requests, and
manual runs. It builds in the Freedesktop 26.08 Flatpak container, installs the
result against the Platform runtime, verifies optional packages aren't bundled
in the base app, and exercises downloads and archives using a local HTTP server.
It installs each add-on alone, checks imports and functionality, removes it,
and checks that the base app is free of bundled optional packages again. Python
dependencies supplied by the runtime, such as MarkupSafe, are allowed only when
their module paths resolve under `/usr`; copies under `/app` fail the check.
It then tests all add-ons together. The checks cover compression round trips, templates,
cryptography, Psycopg's bundled libpq, and mkvmerge remuxing. They don't connect
to a live PostgreSQL server or desktop keyring.

The workflow also checks the exported catalog consumed by software centers for
all nine add-ons and their relationship to the parent app. Every successful
build uploads a `gallery-dl-x86_64` artifact for the app and a
`gallery-dl-addons-x86_64` artifact containing separate add-on bundles.
Builds and pull requests need no secrets.

To try a CI build, download the `gallery-dl-x86_64` artifact from a successful
**Flatpak** run in the repository's GitHub Actions tab. For optional features,
also download `gallery-dl-addons-x86_64`. Extract the archives, then install
the app and whichever add-on bundles you need; for example:

```sh
flatpak remote-add --user --if-not-exists flathub https://dl.flathub.org/repo/flathub.flatpakrepo
flatpak install --user ./gallery-dl-x86_64.flatpak
flatpak install --user ./gallery-dl-yt-dlp-x86_64.flatpak
```

These bundles are unsigned and need to be downloaded and installed again for
each update. The signed repository described below supports `flatpak update`.

Signed publishing is optional:

1. In **Settings → Pages**, select **GitHub Actions** as the source.
2. Add the repository Actions secret `FLATPAK_GPG_PRIVATE_KEY`, containing an
   ASCII-armored private signing key with no passphrase.
3. Add the repository Actions variable `PUBLISH_FLATPAK` with the value `true`.
4. Push to `main` or manually run the workflow on `main`.

The workflow copies the exported repository and signs the tested app ref, every
add-on ref, and its summary. Signing the exported app ref preserves the exclusion
of extension files; exporting the build directory again without those exclusions
would put optional packages back into the app. It exports the public key into
`.flatpakrepo` and `.flatpakref`
files and deploys to GitHub Pages. Each `gallery-dl-<slug>.flatpakref` installs an
extension separately, using the same repository and signing key as the app.
Before signing the repository summary, publishing resets the `appstream` and
`appstream2` refs in the copied repository and regenerates them with the signing
key. Flatpak otherwise reuses unchanged unsigned catalog commits from the test
repository without adding signatures. CI imports the public key into a fresh
test remote and pulls the signed catalog with GPG verification enabled before
deployment.
Signing secrets are used only on `main`, never for pull requests. Each deployment
contains a fresh repository with the latest build; it does not retain old refs
for rollback. The Actions bundle is an unsigned build artifact even when Pages
publishing is enabled.

The default public URL is `https://OWNER.github.io/REPOSITORY/`. For a custom
domain or an account-level Pages repository, set `FLATPAK_REPO_URL` to the actual
URL, including its trailing slash. This setting changes repository metadata;
configure the corresponding domain separately in GitHub Pages.

## Signing keys

Flatpak signing keys authenticate repository commits and summaries. A key can
sign multiple apps and repositories; it does not have to match the application
ID. Reusing an existing publisher key is valid. Separate keys are preferable
when separate repositories have independent CI secrets: compromise or rotation
of one key then affects only its repository.

Generate keys on your own machine, outside the source checkout. For a dedicated
unattended CI key, use a separate GnuPG directory:

```sh
mkdir -p -m 700 "$HOME/.gnupg-gallery-dl/private-keys-v1.d"
gpgconf --homedir "$HOME/.gnupg-gallery-dl" --create-socketdir
gpg --homedir "$HOME/.gnupg-gallery-dl" --batch --pinentry-mode loopback \
  --passphrase '' --quick-generate-key 'gallery-dl Flatpak signing' ed25519 sign 0
gpg --homedir "$HOME/.gnupg-gallery-dl" --list-secret-keys --keyid-format long
```

If generation reports `agent_genkey failed: No such file or directory`, ensure
the private-key directory above exists, then restart the dedicated agent and
retry generation:

```sh
gpgconf --homedir "$HOME/.gnupg-gallery-dl" --kill gpg-agent
gpgconf --homedir "$HOME/.gnupg-gallery-dl" --launch gpg-agent
```

If it still fails, inspect the agent's diagnostic output before proceeding.
Do not upload a secret until key generation succeeds.

Replace `OWNER` and `REPOSITORY` below. With GitHub CLI authenticated on that
machine, export the key to a private temporary file and upload only after the
export succeeds and produces data:

```sh
(
  set -eu
  umask 077
  key_file=$(mktemp "$HOME/.gnupg-gallery-dl/export.XXXXXX")
  trap 'rm -f "$key_file"' EXIT
  gpg --homedir "$HOME/.gnupg-gallery-dl" --armor \
    --export-secret-keys 'gallery-dl Flatpak signing' > "$key_file"
  test -s "$key_file"
  gh secret set FLATPAK_GPG_PRIVATE_KEY --repo OWNER/REPOSITORY < "$key_file"
)
```

After the upload succeeds, enable publishing:

```sh
gh variable set PUBLISH_FLATPAK --body true --repo OWNER/REPOSITORY
```

Keep a secure backup of the key and its revocation certificate. To reuse a
compatible existing CI signing key, export it from its existing GnuPG directory
instead. This workflow does not unlock passphrase-protected keys.

Keep the public signing identity stable after publishing. Replacing a key
without arranging client trust in its successor breaks updates for existing
installations. Flatpak documents signing in its
[builder guide](https://docs.flatpak.org/en/latest/flatpak-builder.html#signing).

## Updating dependencies

Change the gallery-dl version in `flatpak/requirements.txt` or an optional
package's requirements in `flatpak/addons.json`, then resolve dependencies with
Python 3.14 and pip:

```sh
python3.14 -m venv .venv
.venv/bin/python flatpak/generate-python-deps.py
```

The generator resolves the base app first, then all optional requirements with
those base versions constrained. It resolves each add-on against the combined
versions and omits only base packages. Review and commit the requirements and
all generated modules, and run the Flatpak workflow. Regeneration updates
transitive dependencies too. Ordinary builds never resolve new versions.

When adding a new feature, also declare its bundled extension and search path
in `flatpak/eu.nosini.GalleryDl.yml`, add its module to the manifest, and add a
functional check in `scripts/check-optionals.py`. Catalog generation, installer
links, signing, and bundle creation read the central add-on list.

To update mkvmerge, change the AppImage and source archive versions and hashes
in `flatpak/mkvmerge.json`. Verify the extracted binary's library closure and
run the runtime checks; upstream AppImages may change their platform library
requirements.
