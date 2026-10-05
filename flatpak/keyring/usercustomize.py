"""Load the desktop keyring fallback when gallery-dl imports its extractors.

Python imports this module at startup because the add-on's site-packages
directory is on PYTHONPATH. The runtime's sitecustomize module is left alone.
Other Python programs in the sandbox only pay for one name comparison per import.
"""

import sys


class _KeyringHook:
    def find_spec(self, name, path, target=None):
        if name != "gallery_dl.extractor.common":
            return None
        from gallery_dl_keyring import extractor_spec
        return extractor_spec(name, path, target)


sys.meta_path.insert(0, _KeyringHook())
