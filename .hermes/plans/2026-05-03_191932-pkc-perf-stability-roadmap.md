# PKC 5.0 Roadmap — Performance, Stabilität, saubere Plex⇄Kodi Integration

**Repo:** `Serph91P/PlexKodiConnect` (Fork von croneter)
**Branch-Basis:** `develop` (HEAD `02a96903`)
**Stand:** 2026-05-03
**Ziel:** Aus dem 4.x-„Optimierungs-Stapel" eine wirklich saubere, stabile, gut getestete 5.0 machen — keine Halbintegration mehr, sondern eine Brücke die sich auf beiden Seiten (Plex Server-API ↔ Kodi 19/20/21/22 Add-on-API) wie eine Erstanbieter-Lösung anfühlt.

---

## 0. Diagnose — wo wir aktuell stehen

**Gut:**
- 4.0/4.1/4.2 hat Field-Filtering, Batch-Metadata, LRU-Cache, Pagination, Continue-Watching aktiv.
- Kodi-21-Migration laut `KODI21_MIGRATION.md` weitgehend durch (USE_TAGS, InfoTag, VideoStreamDetail).
- CI-Workflows (`addon-validations`, `make-release`) vorhanden.

**Problematisch — die echten Schmerzpunkte:**
1. **Tests fast inexistent.** Genau **eine** Test-Datei (`tests/test_bugfixes.py`) für ~30 k Zeilen Code. Jede Änderung ist Blindflug.
2. **God-Module.** `plex_functions.py` 1357 LoC, `kodi_db/video.py` 1126, `kodigui.py` 1030, `playlist_func.py` 1012 — schwer testbar, schwer review-bar, hohe Regressions-Wahrscheinlichkeit.
3. **Direkter Schreibzugriff auf Kodi-DB an 20+ Stellen** (`grep kodi_db|plex_db` → 20 Files). Schema-Drift zwischen Kodi 19/20/21/22 ist die Haupt-Crashquelle.
4. **25× `except Exception:` / bare except** außerhalb von Vendor-Code → Fehler werden geschluckt, Debugging schwer.
5. **Doku ≠ Realität.** `PKC_4.0_CHANGES.md` markiert Features als „AKTIV" obwohl der Migrations-Doc gleichzeitig „TODO: transfer.py auf moderne API umstellen" listet. `KODI21_MIGRATION.md` hat offene Checkboxen unter „VOLLSTÄNDIG MIGRIERT". Das verschleiert den echten Status.
6. **Settings-Wildwuchs.** 143 `<setting>`-Einträge in `settings.xml`. Viele sind Implementation-Details die User nicht entscheiden sollten (Cache-Größen, Batch-Sizes). Stand User-Präferenz: keine Toggles für Implementierungs-Fallbacks.
7. **Vendored Libs ungepflegt** (`websocket/`, `watchdog/`, `defusedxml/`, `pathtools/`, `pathvalidate/`, `requests/`) — Sicherheits- und Wartungs-Schuld.
8. **Plex-Companion / Music / Watchlist / DVR**: laut `TESTING_CHECKLIST.md` „falls genutzt" — also unsicher ob aktuell funktional. Hier muss entschieden werden: fixen oder rauswerfen.

---

## 1. Leitprinzipien für 5.0

1. **Sichtbar funktioniert > viele Features.** Lieber 12 Features die 100 % laufen als 18 mit Fragezeichen.
2. **Kodi-API-Layer kapseln.** PKC darf nirgends mehr direkt `xbmc`/`xbmcvfs`/`xbmcgui` raw aufrufen, ohne Versions-Adapter (19/20/21/22). Ein Modul, eine Wahrheit.
3. **Plex-API-Layer kapseln.** Alle Plex-Requests durch *einen* Client mit Cache, Retry, Timeout, Field-Selection, Pagination — keine Direkt-Calls mehr aus `widgets.py` / `library_sync/*` / `playback.py`.
4. **Kein User-Toggle für Implementierungs-Fallbacks.** Cache, Batch-Size, Field-Selection automatisch wählen, intern fallback. (User-Präferenz.)
5. **Tests sind Pflicht für alles was die Kodi-DB schreibt** — sonst keine Schema-Sicherheit.
6. **Ehrliche Doku.** `STATUS.md` mit Realstatus pro Feature × Kodi-Version. Keine Marketing-Tabellen mehr.

---

## 2. Phasen-Plan

### Phase A — Fundament (PKC 4.3, 2-3 Wochen)
**Ziel:** Schmerzfrei refactoren können.

