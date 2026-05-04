# -*- coding: utf-8 -*-
"""
Kodi runtime info (version detection, log helper, sleep).

Centralises the few ``xbmc.*`` calls that the rest of the codebase actually
needs at runtime, so the wider code can stay free of direct xbmc imports.
"""

from __future__ import annotations

import xbmc

#: Major Kodi version, e.g. 20 (Nexus), 21 (Omega), 22 (Piers).
KODI_VERSION: int = int(xbmc.getInfoLabel("System.BuildVersion").split(".", 1)[0])


def is_kodi(major: int) -> bool:
    """Return True iff running on Kodi major version ``major``."""
    return KODI_VERSION == major


def at_least(major: int) -> bool:
    """Return True iff Kodi major version is >= ``major``."""
    return KODI_VERSION >= major


def sleep(ms: int) -> None:
    """xbmc.sleep wrapper -- exists so callers can be tested without xbmc."""
    xbmc.sleep(ms)


def execute_builtin(cmd: str, wait: bool = False) -> None:
    xbmc.executebuiltin(cmd, wait)


def get_info_label(label: str) -> str:
    return xbmc.getInfoLabel(label)


def get_cond_visibility(cond: str) -> bool:
    return bool(xbmc.getCondVisibility(cond))
