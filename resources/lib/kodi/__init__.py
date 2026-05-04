# -*- coding: utf-8 -*-
"""
Kodi adapter layer (PKC v5).

Goal: keep all direct ``xbmc``/``xbmcgui``/``xbmcvfs``/``xbmcaddon``/``xbmcplugin``
calls behind this package so that:

* Plex-side code never imports xbmc directly,
* Kodi 20 -> 21 -> 22 API churn (e.g. InfoTagVideo additions, deprecated
  ``setInfo`` / ``addStreamInfo`` semantics) is patched in exactly one place,
* unit tests can swap out a single seam instead of monkey-patching dozens of
  call sites.

Status: scaffolding. Modules and call-site migration land in Phase B.
See ``STATUS.md`` and ``.hermes/plans/2026-05-03_191932-pkc-perf-stability-roadmap.md``.
"""

from . import dialogs, listitem, runtime  # noqa: F401

__all__ = ["dialogs", "listitem", "runtime"]
