# -*- coding: utf-8 -*-
"""
Thin wrappers around xbmcgui dialogs and notifications.

Use these instead of importing xbmcgui directly so dialog text/icons stay
consistent and tests can stub a single module.
"""

from __future__ import annotations

from typing import Iterable, Optional

import xbmcgui

#: Default notification icon -- PKC ships its own icon.png at the addon root.
_ICON = "special://home/addons/plugin.video.plexkodiconnect/icon.png"


def notify(heading: str, message: str, *, icon: str = _ICON, time_ms: int = 5000,
           sound: bool = True) -> None:
    """Show a corner notification."""
    xbmcgui.Dialog().notification(heading, message, icon, time_ms, sound)


def yes_no(heading: str, message: str, *, yes_label: str = "", no_label: str = "",
           default_yes: bool = False) -> bool:
    """Show a yes/no dialog and return True if the user picked 'yes'."""
    return bool(xbmcgui.Dialog().yesno(
        heading, message,
        nolabel=no_label, yeslabel=yes_label,
        defaultbutton=xbmcgui.DLG_YESNO_YES_BTN if default_yes else xbmcgui.DLG_YESNO_NO_BTN,
    ))


def ok(heading: str, message: str) -> None:
    xbmcgui.Dialog().ok(heading, message)


def select(heading: str, choices: Iterable[str], *, preselect: int = -1) -> int:
    """Show a single-select list. Returns -1 on cancel."""
    return xbmcgui.Dialog().select(heading, list(choices), preselect=preselect)


def text_input(heading: str, default: str = "", *, hidden: bool = False) -> Optional[str]:
    """Show a keyboard input. Returns None on cancel."""
    kb = xbmcgui.Dialog().input(
        heading, default,
        type=xbmcgui.INPUT_ALPHANUM,
        option=xbmcgui.ALPHANUM_HIDE_INPUT if hidden else 0,
    )
    return kb if kb else None
