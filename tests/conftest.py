"""
Pytest config for PKC.

Installs Kodi API mocks before any PKC module is imported so unit tests can
run outside Kodi (CI, local dev). Individual tests can still patch specific
mock methods to assert call behavior.
"""
import sys
from pathlib import Path

# Make `resources` and project root importable as top-level packages.
ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT, ROOT / "resources" / "lib"):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

# Install Kodi mocks at collection time — must run before any
# `from resources.lib import ...` in test modules.
from tests.kodi_mocks import install_kodi_mocks  # noqa: E402

install_kodi_mocks()

# Pre-import PKC modules that tests reference via @patch('resources.lib.<mod>.X').
# unittest.mock.patch resolves dotted paths via getattr on the parent package,
# which fails if the submodule was never imported (parent is a MagicMock).
# Importing them here once makes them available as real attributes of
# `resources.lib`. Failures are tolerated — a missing module just means those
# tests will skip naturally.
for _mod in (
    "resources.lib.variables",
    "resources.lib.timing",
    "resources.lib.plex_functions",
    "resources.lib.kodimonitor",
    "resources.lib.utils",
    "resources.lib.playback",
    "resources.lib.playqueue",
):
    try:
        __import__(_mod)
    except Exception:  # noqa: BLE001
        pass