- **A1.** Test-Infrastruktur ausbauen
  - `pytest` + `pytest-cov` + `pytest-mock` in `requirements-dev.txt`.
  - `tests/conftest.py` mit Kodi-Mock-Fixtures (existiert teilweise in `tests/kodi_mocks.py`, aber unvollständig).
  - GH-Action `tests.yml`: matrix python `3.10/3.11/3.12`, run pytest mit Coverage-Gate (Start: 15 %, Ziel 5.0: 60 %).
  - Mock-Server für Plex (siehe `python-plexapi` Tests als Vorbild) → `tests/fixtures/plex_responses/*.xml`.
- **A2.** Linting/Format-Gate
  - `ruff` config (PKC ist Python 3, Kodi 21 = py 3.11). Auto-fix bei PR via Workflow.
  - `mypy --strict` zumindest auf neuen Modulen — kein „big-bang", inkrementell.
- **A3.** Realstatus-Audit
  - `STATUS.md` mit Feature × {Kodi 19, 20, 21, 22} × {direct play, transcode, sync, watched-state, …}: ✅ / ⚠ / ❌ / „nie getestet".
  - Issues für jedes ⚠/❌ anlegen, mit Reproduktions-Steps.
- **A4.** Bare-except Audit
  - Alle 25 `except Exception:` durchgehen; mindestens loggen mit `LOG.exception(...)`. Wo sinnvoll: spezifischer Exception-Typ.

**Dateien neu/geändert:**
`requirements-dev.txt`, `pyproject.toml` (ruff/mypy), `.github/workflows/tests.yml`, `tests/conftest.py`, `tests/fixtures/plex_responses/`, `STATUS.md`.

### Phase B — Plex-API-Layer konsolidieren (PKC 4.4, ~3 Wochen)
**Ziel:** Genau ein Pfad zum Plex-Server. Ende.

- **B1.** `resources/lib/plex/` Paket (sauber, neu) mit:
  - `client.py` — `PlexClient`: Session-Pooling (`requests.Session` mit Connection-Reuse), Retry mit Backoff (`urllib3.Retry`), Timeout-Defaults, ETag-Support, einheitliches Error-Mapping.
  - `endpoints.py` — alle URL-Builder als Funktionen, ein Ort.
  - `fields.py` — `WIDGET_FIELDS` / `SYNC_FIELDS` / `DETAIL_FIELDS` zentral (sind in `plex_functions.py` versteckt).
  - `cache.py` — der bereits vorhandene `metadata_cache.py` aufgeräumt + Stats-Endpunkt für ein Diagnose-UI.
  - `batch.py` — `GetPlexMetadataBatch` raus aus `plex_functions.py`, eigenständig + getestet.
- **B2.** Schrittweise Migration: `plex_functions.py` (1357 LoC) wird zur Adapter-Shim auf `plex/`. Kein bigbang, modul-für-modul:
  - `widgets.py` → nutzt `plex.client`
  - `library_sync/*` → nutzt `plex.client`
  - `playback.py` → nutzt `plex.client`
- **B3.** Companion: prüfen ob „Play on Kodi" / Timeline-Updates noch laufen. Falls ja → Tests dazu. Falls nein → in `STATUS.md` rot, Fix-Issue oder Removal-Entscheidung.

**Pitfall (User-Präferenz):** kein neues Setting „use new client" — der neue Client IST der Pfad, alter wird gelöscht sobald migriert.

### Phase C — Kodi-Adapter-Layer (PKC 4.5, ~3 Wochen)
**Ziel:** PKC bricht nicht mehr bei jedem Kodi-Release.

- **C1.** `resources/lib/kodi/` Paket:
  - `version.py` — eine Quelle für `KODI_MAJOR`, `IS_NEXUS`, `IS_OMEGA`, `IS_PIERS`. Aktuell verstreut in `variables.py`/`widgets.py`.
  - `listitem.py` — Wrapper um `xbmcgui.ListItem` der intern auf InfoTag (≥20) oder `setInfo` (19) routet. **Alle** Aufrufer (`widgets.py`, `transfer.py`, `kodigui.py`, …) gehen darüber.
  - `streaminfo.py` — analoger Wrapper für `addStreamInfo` vs. `VideoStreamDetail`.
  - `db_schema.py` — Schema-Detection: liest `MyVideos1XX.db` und detektiert Schema-Version pro Kodi-Major; alle `kodi_db/*.py` Writes routen über schema-bewusste Helpers.
- **C2.** `kodi_db/video.py` (1126 LoC) entzerren in `movies.py`, `tvshows.py`, `episodes.py`, `music_videos.py` — kleinere Module, einzeln testbar.
- **C3.** Tests: für jedes Schema-Op (insert movie, update playcount, delete episode) ein Roundtrip-Test gegen eine echte SQLite-Test-DB (Kodi-Schemas als Fixture in `tests/fixtures/kodi_schemas/`).
- **C4.** `transfer.py` Restmigration (`addStreamInfo` → modern). Steht im `KODI21_MIGRATION.md` als offen.

