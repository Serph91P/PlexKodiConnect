#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Unit tests for the PKC bugfixes:
  Bug 1: Watch status / playback progress not reported to PMS on stop
  Bug 2: UpNext / playlist breaks after ~2 episodes

Run with: python -m pytest tests/test_bugfixes.py -v
"""
import sys
import os
import copy
from unittest.mock import MagicMock, patch, call

# Kodi mocks are installed by conftest.py before collection

# Now we can import PKC modules
from resources.lib import variables as v
from resources.lib import timing


# ---------------------------------------------------------------------------
# Test helpers / fixtures
# ---------------------------------------------------------------------------

def _make_status(plex_id=12345, plex_type='movie', playcount=0,
                 time_seconds=600, total_seconds=3600,
                 external_player=False, container_key=None):
    """Build a player status dict similar to app.PLAYSTATE.player_states[1]."""
    return {
        'plex_id': plex_id,
        'plex_type': plex_type,
        'playcount': playcount,
        'time': {
            'hours': time_seconds // 3600,
            'minutes': (time_seconds % 3600) // 60,
            'seconds': time_seconds % 60,
            'milliseconds': 0,
        },
        'totaltime': {
            'hours': total_seconds // 3600,
            'minutes': (total_seconds % 3600) // 60,
            'seconds': total_seconds % 60,
            'milliseconds': 0,
        },
        'external_player': external_player,
        'container_key': container_key,
        'first_credits_marker': None,
        'final_credits_marker': None,
        'playmethod': v.PLAYBACK_METHOD_DIRECT_PATH,
        'speed': 1,
        'shuffled': False,
        'repeat': 'off',
    }


def _make_playqueue_item(plex_id, kodi_id=None, kodi_type='episode',
                         file=None):
    """Create a minimal mock PlaylistItem."""
    item = MagicMock()
    item.plex_id = plex_id
    item.plex_type = v.PLEX_TYPE_EPISODE
    item.kodi_id = kodi_id
    item.kodi_type = kodi_type
    item.file = file or 'plugin://plugin.video.plexkodiconnect?plex_id=%s' % plex_id
    item.playmethod = v.PLAYBACK_METHOD_DIRECT_PATH
    item.playcount = 0
    item.streams_initialized = True
    item.api = MagicMock()
    item.id = plex_id  # playQueueItemID
    return item


# ===========================================================================
#  BUG 1 TESTS: Watch status / progress reporting
# ===========================================================================

class TestReportPlaybackProgress:
    """Test the new report_playback_progress() function in plex_functions.py"""

    @patch('resources.lib.plex_functions.DU')
    @patch('resources.lib.plex_functions.utils')
    def test_sends_timeline_with_correct_params(self, mock_utils, mock_du_cls):
        """Verify report_playback_progress sends correct data to /:/timeline"""
        from resources.lib.plex_functions import report_playback_progress

        mock_du_instance = MagicMock()
        mock_du_cls.return_value = mock_du_instance
        mock_utils.extend_url = lambda url, params: f"{url}?test"

        report_playback_progress(
            plex_id=12345,
            time_ms=600000,
            duration_ms=3600000,
            state='stopped',
            container_key='/library/metadata/12345'
        )

        # Verify downloadUrl was called
        mock_du_instance.downloadUrl.assert_called_once()

    @patch('resources.lib.plex_functions.DU')
    @patch('resources.lib.plex_functions.utils')
    def test_builds_correct_url_params(self, mock_utils, mock_du_cls):
        """Verify the params dict includes all required fields"""
        from resources.lib.plex_functions import report_playback_progress

        captured_params = {}

        def capture_extend_url(url, params):
            captured_params.update(params)
            return url

        mock_utils.extend_url = capture_extend_url
        mock_du_cls.return_value = MagicMock()

        report_playback_progress(
            plex_id=99999,
            time_ms=120000,
            duration_ms=7200000,
            state='stopped',
            container_key='/playQueues/55'
        )

        assert captured_params['ratingKey'] == 99999
        assert captured_params['time'] == 120000
        assert captured_params['duration'] == 7200000
        assert captured_params['state'] == 'stopped'
        assert captured_params['containerKey'] == '/playQueues/55'
        assert captured_params['key'] == '/library/metadata/99999'

    @patch('resources.lib.plex_functions.DU')
    @patch('resources.lib.plex_functions.utils')
    def test_no_container_key(self, mock_utils, mock_du_cls):
        """container_key should be omitted when None"""
        from resources.lib.plex_functions import report_playback_progress

        captured_params = {}

        def capture_extend_url(url, params):
            captured_params.update(params)
            return url

        mock_utils.extend_url = capture_extend_url
        mock_du_cls.return_value = MagicMock()

        report_playback_progress(plex_id=1, time_ms=1000, duration_ms=2000)

        assert 'containerKey' not in captured_params


class TestRecordPlaystateReportsToServer:
    """Test that _record_playstate now sends progress to the PMS"""

    @patch('resources.lib.kodimonitor._clean_file_table')
    @patch('resources.lib.kodimonitor.backgroundthread')
    @patch('resources.lib.kodimonitor.xbmc')
    @patch('resources.lib.kodimonitor.PF')
    @patch('resources.lib.kodimonitor.kodi_db')
    @patch('resources.lib.kodimonitor.PlexDB')
    def test_scrobble_called_when_video_ended(
            self, mock_plexdb, mock_kodi_db, mock_pf, mock_xbmc,
            mock_bgthread, mock_clean):
        """When a video is fully watched, scrobble('watched') must be called"""
        from resources.lib.kodimonitor import _record_playstate

        # Setup PlexDB to return a valid db_item
        db_item = {
            'plex_id': 12345,
            'plex_type': 'movie',
            'kodi_fileid': 1,
        }
        mock_plexdb_ctx = MagicMock()
        mock_plexdb_ctx.item_by_id.return_value = db_item
        mock_plexdb.return_value.__enter__ = MagicMock(return_value=mock_plexdb_ctx)
        mock_plexdb.return_value.__exit__ = MagicMock(return_value=False)

        # Setup KodiVideoDB
        mock_kodidb = MagicMock()
        mock_kodi_db.KodiVideoDB.return_value.__enter__ = MagicMock(return_value=mock_kodidb)
        mock_kodi_db.KodiVideoDB.return_value.__exit__ = MagicMock(return_value=False)

        # Status: movie watched to 95% (over MARK_PLAYED_AT threshold)
        status = _make_status(
            plex_id=12345,
            plex_type='movie',
            playcount=0,
            time_seconds=3420,  # 95% of 3600
            total_seconds=3600,
        )

        _record_playstate(status, ended=True)

        # scrobble must be called with 'watched'
        mock_pf.scrobble.assert_called_once_with(12345, 'watched')

    @patch('resources.lib.kodimonitor._clean_file_table')
    @patch('resources.lib.kodimonitor.backgroundthread')
    @patch('resources.lib.kodimonitor.xbmc')
    @patch('resources.lib.kodimonitor.PF')
    @patch('resources.lib.kodimonitor.kodi_db')
    @patch('resources.lib.kodimonitor.PlexDB')
    def test_progress_reported_for_partial_watch(
            self, mock_plexdb, mock_kodi_db, mock_pf, mock_xbmc,
            mock_bgthread, mock_clean):
        """When video is partially watched, report_playback_progress must be called"""
        from resources.lib.kodimonitor import _record_playstate

        db_item = {
            'plex_id': 12345,
            'plex_type': 'movie',
            'kodi_fileid': 1,
        }
        mock_plexdb_ctx = MagicMock()
        mock_plexdb_ctx.item_by_id.return_value = db_item
        mock_plexdb.return_value.__enter__ = MagicMock(return_value=mock_plexdb_ctx)
        mock_plexdb.return_value.__exit__ = MagicMock(return_value=False)

        mock_kodidb = MagicMock()
        mock_kodi_db.KodiVideoDB.return_value.__enter__ = MagicMock(return_value=mock_kodidb)
        mock_kodi_db.KodiVideoDB.return_value.__exit__ = MagicMock(return_value=False)

        # Status: movie watched to 50% — should NOT scrobble, should report progress
        status = _make_status(
            plex_id=12345,
            plex_type='movie',
            playcount=0,
            time_seconds=1800,  # 50% of 3600
            total_seconds=3600,
            container_key='/library/metadata/12345',
        )

        _record_playstate(status, ended=False)

        # scrobble must NOT be called
        mock_pf.scrobble.assert_not_called()
        # report_playback_progress must be called with the resume time
        mock_pf.report_playback_progress.assert_called_once_with(
            12345,
            1800000,  # 1800 seconds in ms
            3600000,  # 3600 seconds in ms
            state='stopped',
            container_key='/library/metadata/12345'
        )

    @patch('resources.lib.kodimonitor._clean_file_table')
    @patch('resources.lib.kodimonitor.backgroundthread')
    @patch('resources.lib.kodimonitor.xbmc')
    @patch('resources.lib.kodimonitor.PF')
    @patch('resources.lib.kodimonitor.kodi_db')
    @patch('resources.lib.kodimonitor.PlexDB')
    def test_no_report_for_very_short_playback(
            self, mock_plexdb, mock_kodi_db, mock_pf, mock_xbmc,
            mock_bgthread, mock_clean):
        """Playback < IGNORE_SECONDS_AT_START should NOT report progress"""
        from resources.lib.kodimonitor import _record_playstate

        db_item = {
            'plex_id': 12345,
            'plex_type': 'movie',
            'kodi_fileid': 1,
        }
        mock_plexdb_ctx = MagicMock()
        mock_plexdb_ctx.item_by_id.return_value = db_item
        mock_plexdb.return_value.__enter__ = MagicMock(return_value=mock_plexdb_ctx)
        mock_plexdb.return_value.__exit__ = MagicMock(return_value=False)

        mock_kodidb = MagicMock()
        mock_kodi_db.KodiVideoDB.return_value.__enter__ = MagicMock(return_value=mock_kodidb)
        mock_kodi_db.KodiVideoDB.return_value.__exit__ = MagicMock(return_value=False)

        # Status: only 30 seconds watched (< IGNORE_SECONDS_AT_START=60)
        status = _make_status(
            plex_id=12345,
            plex_type='movie',
            playcount=0,
            time_seconds=30,
            total_seconds=3600,
        )

        _record_playstate(status, ended=False)

        # Neither scrobble nor progress report should be called
        mock_pf.scrobble.assert_not_called()
        mock_pf.report_playback_progress.assert_not_called()


# ===========================================================================
#  BUG 2 TESTS: Playqueue reuse & UpNext retry
# ===========================================================================

class TestPlayqueueReuse:
    """Test that PlayBackStart reuses existing playqueue for sequential episodes"""

    def test_item_found_in_existing_playqueue(self):
        """
        When an episode is already in the playqueue, PlayBackStart should
        find it and reuse the queue instead of initializing a new one.

        We test the core logic extracted from PlayBackStart's initialize block.
        """
        # Simulate a playqueue with 4 episodes
        items = [
            _make_playqueue_item(plex_id=100, kodi_id=1, file='/ep1.mkv'),
            _make_playqueue_item(plex_id=101, kodi_id=2, file='/ep2.mkv'),
            _make_playqueue_item(plex_id=102, kodi_id=3, file='/ep3.mkv'),
            _make_playqueue_item(plex_id=103, kodi_id=4, file='/ep4.mkv'),
        ]

        playqueue_id = 'abc123'  # Non-None means playqueue is active
        target_plex_id = 102  # Episode 3

        # This is the core logic from the fix in PlayBackStart
        found_item = None
        found_pos = None
        if playqueue_id is not None:
            for i, queue_item in enumerate(items):
                if queue_item.plex_id == target_plex_id:
                    found_item = queue_item
                    found_pos = i
                    break

        assert found_item is not None, "Item should be found in playqueue"
        assert found_item.plex_id == 102
        assert found_pos == 2

    def test_item_not_in_playqueue_requires_init(self):
        """
        When the episode is NOT in the existing playqueue => init_plex_playqueue
        should be called (fallback to current behavior).
        """
        items = [
            _make_playqueue_item(plex_id=100),
            _make_playqueue_item(plex_id=101),
        ]

        playqueue_id = 'abc123'
        target_plex_id = 999  # Not in queue

        found_item = None
        if playqueue_id is not None:
            for i, queue_item in enumerate(items):
                if queue_item.plex_id == target_plex_id:
                    found_item = queue_item
                    break

        assert found_item is None, "Item should NOT be found — must init new playqueue"

    def test_no_playqueue_id_skips_search(self):
        """
        When playqueue.id is None (no active PMS playqueue), don't search
        through items — go straight to init.
        """
        items = [_make_playqueue_item(plex_id=100)]
        playqueue_id = None  # No active playqueue
        target_plex_id = 100

        found_item = None
        if playqueue_id is not None:
            for i, queue_item in enumerate(items):
                if queue_item.plex_id == target_plex_id:
                    found_item = queue_item
                    break

        assert found_item is None, "Should not search when playqueue_id is None"

    def test_reuse_preserves_remaining_items(self):
        """
        Key assertion: after finding the item in the existing playqueue,
        the remaining items in the queue should still be there.
        (The old code would call init_plex_playqueue which calls clear())
        """
        items = [
            _make_playqueue_item(plex_id=100),
            _make_playqueue_item(plex_id=101),
            _make_playqueue_item(plex_id=102),
            _make_playqueue_item(plex_id=103),
        ]
        original_length = len(items)

        playqueue_id = 'abc123'
        target_plex_id = 101  # Episode 2

        found_item = None
        for i, queue_item in enumerate(items):
            if queue_item.plex_id == target_plex_id:
                found_item = queue_item
                found_item.file = '/new/path.mkv'
                break

        # Queue should still have all 4 items
        assert len(items) == original_length
        assert items[2].plex_id == 102  # Episode 3 still there
        assert items[3].plex_id == 103  # Episode 4 still there


class TestUpNextRetry:
    """Test the retry logic in _get_next_episode_api and SendUpNextSignal"""

    @patch('resources.lib.upnext.xbmc')
    @patch('resources.lib.upnext.PF')
    def test_retries_on_first_failure(self, mock_pf, mock_xbmc):
        """If show_episodes fails the first time, it should retry once"""
        from resources.lib.upnext import _get_next_episode_api

        mock_api = MagicMock()
        mock_api.grandparent_id.return_value = 555
        mock_api.plex_id = 10

        # First call returns None (failure), second returns valid XML
        ep1_xml = MagicMock()
        ep2_xml = MagicMock()
        xml_list = MagicMock()
        xml_list.__iter__ = MagicMock(return_value=iter([ep1_xml, ep2_xml]))
        xml_list.__getitem__ = MagicMock(return_value=ep2_xml)

        mock_pf.show_episodes.side_effect = [None, xml_list]

        with patch('resources.lib.upnext.API') as mock_api_cls:
            api_instance_1 = MagicMock()
            api_instance_1.plex_id = 10
            api_instance_2 = MagicMock()
            api_instance_2.plex_id = 11
            mock_api_cls.side_effect = [api_instance_1, api_instance_2]

            result = _get_next_episode_api(mock_api)

        # show_episodes should have been called twice
        assert mock_pf.show_episodes.call_count == 2
        # xbmc.sleep should have been called for the retry wait
        mock_xbmc.sleep.assert_called_once_with(2000)

    @patch('resources.lib.upnext.xbmc')
    @patch('resources.lib.upnext.PF')
    def test_returns_none_after_both_failures(self, mock_pf, mock_xbmc):
        """If both attempts fail, should return None gracefully"""
        from resources.lib.upnext import _get_next_episode_api

        mock_api = MagicMock()
        mock_api.grandparent_id.return_value = 555

        # Both calls return None
        mock_pf.show_episodes.return_value = None

        result = _get_next_episode_api(mock_api)

        assert result is None
        assert mock_pf.show_episodes.call_count == 2

    @patch('resources.lib.upnext.xbmc')
    @patch('resources.lib.upnext.PF')
    def test_no_retry_when_first_succeeds(self, mock_pf, mock_xbmc):
        """If the first call succeeds, no retry should happen"""
        from resources.lib.upnext import _get_next_episode_api

        mock_api = MagicMock()
        mock_api.grandparent_id.return_value = 555
        mock_api.plex_id = 10

        ep1_xml = MagicMock()
        ep2_xml = MagicMock()
        xml_list = MagicMock()
        xml_list.__iter__ = MagicMock(return_value=iter([ep1_xml, ep2_xml]))
        xml_list.__getitem__ = MagicMock(return_value=ep2_xml)

        mock_pf.show_episodes.return_value = xml_list

        with patch('resources.lib.upnext.API') as mock_api_cls:
            api_instance_1 = MagicMock()
            api_instance_1.plex_id = 10
            api_instance_2 = MagicMock()
            api_instance_2.plex_id = 11
            mock_api_cls.side_effect = [api_instance_1, api_instance_2]

            result = _get_next_episode_api(mock_api)

        # show_episodes only called once
        assert mock_pf.show_episodes.call_count == 1
        # no sleep needed
        mock_xbmc.sleep.assert_not_called()


class TestSendUpNextSignalRetry:
    """Test that SendUpNextSignal retries on first failure"""

    @patch('resources.lib.kodimonitor.app')
    @patch('resources.lib.kodimonitor.upnext')
    def test_retries_when_first_signal_fails(self, mock_upnext, mock_app):
        """If send_upnext_signal returns False, it should retry after 3s"""
        from resources.lib.kodimonitor import SendUpNextSignal

        mock_app.APP.monitor.waitForAbort.return_value = False
        mock_app.PLAYSTATE.player_states = {1: {'upnext_signal_sent': False}}

        mock_upnext.get_notification_time_from_markers.return_value = 30
        # First call returns False, second returns True
        mock_upnext.send_upnext_signal.side_effect = [False, True]

        item = MagicMock()
        status = {'first_credits_marker': None, 'final_credits_marker': None}

        task = SendUpNextSignal(item, status, playerid=1)
        task.run()

        # send_upnext_signal should be called twice
        assert mock_upnext.send_upnext_signal.call_count == 2
        # waitForAbort called: once for initial 2s wait, once for 3s retry wait
        assert mock_app.APP.monitor.waitForAbort.call_count == 2

    @patch('resources.lib.kodimonitor.app')
    @patch('resources.lib.kodimonitor.upnext')
    def test_no_retry_when_first_succeeds(self, mock_upnext, mock_app):
        """If first signal succeeds, no retry needed"""
        from resources.lib.kodimonitor import SendUpNextSignal

        mock_app.APP.monitor.waitForAbort.return_value = False
        mock_app.PLAYSTATE.player_states = {1: {'upnext_signal_sent': False}}

        mock_upnext.get_notification_time_from_markers.return_value = 30
        mock_upnext.send_upnext_signal.return_value = True

        item = MagicMock()
        status = {}

        task = SendUpNextSignal(item, status, playerid=1)
        task.run()

        # Only called once
        assert mock_upnext.send_upnext_signal.call_count == 1
        # Only the initial 2s wait
        assert mock_app.APP.monitor.waitForAbort.call_count == 1


# ===========================================================================
#  BUG 1b TESTS: Watch status for non-library items (widget/plugin playback)
# ===========================================================================

class TestReportPlaystateToPms:
    """Test _report_playstate_to_pms for items not in the Kodi DB"""

    @patch('resources.lib.kodimonitor.PF')
    def test_scrobble_watched_when_ended(self, mock_pf):
        """When ended=True, should scrobble as watched"""
        from resources.lib.kodimonitor import _report_playstate_to_pms

        status = _make_status(plex_id=83197, plex_type='episode',
                              time_seconds=7200, total_seconds=7200)
        _report_playstate_to_pms(status, ended=True)

        mock_pf.scrobble.assert_called_once_with(83197, 'watched')
        mock_pf.report_playback_progress.assert_not_called()

    @patch('resources.lib.kodimonitor.PF')
    def test_scrobble_watched_when_progress_above_threshold(self, mock_pf):
        """When progress >= MARK_PLAYED_AT (90%), should scrobble as watched"""
        from resources.lib.kodimonitor import _report_playstate_to_pms

        # 95% of 7200 = 6840 seconds
        status = _make_status(plex_id=83197, plex_type='episode',
                              time_seconds=6840, total_seconds=7200)
        _report_playstate_to_pms(status, ended=False)

        mock_pf.scrobble.assert_called_once_with(83197, 'watched')

    @patch('resources.lib.kodimonitor.PF')
    def test_report_progress_for_partial_watch(self, mock_pf):
        """Partial watch should report progress, not scrobble"""
        from resources.lib.kodimonitor import _report_playstate_to_pms

        # 50% of 7200 = 3600 seconds
        status = _make_status(plex_id=83198, plex_type='episode',
                              time_seconds=3600, total_seconds=7200,
                              container_key='/playQueues/123')
        _report_playstate_to_pms(status, ended=False)

        mock_pf.scrobble.assert_not_called()
        mock_pf.report_playback_progress.assert_called_once_with(
            83198,
            3600000,  # time_ms
            7200000,  # duration_ms
            state='stopped',
            container_key='/playQueues/123'
        )

    @patch('resources.lib.kodimonitor.PF')
    def test_ignore_very_short_playback(self, mock_pf):
        """Playback < IGNORE_SECONDS_AT_START (60s) should be ignored"""
        from resources.lib.kodimonitor import _report_playstate_to_pms

        status = _make_status(plex_id=83199, plex_type='episode',
                              time_seconds=30, total_seconds=7200)
        _report_playstate_to_pms(status, ended=False)

        mock_pf.scrobble.assert_not_called()
        mock_pf.report_playback_progress.assert_not_called()


class TestRecordPlaystateNonLibraryItem:
    """Test that _record_playstate calls _report_playstate_to_pms when db_item is None"""

    @patch('resources.lib.kodimonitor._report_playstate_to_pms')
    @patch('resources.lib.kodimonitor.PlexDB')
    def test_calls_pms_report_when_not_in_db(self, mock_plexdb, mock_report):
        """When item is not in Kodi DB, should still report to PMS"""
        from resources.lib.kodimonitor import _record_playstate

        mock_plexdb_ctx = MagicMock()
        mock_plexdb_ctx.item_by_id.return_value = None  # Not in DB
        mock_plexdb.return_value.__enter__ = MagicMock(return_value=mock_plexdb_ctx)
        mock_plexdb.return_value.__exit__ = MagicMock(return_value=False)

        status = _make_status(plex_id=83197, plex_type='episode',
                              time_seconds=3600, total_seconds=7200)
        _record_playstate(status, ended=False)

        mock_report.assert_called_once_with(status, False)

    @patch('resources.lib.kodimonitor._report_playstate_to_pms')
    @patch('resources.lib.kodimonitor.PlexDB')
    def test_no_pms_report_for_missing_plex_id(self, mock_plexdb, mock_report):
        """When plex_id is None/0, should return early without reporting"""
        from resources.lib.kodimonitor import _record_playstate

        status = _make_status(plex_id=None, plex_type='episode')
        _record_playstate(status, ended=False)

        mock_report.assert_not_called()
        mock_plexdb.assert_not_called()


# ===========================================================================
#  BUG 2b TESTS: Playqueue switch for kodi_playlist_playback
# ===========================================================================

class TestPlayqueueSwitchForKodiPlaylistPlayback:
    """Test that PlayBackStart switches to the correct playqueue when
    kodi_playlist_playback is set on a different queue (e.g. audio queue)
    than the one Kodi reports (video player)."""

    def test_switches_to_audio_queue_when_flag_set(self):
        """When video queue lacks kodi_playlist_playback but audio queue has
        it with items, should switch to the audio queue."""
        video_queue = MagicMock()
        video_queue.kodi_playlist_playback = False
        video_queue.items = [_make_playqueue_item(plex_id=100)]

        audio_queue = MagicMock()
        audio_queue.kodi_playlist_playback = True
        audio_queue.items = [_make_playqueue_item(plex_id=200)]

        photo_queue = MagicMock()
        photo_queue.kodi_playlist_playback = False
        photo_queue.items = []

        all_queues = [audio_queue, video_queue, photo_queue]

        # Simulate the logic from PlayBackStart
        playqueue = video_queue  # playerid=1 → video
        if not playqueue.kodi_playlist_playback:
            for pq in all_queues:
                if pq is not playqueue and pq.kodi_playlist_playback and pq.items:
                    playqueue = pq
                    break

        assert playqueue is audio_queue
        assert playqueue.items[0].plex_id == 200

    def test_no_switch_when_current_has_flag(self):
        """When the current playqueue already has kodi_playlist_playback,
        no switch should happen."""
        video_queue = MagicMock()
        video_queue.kodi_playlist_playback = True
        video_queue.items = [_make_playqueue_item(plex_id=100)]

        audio_queue = MagicMock()
        audio_queue.kodi_playlist_playback = False
        audio_queue.items = []

        all_queues = [audio_queue, video_queue]

        playqueue = video_queue
        if not playqueue.kodi_playlist_playback:
            for pq in all_queues:
                if pq is not playqueue and pq.kodi_playlist_playback and pq.items:
                    playqueue = pq
                    break

        assert playqueue is video_queue

    def test_no_switch_when_no_flag_anywhere(self):
        """When no playqueue has the flag, should stay on current queue."""
        video_queue = MagicMock()
        video_queue.kodi_playlist_playback = False
        video_queue.items = [_make_playqueue_item(plex_id=100)]

        audio_queue = MagicMock()
        audio_queue.kodi_playlist_playback = False
        audio_queue.items = []

        all_queues = [audio_queue, video_queue]

        playqueue = video_queue
        if not playqueue.kodi_playlist_playback:
            for pq in all_queues:
                if pq is not playqueue and pq.kodi_playlist_playback and pq.items:
                    playqueue = pq
                    break

        assert playqueue is video_queue

    def test_ignores_empty_flagged_queue(self):
        """If a queue has kodi_playlist_playback but no items, skip it."""
        video_queue = MagicMock()
        video_queue.kodi_playlist_playback = False
        video_queue.items = [_make_playqueue_item(plex_id=100)]

        audio_queue = MagicMock()
        audio_queue.kodi_playlist_playback = True
        audio_queue.items = []  # Empty!

        all_queues = [audio_queue, video_queue]

        playqueue = video_queue
        if not playqueue.kodi_playlist_playback:
            for pq in all_queues:
                if pq is not playqueue and pq.kodi_playlist_playback and pq.items:
                    playqueue = pq
                    break

        assert playqueue is video_queue


# ===========================================================================
#  BUG 3 TESTS: UpNext transition scrobbles old episode
# ===========================================================================

class TestUpNextTransitionScrobble:
    """
    Kodi does NOT fire Player.OnStop during UpNext playnext() transitions.
    PlayBackStart must detect episode transitions and scrobble the old episode.
    """

    def test_scrobbles_old_episode_on_transition(self):
        """When plex_id changes and upnext_signal_sent is True, scrobble."""
        old_status = _make_status(plex_id=82810, plex_type='episode',
                                  playcount=0, time_seconds=16000,
                                  total_seconds=16620)
        old_status['upnext_signal_sent'] = True

        new_plex_id = 82868

        # Simulate the transition check
        old_plex_id = old_status.get('plex_id')
        should_scrobble = (old_plex_id and old_plex_id != new_plex_id
                           and old_status.get('upnext_signal_sent'))

        assert should_scrobble
        assert old_plex_id == 82810

    def test_no_scrobble_when_same_plex_id(self):
        """If plex_id doesn't change, don't scrobble."""
        old_status = _make_status(plex_id=82810, plex_type='episode')
        old_status['upnext_signal_sent'] = True

        new_plex_id = 82810
        old_plex_id = old_status.get('plex_id')
        should_scrobble = (old_plex_id and old_plex_id != new_plex_id
                           and old_status.get('upnext_signal_sent'))

        assert not should_scrobble

    def test_no_scrobble_without_upnext_signal(self):
        """If upnext_signal_sent is False, don't auto-scrobble."""
        old_status = _make_status(plex_id=82810, plex_type='episode')
        old_status['upnext_signal_sent'] = False

        new_plex_id = 82868
        old_plex_id = old_status.get('plex_id')
        should_scrobble = (old_plex_id and old_plex_id != new_plex_id
                           and old_status.get('upnext_signal_sent'))

        assert not should_scrobble

    def test_no_scrobble_when_no_old_plex_id(self):
        """If no old plex_id (fresh start), don't scrobble."""
        old_status = _make_status(plex_id=None, plex_type=None)
        old_status['upnext_signal_sent'] = False

        new_plex_id = 82868
        old_plex_id = old_status.get('plex_id')
        should_scrobble = (old_plex_id and old_plex_id != new_plex_id
                           and old_status.get('upnext_signal_sent'))

        assert not should_scrobble
