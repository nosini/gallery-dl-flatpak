# Building and publishing

The packaging lives at the repository root. A local `gallery-dl/` checkout is
ignored and is not used by the build. The manifest installs release wheels
from PyPI, pinned by URL and SHA-256 in `flatpak/python-packages.json`.

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

The manifest uses Freedesktop 26.08 and Python 3.14. Builds need network access
to fetch the runtime and the pinned sources; pip installation itself is offline.
The native wheels target x86_64. Adding another architecture requires generating
matching wheels and extending the workflow.

To produce a portable installer:

```sh
flatpak build-bundle --arch=x86_64 \
  --runtime-repo=https://dl.flathub.org/repo/flathub.flatpakrepo \
  repo gallery-dl-x86_64.flatpak eu.nosini.GalleryDl stable
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
result against the Platform runtime, checks the CLI and optional Python imports,
and exercises a download and its archive using a local HTTP server.
Every successful build uploads a `gallery-dl-x86_64` artifact containing the bundle.
Builds and pull requests need no secrets.

Signed publishing is optional:

1. In **Settings → Pages**, select **GitHub Actions** as the source.
2. Add the repository Actions secret `FLATPAK_GPG_PRIVATE_KEY`, containing an
   ASCII-armored private signing key with no passphrase.
3. Add the repository Actions variable `PUBLISH_FLATPAK` with the value `true`.
4. Push to `main` or manually run the workflow on `main`.

The workflow signs the tested build and repository summary, exports the public
key into `.flatpakrepo` and `.flatpakref` files, and deploys to GitHub Pages.
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

Change the gallery-dl version in `flatpak/requirements.txt`, then resolve its
dependencies with Python 3.14 and pip:

```sh
python3.14 -m venv .venv
.venv/bin/python flatpak/generate-python-deps.py
```

Review and commit both the requirements file and the generated module, update
the version in the README, and run the Flatpak workflow. Regeneration updates
transitive dependencies too. Ordinary builds never resolve new dependency
versions.
