"""
Mock modules for Kodi Python API.
These mocks allow running PKC unit tests outside of Kodi.
"""
import sys
from unittest.mock import MagicMock, patch


def install_kodi_mocks():
    """
    Install mock Kodi modules into sys.modules so PKC code can be imported.
    Must be called before importing any PKC module.
    """
    mock_modules = {
        'xbmc': _make_xbmc_mock(),
        'xbmcaddon': _make_xbmcaddon_mock(),
        'xbmcgui': MagicMock(),
        'xbmcplugin': MagicMock(),
        'xbmcvfs': _make_xbmcvfs_mock(),
    }
    for name, mock in mock_modules.items():
        sys.modules[name] = mock
    return mock_modules


def _make_xbmc_mock():
    mock = MagicMock()
    mock.LOGDEBUG = 0
    mock.LOGINFO = 1
    mock.LOGWARNING = 2
    mock.LOGERROR = 3
    mock.LOGFATAL = 4
    mock.LOGNONE = 5

    # Monitor class
    mock.Monitor = MagicMock
    mock.Player = MagicMock

    # Common functions
    mock.log = MagicMock()
    mock.sleep = MagicMock()
    mock.executeJSONRPC = MagicMock(return_value='{"result": "OK"}')
    mock.executebuiltin = MagicMock()
    mock.getCondVisibility = MagicMock(return_value=True)
    mock.translatePath = MagicMock(side_effect=lambda x: x)
    mock.getInfoLabel = MagicMock(side_effect=lambda label: {
        'System.BuildVersion': '20.5 (20.5.0) Git:20251020-abc',
    }.get(label, ''))
    return mock


def _make_xbmcaddon_mock():
    mock = MagicMock()
    addon_mock = MagicMock()
    addon_mock.getAddonInfo = MagicMock(side_effect=lambda key: {
        'version': '4.2.0',
        'path': '/tmp/pkc_test',
        'profile': '/tmp/pkc_test/profile',
        'id': 'plugin.video.plexkodiconnect',
        'name': 'PlexKodiConnect',
    }.get(key, ''))
    # Return sensible defaults for settings read at import time
    addon_mock.getSetting = MagicMock(side_effect=lambda key: {
        'companionPort': '39005',
        'deviceName': 'PKC-Test',
        'limitindex': '50',
        'transcodeIntoH265Profile': 'false',
    }.get(key, ''))
    mock.Addon = MagicMock(return_value=addon_mock)
    return mock


def _make_xbmcvfs_mock():
    mock = MagicMock()
    mock.translatePath = MagicMock(side_effect=lambda x: x)
    mock.exists = MagicMock(return_value=True)
    mock.mkdirs = MagicMock(return_value=True)
    return mock