### Phase D — Stabilität von Sync & Playback (PKC 4.6, ~2 Wochen)

- **D1.** `library_sync/` Threading-Audit
  - `backgroundthread.py` (526 LoC) Review: Worker-Pool-Größen, Queue-Backpressure, sauberer Shutdown bei `Monitor.abortRequested()`.
  - Stress-Test-Skript: 20 k-Item-Library-Sync gegen Mock-PMS, dann Memory/CPU-Profil.
- **D2.** WebSocket-Robustheit
  - `library_sync/websocket.py` (517 LoC) + vendored `websocket/` ersetzen durch maintained `websocket-client` aus PyPI (vendored, fixed version) — bringt aktuelle Reconnect-Logik.
  - Reconnect-Backoff exponentiell, kein „busy loop".
- **D3.** Playback / Watch-Status (das war Bug 1+2 in `test_bugfixes.py`)
  - Tests dort ausbauen, bis alle Übergänge abgedeckt sind: stop, skip, UpNext, external player, partial play.
  - Race-Condition zwischen `kodimonitor.py` (892 LoC) Events und PMS-Status-Push expliziet dokumentieren.
- **D4.** Direct-Path-Sources sicher machen
  - Pfad-Validierung (`pathvalidate` schon vendored) konsequent einsetzen, vor allem für SMB/NFS Edge-Cases.

### Phase E — Feature-Inventur: was bleibt, was fliegt (PKC 5.0)

Pro Feature: **Funktioniert?** → behalten. **Kaputt aber wertvoll?** → fixen. **Kaputt + Nische + Aufwand groß?** → entfernen, im CHANGELOG dokumentieren, Migrations-Hinweis im Settings-Dialog.

Kandidaten zur Diskussion (Entscheidung pro Feature im Issue-Tracker):

| Feature | Aktueller Verdacht | Vorschlag |
|---|---|---|
| Plex Companion (fling, Timeline) | Wahrscheinlich teilweise broken | **Fix oder cut** — wenn nach Phase B nicht mit ≤ 2 Wochen Aufwand stabilisierbar → entfernen |
| Music-Library-Sync (`itemtypes/music.py` 545, `kodi_db/music.py` 480) | „Optional" in Testing-Checklist | **Behalten**, aber mit Tests + Schema-Adapter |
| Live-TV / DVR | „falls genutzt" | **Cut** wenn keine User-Reports zeigen dass es funktioniert; Plex hat eigene Tuner-UX |
| Plex Watchlist | unklar | **Fix** — wertvoll, sichtbar im Plex-Universum |
| Skip Intro / Credits / Commercials | aktiv, getestet | **Behalten** — Killer-Feature |
| Trailer-Fallback via TMDB-Add-on | low-value | **Cut** — Add-on-Abhängigkeit, fragil |
| Alexa Voice Recognition (im Readme beworben) | macht PKC selbst nichts | **Aus README streichen** — ist reine PMS-Feature, kein PKC-Beitrag |
| Settings-Toggles für Cache/Batch/Field-Filter | User-Antipattern | **Entfernen** (User-Präferenz: keine Toggles für Implementierungs-Details) |
| Multi-User-Switching (`userselect.py`) | unklar | Status klären, dann Entscheidung |

**Settings-Trim-Ziel:** von 143 auf ≤ 60 user-relevante Settings.

### Phase F — Polish & Release 5.0 (~1 Woche)

- **F1.** `addon.xml` aufräumen, Provider-Konsistenz (Seraph91P), korrekte minVersion pro Plattform.
- **F2.** README neuschreiben — ehrlich was PKC tut/nicht tut, Screenshots aktualisieren.
- **F3.** Migrations-Skript (`migration.py` existiert) für 4.x → 5.0: alte Settings entfernen, Cache-DB neu aufbauen.
- **F4.** Repo-Release-Pipeline checken (`make-release.yml` + `notify-repository.yml`) → automatisierter Tag → Repo.

---

## 3. Files die in Phase A/B/C garantiert angefasst werden

```
resources/lib/plex_functions.py          # → in resources/lib/plex/* aufgeteilt
resources/lib/kodi_db/video.py           # → in kodi_db/{movies,tvshows,episodes,...}.py
resources/lib/kodi_db/music.py           # Schema-Adapter
resources/lib/widgets.py                 # nutzt neue plex.client + kodi.listitem
resources/lib/transfer.py                # addStreamInfo-Restmigration
resources/lib/playback.py                # nutzt neue plex.client, kodi-adapter
resources/lib/kodimonitor.py             # Race-Conditions Watch-Status
resources/lib/backgroundthread.py        # Threading-Audit
resources/lib/library_sync/websocket.py  # ws-client modernisieren
resources/lib/metadata_cache.py          # → resources/lib/plex/cache.py
resources/lib/variables.py               # Kodi-Version-Detection raus → kodi/version.py
resources/settings.xml                   # Trim auf ≤ 60 Settings
resources/language/.../strings.po        # Strings für entfernte Settings markieren
addon.xml                                # Provider/Version
```

