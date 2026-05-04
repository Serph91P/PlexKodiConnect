# -*- coding: utf-8 -*-
"""Smoke tests for the new kodi adapter layer (Phase B scaffold)."""

from __future__ import annotations


def test_kodi_package_imports():
    from resources.lib import kodi
    assert hasattr(kodi, "dialogs")
    assert hasattr(kodi, "listitem")
    assert hasattr(kodi, "runtime")


def test_runtime_exposes_version_helpers():
    from resources.lib.kodi import runtime
    assert isinstance(runtime.KODI_VERSION, int)
    assert runtime.at_least(0) is True
    assert runtime.is_kodi(runtime.KODI_VERSION) is True


def test_dialogs_module_exposes_helpers():
    from resources.lib.kodi import dialogs
    for name in ("notify", "yes_no", "ok", "select", "text_input"):
        assert callable(getattr(dialogs, name)), f"missing helper: {name}"


def test_listitem_dataclasses_have_defaults():
    from resources.lib.kodi.listitem import VideoStream, AudioStream, SubtitleStream
    v = VideoStream()
    assert v.codec == "" and v.width == 0 and v.hdr_type == ""
    a = AudioStream()
    assert a.channels == 0
    s = SubtitleStream()
    assert s.language == ""
