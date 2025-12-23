# PlexKodiConnect Kodi 21 Testing Checkliste

**Test-System:** LibreELEC 12.2.1 mit Kodi 21.3 Omega  
**PKC Version:** 3.11.2 (+ Phase 1+2 Fixes)  
**Datum:** 22. Dezember 2025

---

## ✅ Phase 1 & 2 Fixes - Verification

### 1. Lokale Server HTTP-Erkennung
- [ ] Server-Setup mit privatem IP durchführen
- [ ] User-Dialog "HTTP verwenden?" erscheint
- [ ] HTTP wird korrekt in Settings gespeichert
- [ ] 4K HDR Content spielt direkt ab (kein Transcoding)
- [ ] Bandwidth-Check: Keine 40 Mbps Limits
- [ ] Log-Check: Server URL ist `http://192.168.x.x:32400`

### 2. ListItem API Modernisierung
- [ ] Widgets laden ohne Deprecated-Warnings
- [ ] "Recently Added" Widget zeigt Content
- [ ] "On Deck" Widget funktioniert
- [ ] "Continue Watching" aktualisiert sich
- [ ] Video-Metadata korrekt angezeigt (Titel, Plot, Jahr, etc.)
- [ ] Cast & Crew Informationen vorhanden
- [ ] Log-Check: Keine `setInfo()` Warnings von PKC

### 3. Stream Info API
- [ ] Video-Streams: Codec, Resolution, HDR-Info korrekt
- [ ] Audio-Streams: Codec, Kanäle, Sprache korrekt
- [ ] Untertitel-Streams: Sprachen korrekt angezeigt
- [ ] Multi-Audio Content: Stream-Auswahl funktioniert
- [ ] Log-Check: Keine `addStreamInfo()` Warnings von PKC

### 4. Playlist-Crash Fix
- [ ] M3U Playlists syncen ohne Crash
- [ ] Plex Collections werden korrekt synchronisiert
- [ ] Leere Playlist-Einträge werden übersprungen
- [ ] Log-Check: Keine `kodiid_from_filename()` Errors

---

## 🎬 Playback Testing

### Direct Play (Lokal)
- [ ] 4K HDR10 Content (z.B. Dune 2)
- [ ] 4K DV (Dolby Vision) Content
- [ ] 1080p Content
- [ ] HEVC / H.265 Codec
- [ ] H.264 Codec
- [ ] TrueHD Atmos Audio
- [ ] DTS-HD MA Audio
- [ ] Resume-Funktion funktioniert
- [ ] Watched-Status wird korrekt gesetzt

### Transcode (wenn nötig)
- [ ] Subtitle-Transcode funktioniert
- [ ] Audio-Transcode bei inkompatiblen Formaten
- [ ] Bandbreiten-Limit wird respektiert
- [ ] Transcoding-Status in Plex Dashboard sichtbar

### Edge Cases
- [ ] Sehr große Dateien (>50 GB Remux)
- [ ] 10-bit HEVC Content
- [ ] AV1 Codec (falls vorhanden)
- [ ] Multi-Episode Files
- [ ] ISOs / Disc Images

---

## 📚 Library Sync

### Initial Sync
- [ ] Vollständiger Sync ohne Fehler
- [ ] Alle Sektionen syncen (Filme, Serien, Musik)
- [ ] Sync-Zeit akzeptabel (<5 Min für mittelgroße Library)
- [ ] Kodi DB Größe korrekt (~50 MB+)
- [ ] Artwork wird geladen
- [ ] Collections werden erstellt

### Inkrementeller Sync
- [ ] Neue Inhalte werden erkannt
- [ ] Gelöschte Inhalte werden entfernt
- [ ] Metadata-Änderungen werden übernommen
- [ ] Watched-Status synct bidirektional
- [ ] Background-Sync läuft automatisch

### Spezial-Content
- [ ] TV Shows mit vielen Seasons (>10)
- [ ] Anime mit Special Episodes
- [ ] Multi-Version Movies
- [ ] 3D Movies (falls vorhanden)

---

