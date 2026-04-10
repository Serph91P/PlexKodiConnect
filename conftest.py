"""
conftest.py - Install Kodi mocks before any test collection.
This ensures xbmc/xbmcaddon/etc. are available when PKC modules are imported.
"""
from tests.kodi_mocks import install_kodi_mocks

# Install mocks at conftest load time (before collection)
install_kodi_mocks()
