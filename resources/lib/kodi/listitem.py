# -*- coding: utf-8 -*-
"""
Centralised ListItem / InfoTag helpers (Kodi 20+).

Background:
* On Kodi 19 we used ``ListItem.setInfo()`` and ``ListItem.addStreamInfo()``.
  Both are deprecated and will be removed in a future Kodi.
* On Kodi 20+ everything goes through the typed ``InfoTagVideo`` /
  ``InfoTagMusic`` objects (``getVideoInfoTag`` / ``getMusicInfoTag``) and
  the typed ``VideoStreamDetail`` family.

PKC v5 dropped Kodi 19 support, so this module assumes the typed API and
exists to:

* keep the call sites short (one helper instead of 15 setX() calls),
* provide a single seam to upgrade for Kodi 22 if/when the API changes again.

Currently defines the surface; call-site migration happens in Phase B/C
(``itemtypes/`` and ``transfer.py`` are the largest consumers).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import xbmcgui


@dataclass(slots=True)
class VideoStream:
    codec: str = ""
    aspect: float = 0.0
    width: int = 0
    height: int = 0
    duration: int = 0  # seconds
    stereo_mode: str = ""
    language: str = ""
    hdr_type: str = ""  # Kodi 20+: dolbyvision/hdr10/hlg/...


@dataclass(slots=True)
class AudioStream:
    codec: str = ""
    channels: int = 0
    language: str = ""


@dataclass(slots=True)
class SubtitleStream:
    language: str = ""


def add_video_stream(item: xbmcgui.ListItem, s: VideoStream) -> None:
    """Attach a video stream description to the ListItem (Kodi 20+ API)."""
    info = item.getVideoInfoTag()
    detail = xbmcgui.VideoStreamDetail(
        width=s.width,
        height=s.height,
        aspect=s.aspect,
        duration=s.duration,
        codec=s.codec,
        stereoMode=s.stereo_mode,
        language=s.language,
        hdrType=s.hdr_type,
    )
    info.addVideoStream(detail)


def add_audio_stream(item: xbmcgui.ListItem, s: AudioStream) -> None:
    info = item.getVideoInfoTag()
    info.addAudioStream(xbmcgui.AudioStreamDetail(
        channels=s.channels, codec=s.codec, language=s.language,
    ))


def add_subtitle_stream(item: xbmcgui.ListItem, s: SubtitleStream) -> None:
    info = item.getVideoInfoTag()
    info.addSubtitleStream(xbmcgui.SubtitleStreamDetail(language=s.language))


def set_resume(item: xbmcgui.ListItem, position: float, total: Optional[float] = None) -> None:
    """Set resume point (seconds). Total defaults to position*0 if unknown."""
    info = item.getVideoInfoTag()
    info.setResumePoint(position, total or 0.0)
