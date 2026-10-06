"""Read gallery-dl site options from the desktop keyring (Secret Service).

When an extractor option such as ``password`` or ``api-key`` isn't set in the
configuration, gallery-dl looks for a Secret Service item with the attributes
``application=gallery-dl``, ``category=<site>`` and ``option=<name>``.
Configured values, including explicit ``null``, take precedence.

This module also provides the ``gallery-dl-keyring`` command for managing
those items. Both are part of the gallery-dl Flatpak package, not of upstream
gallery-dl.
"""

import argparse
import getpass
import importlib.machinery
import logging
import sys
import threading

APPLICATION = "gallery-dl"
MISSING = object()
# Unattended downloads shouldn't wait forever for an unlock prompt.
UNLOCK_TIMEOUT = 120
# Marks log lines as coming from this package, not upstream gallery-dl.
log = logging.getLogger("flatpak-keyring")


class SecretServiceStore:
    """Look up items, connecting to the Secret Service on first use.

    Item attributes are read once per process. Secrets are only requested
    for options gallery-dl asks for, which may prompt to unlock the keyring.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._items = None
        self._values = {}

    def lookup(self, category, option):
        with self._lock:
            if self._items is None:
                self._items = self._load()
            key = (category, option)
            if key not in self._items:
                return MISSING
            if key not in self._values:
                self._values[key] = self._read(category, option)
            return self._values[key]

    def _load(self):
        try:
            import secretstorage
            connection = secretstorage.dbus_init()
            found = {}
            for item in secretstorage.search_items(connection, {"application": APPLICATION}):
                attributes = item.get_attributes()
                key = (attributes.get("category"), attributes.get("option"))
                if None in key:
                    continue
                # Several collections can hold an item for the same option.
                modified = item.get_modified()
                if key not in found or modified > found[key][0]:
                    found[key] = (modified, item)
        except Exception as exc:
            # Expected without --talk-name=org.freedesktop.secrets.
            log.debug("Desktop keyring not available (%s: %s)", exc.__class__.__name__, exc)
            return {}
        log.debug("Found %d option(s) in the desktop keyring", len(found))
        return {key: item for key, (_, item) in found.items()}

    def _read(self, category, option):
        item = self._items[(category, option)]
        try:
            if item.is_locked() and item.unlock(timeout=UNLOCK_TIMEOUT):
                log.warning("Keyring unlock was cancelled; not using its '%s' for %s",
                            option, category)
                return MISSING
            value = item.get_secret().decode()
        except Exception as exc:
            log.warning("Failed to read '%s' for %s from the desktop keyring (%s: %s)",
                        option, category, exc.__class__.__name__, exc)
            return MISSING
        log.debug("Using '%s' for %s from the desktop keyring", option, category)
        return value


store = SecretServiceStore()


def patch_extractor(common):
    """Make Extractor.config() fall back to the desktop keyring."""
    original = common.Extractor.config
    if getattr(original, "__module__", None) == __name__:
        return

    def config(self, key, default=None):
        value = original(self, key, MISSING)
        if value is MISSING:
            value = store.lookup(self.category, key)
            if value is MISSING:
                return default
        return value

    config.__doc__ = original.__doc__
    common.Extractor.config = config


class _PatchingLoader:
    def __init__(self, loader):
        self.loader = loader

    def create_module(self, spec):
        return self.loader.create_module(spec)

    def exec_module(self, module):
        # Tracebacks and introspection should see the normal loader.
        module.__loader__ = module.__spec__.loader = self.loader
        self.loader.exec_module(module)
        try:
            patch_extractor(module)
        except Exception as exc:
            log.warning("The Flatpak package's keyring support is unavailable for "
                        "this gallery-dl version (%s: %s)", exc.__class__.__name__, exc)


def extractor_spec(name, path, target=None):
    """Find gallery_dl.extractor.common so that it is patched once loaded."""
    spec = importlib.machinery.PathFinder.find_spec(name, path, target)
    if spec is not None and spec.loader is not None:
        spec.loader = _PatchingLoader(spec.loader)
    return spec


# gallery-dl-keyring command

def _attributes(category=None, option=None):
    attributes = {"application": APPLICATION}
    if category is not None:
        attributes["category"] = category
    if option is not None:
        attributes["option"] = option
    return attributes


def _read_value(category, option):
    if sys.stdin.isatty():
        return getpass.getpass(f"{option} for {category}: ")
    value = sys.stdin.read()
    return value[:-1] if value.endswith("\n") else value


def _set(connection, args):
    import secretstorage
    value = _read_value(args.category, args.option)
    if not value:
        raise SystemExit("gallery-dl-keyring: Refusing to store an empty value")
    collection = secretstorage.get_default_collection(connection)
    if collection.is_locked() and collection.unlock():
        raise SystemExit("gallery-dl-keyring: Unlocking the keyring was cancelled")
    collection.create_item(
        f"gallery-dl: {args.category} {args.option}",
        _attributes(args.category, args.option),
        value.encode(), replace=True,
    )
    print(f"Stored '{args.option}' for {args.category}. gallery-dl uses it unless "
          f"extractor.{args.category}.{args.option} is set in its configuration.")


def _delete(connection, args):
    import secretstorage
    items = list(secretstorage.search_items(connection, _attributes(args.category, args.option)))
    if not items:
        raise SystemExit(f"gallery-dl-keyring: No '{args.option}' stored for {args.category}")
    for item in items:
        item.delete()
    print(f"Deleted '{args.option}' for {args.category}.")


def _list(connection, args):
    import secretstorage
    entries = set()
    for item in secretstorage.search_items(connection, _attributes()):
        attributes = item.get_attributes()
        if "category" in attributes and "option" in attributes:
            entries.add((attributes["category"], attributes["option"]))
    for category, option in sorted(entries):
        print(f"{category}\t{option}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="gallery-dl-keyring",
        description="Store gallery-dl site options, such as passwords and API keys, "
                    "in the desktop keyring. gallery-dl uses them when the option "
                    "isn't set in its configuration.",
        epilog="This command is part of the gallery-dl Flatpak package, "
               "not of upstream gallery-dl.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    command = commands.add_parser(
        "set", help="store a value, read from standard input or prompted for")
    command.add_argument("category", help="site name, as in extractor.CATEGORY")
    command.add_argument("option", help="option name, such as username or password")
    command.set_defaults(run=_set)
    command = commands.add_parser("delete", help="remove a stored value")
    command.add_argument("category")
    command.add_argument("option")
    command.set_defaults(run=_delete)
    command = commands.add_parser("list", help="list stored options without their values")
    command.set_defaults(run=_list)
    args = parser.parse_args(argv)

    import secretstorage
    from secretstorage.exceptions import PromptDismissedException, SecretServiceNotAvailableException
    try:
        try:
            connection = secretstorage.dbus_init()
        except OSError as exc:
            # SecretStorage converts some socket errors, but not a missing socket.
            raise SecretServiceNotAvailableException(str(exc)) from exc
        args.run(connection, args)
    except SecretServiceNotAvailableException as exc:
        raise SystemExit(
            f"gallery-dl-keyring: The desktop keyring is not available ({exc}). "
            "Allow access with --talk-name=org.freedesktop.secrets.")
    except PromptDismissedException:
        raise SystemExit("gallery-dl-keyring: The keyring prompt was cancelled")
    except (EOFError, KeyboardInterrupt):
        raise SystemExit(1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
