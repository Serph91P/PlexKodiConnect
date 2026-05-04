# PlexKodiConnect 5.0 — Status & ehrliche Feature-Matrix

> Stand: Branch `feat/v5-cleanup`. Dieses Dokument ersetzt Marketing mit
> Wahrheit. Wenn etwas hier als ✅ steht, hat es einen Test oder wurde
> manuell auf der genannten Kodi-Version verifiziert.

## Unterstützte Kodi-Versionen

| Kodi   | Codename | Status v5  | Notiz                                                |
|--------|----------|-----------:|------------------------------------------------------|
| 19     | Matrix   | ❌ dropped | Code-Pfade entfernt (USE_TAGS, streamdetails legacy) |
| 20     | Nexus    | ✅ baseline| Alle Features sollten laufen                          |
| 21     | Omega    | ✅ primary | Aktiv getestet, Modern Tags API ist die einzige      |
| 22     | Piers*   | 🟡 best-effort | API kompatibel, aber kein Dauer-CI                |

\* Kodi 22 ist im Nightly. Wir tracken Breaking Changes, garantieren aber
keine Stabilität bevor 22 RC erscheint.

## Feature-Matrix

Legende:
- ✅ = funktioniert + getestet
- 🟢 = funktioniert (manuell verifiziert, kein automatischer Test)
- 🟡 = funktioniert teilweise / mit Caveats (siehe Notes)
- ❌ = entfernt in v5
- ⏳ = geplant für Phase B/C

| Feature                              | Kodi 20 | Kodi 21 | Kodi 22 | Notes |
|--------------------------------------|:-------:|:-------:|:-------:|-------|
| **Library**                          |         |         |         |       |
| Movies sync                          |   🟢    |   🟢    |   🟡    | full + delta sync |
| TV Shows sync                        |   🟢    |   🟢    |   🟡    | inkl. extras |
| Music sync                           |   🟢    |   🟢    |   🟡    | nicht primärer Fokus |
| Photos                               |   🟢    |   🟢    |   🟡    |       |
| **Playback**                         |         |         |         |       |
| Direct Play                          |   🟢    |   🟢    |   🟡    |       |
| Direct Stream                        |   🟢    |   🟢    |   🟡    |       |
| Transcode                            |   🟢    |   🟢    |   🟡    |       |
| Resume / Watch state → PMS           |   ✅    |   ✅    |   🟡    | bugfix-Tests in `tests/test_bugfixes.py` |
| UpNext integration                   |   ✅    |   ✅    |   🟡    | retry-Tests covered |
| Subtitles (forced/external)          |   🟢    |   🟢    |   🟡    |       |
| **Auth & Server**                    |         |         |         |       |
| Plex.tv login (OAuth/PIN)            |   🟢    |   🟢    |   🟡    |       |
| Multi-server / shared libraries      |   🟡    |   🟡    |   🟡    | switching ist klobig — Phase C |
| **Removed in v5**                    |         |         |         |       |
| Plex Companion (fling-to-Kodi)       |   ❌    |   ❌    |   ❌    | Code + Settings raus |
| Plex Watchlist                       |   ❌    |   ❌    |   ❌    | Context-Items + Nodes raus |
| Live TV / DVR                        |   n/a   |   n/a   |   n/a   | nie implementiert; Skip-Filter in websocket bleibt |
| Alexa-Voice                          |   ❌    |   ❌    |   ❌    | mit Companion entfernt (war ein dünner Wrapper) |

## Bekannte offene Baustellen (werden in den Phasen adressiert)

- **Phase B — Kodi-Adapter-Layer (gestartet):** Scaffold liegt unter
  `resources/lib/kodi/` (Module `runtime`, `dialogs`, `listitem`).
  Migration der Call-Sites (`transfer.py`, `itemtypes/`, `playback*`) folgt
  Datei für Datei mit Tests.
- **Phase B — Settings-Trimm (laufend):** 138 → 135 nach Alexa-Cut.
  Ziel ≤ 60 sichtbare. Nächste Runde: Implementation-Detail-Toggles aus
  `Sync`/`Customisation` (z.B. `dbSyncIndicator`, alte experimentelle Flags).
- **Phase C — Plex-Layer:** `plex_functions.py` ist der schwammige
  Sammeltopf. Plan: in `plex/api/` mit klaren Submodulen (library, player,
  metadata, sync) zerschneiden.
- **Phase D — Vendored libs raus:** `websocket`, `watchdog`, `pathtools`,
  `defusedxml`, `pathvalidate` über `addon.xml`-Requires beziehen.
- ~~**Phase E — Alexa**~~ — erledigt: Alexa-Code, Settings-Group,
  `ALEXA_TO_COMPANION`-Tabelle und `alexa_on_message`-Stub sind raus.
  Begründung: Alexa-Steuerung war ein Wrapper über Plex-Companion; ohne
  Companion gibt es keine sinnvolle Reimplementierung.
- **Phase F — Doku & Release:** README-Cleanup, Migrations-Guide 4.x → 5.0,
  CHANGELOG.

## Tests

```bash
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/pytest -q     # 33 passing
.venv/bin/ruff check .  # advisory in v5; gate kommt in Phase B
```

CI: `.github/workflows/tests.yml` läuft Pytest (3.11 + 3.12) bei jedem
Push/PR auf `main`, `develop`, `feat/**`, `fix/**`.