## 🎨 UI & Widgets

### Home Screen Widgets
- [ ] "Recently Added Movies" zeigt neueste Filme
- [ ] "Recently Added Episodes" zeigt neueste Episoden
- [ ] "On Deck" zeigt weiterzuschauenden Content
- [ ] "Continue Watching" funktioniert
- [ ] Widget-Thumbnails laden korrekt
- [ ] Metadata in Widgets vollständig

### Navigation
- [ ] Plex Library Nodes funktionieren
- [ ] Breadcrumb-Navigation
- [ ] Search funktioniert
- [ ] Filter funktionieren (Genre, Jahr, etc.)
- [ ] Sort funktioniert

### Context Menus
- [ ] "Mark as Watched/Unwatched"
- [ ] "Refresh Metadata"
- [ ] "Delete from Plex"
- [ ] "Add to Watchlist"
- [ ] "Play Version..." (bei Multi-Version)

---

## 🎵 Music Testing (Optional)

- [ ] Music Library Sync
- [ ] Artist / Album Browsing
- [ ] Playback funktioniert
- [ ] Playlists funktionieren
- [ ] Album Art lädt

---

## 📡 Advanced Features

### Plex Companion
- [ ] Remote Control vom Handy/Web
- [ ] Timeline-Updates funktionieren
- [ ] "Play on Kodi" funktioniert

### Live TV & DVR (falls genutzt)
- [ ] Live TV Channels laden
- [ ] EPG wird angezeigt
- [ ] Aufnahmen werden gelistet
- [ ] Playback von Aufnahmen

### Watchlist Integration
- [ ] Plex Watchlist wird angezeigt
- [ ] Add to Watchlist funktioniert
- [ ] Sync mit anderen Geräten

---

## 🐛 Error Handling

### Netzwerk-Probleme
- [ ] Server nicht erreichbar: Saubere Fehlermeldung
- [ ] Timeout: Keine Kodi-Freezes
- [ ] Verbindungsabbruch während Playback: Recovery

### Ungültige Daten
- [ ] Fehlende Metadata: Kein Crash
- [ ] Korrupte Artwork URLs: Fallback zu Default
- [ ] Ungültige Playback URLs: Skip statt Crash

---

## 📊 Performance

### Startup Performance
- [ ] PKC startet innerhalb 5 Sekunden
- [ ] Keine Blockierung von Kodi UI
- [ ] Background-Tasks laufen asynchron

### Memory Usage
- [ ] Kein Memory Leak bei Langzeitbetrieb
- [ ] Memory Usage stabil (<200 MB)

### Database Performance
- [ ] Keine langsamen Queries (Log prüfen)
- [ ] Database Locks minimal
- [ ] Texture Cache Performance OK

---

## 📝 Log Analysis

### Keine kritischen Errors
- [ ] Keine `ERROR` Meldungen von PKC
- [ ] Keine Exceptions/Tracebacks
- [ ] Keine Deprecated API Warnings von PKC

### Nur erwartete Warnings
- [ ] Andere Addons können Warnings haben (OK)
- [ ] Kodi Core Warnings (nicht PKC-bezogen)

---

## 🔄 Upgrade Testing

### Von vorheriger Version
- [ ] Upgrade von PKC 3.11.2 (stock) läuft sauber
- [ ] Keine Datenverlust
- [ ] Settings bleiben erhalten
- [ ] Re-Sync nicht nötig

---

## ✅ Sign-Off Kriterien

Phase 2 ist komplett wenn:
1. ✅ Alle "Critical" Items (🔴) erfolgreich getestet
2. ✅ Mind. 90% aller anderen Items erfolgreich
3. ✅ Keine Regressions vs. Stock-Version
4. ✅ Performance gleichwertig oder besser
5. ✅ Mindestens 7 Tage Langzeit-Stabilitätstest

**Aktueller Status:** Testing läuft...

---

**Getestet von:** Max  
**Test-Datum Start:** 22. Dezember 2025  
**Test-Datum Ende:** TBD  
**Sign-Off:** ⏳ Pending