Neue Dateien:
```
pyproject.toml                # ruff, mypy, pytest config
requirements-dev.txt
.github/workflows/tests.yml
STATUS.md                     # ehrlicher Feature/Version-Matrix
resources/lib/plex/{__init__,client,endpoints,fields,cache,batch}.py
resources/lib/kodi/{__init__,version,listitem,streaminfo,db_schema}.py
tests/fixtures/plex_responses/
tests/fixtures/kodi_schemas/
tests/test_plex_client.py
tests/test_kodi_listitem.py
tests/test_kodi_db_video.py
tests/test_library_sync_*.py
```

---

## 4. Validation — wie wir wissen dass 5.0 wirklich besser ist

| Metrik | Heute (geschätzt) | Ziel 5.0 |
|---|---|---|
| Pytest Coverage | <5 % | ≥ 60 % der eigenen Module (vendored ausgeklammert) |
| Settings-Anzahl | 143 | ≤ 60 |
| `except Exception:` ohne Logging | 25 | 0 |
| Module > 800 LoC | 8 | ≤ 2 (vendored ignoriert) |
| Initial-Sync 5 k Movies (lokales LAN) | ~5 min (laut Doku) | ≤ 90 s |
| Widget-Refresh „Recently Added" | ~8 s | ≤ 1 s |
| Memory nach 24 h Service | unbekannt | < 200 MB stabil (Profiling-Test) |
| Crash-Log nach 24 h Sync-Loop | unbekannt | 0 unhandled exceptions |
| GH-CI grün auf Kodi-19/20/21/22-Mock | partial | komplett |

Zusätzlich Manual-Test-Matrix gegen echte PMS aus `TESTING_CHECKLIST.md` — als ausfüllbares Markdown im Release-PR.

---

## 5. Risiken & Tradeoffs

- **Refactor-Big-Bang vs. graduell.** Plan ist bewusst graduell (4.3 → 4.4 → 4.5 → 4.6 → 5.0), weil die Test-Basis fehlt — sonst riskieren wir Regressions die niemand mitkriegt. Tradeoff: Roadmap dauert ~3 Monate Kalenderzeit.
- **Vendored Libs ersetzen.** Wenn wir `websocket/` raus und gegen PyPI-Version ersetzen, müssen wir Kodi-19-Kompat (Python 3.8) sicherstellen — ggf. zwei Pin-Versionen.
- **Settings-Removal ist breaking.** User die das tunen müssen `5.0` als Major verstehen. Migrations-Skript + klare Release-Notes.
- **„Companion / Live-TV cut" ist politisch.** Issue mit User-Umfrage vorher, sonst Shitstorm.
- **Upstream croneter** ist seit langem inaktiv — wir sind effektiv der Maintainer. Heißt: keine Upstream-Konflikte, aber auch keine Hilfe. Plan einrechnen.

---

## 6. Entscheidungen (bestätigt vom User, 2026-05-03)

- **Kodi 19 wird gedroppt.** Min-Version = Kodi 20 (Nexus). Adapter-Schicht entfällt, KODIVERSION-Checks `< 20` werden entfernt, `USE_TAGS`-Konstante fällt weg (immer true).
- **Plex Companion komplett raus.** `resources/lib/companion.py`, `resources/lib/plex_companion/` (8 Dateien, ~1700 LoC), Settings (`plexCompanion`, `companionPort`, `companionUpdatePort`, `companion_show_gdm_port_warning`), Strings, Service-Hooks und websocket_client-Aufruf werden entfernt. Begründung: Plex Companion-Protokoll wurde von Plex deprecatet, neue Plex-Apps nutzen es nicht mehr.
- **DVR / Live-TV bleibt out.** PKC hat aktuell ohnehin keine eigene DVR/Live-TV-Implementierung (nur das Wort taucht in einem Kommentar in `library_sync/websocket.py` auf) — keine Code-Removal nötig.
- **Watchlist komplett raus.** `entrypoint.watchlist`, `library_sync/nodes.py` Watchlist-Einträge, `service_entry.watchlist_add/remove`, `addon.xml` Context-Items `context_watchlist_add.py` / `context_watchlist_remove.py` (samt Dateien), Strings 30402/30403/39212/1463.
- **Reihenfolge:** Erst Cuts (Phasen E-Anteile), dann Fundament (Phase A), dann Refactor (B/C/D). Cuts zuerst, weil weniger Code = weniger zu testen / refactoren.
