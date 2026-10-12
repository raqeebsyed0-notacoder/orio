# Handoff — ORIO Operations plugin (Innovex pilot → real product)

Last updated: 2026-10-12 (Phase 1). Earlier: 2026-10-06 (demo baseline).

## Current status

**Phase 1 shipped: multi-day ingestion + market-intelligence track.**
Backend suite 24/24 PASS (was 14). UI ESM gate clean. Three copies in sync.

The plugin now reads more than one report day and carries the competitor
matrix as a first-class, separate track.

## What this is

ORIO Operations for Ajeez Sebastian's 90-Day AI Operations Pilot, now built as
a **real product** rather than a demo. Ajeez is client #1, not the only client.
Two tracks live side by side and never mix:

1. **ORIO operations** — rig/well/job-cycle lifecycle, reconciliation, MDD.
   Evidence states, approval gates, page lineage.
2. **Market intelligence** — competitor tool-size x company rows mined from
   morning reports. Market observations only, never operational claims.
   End goal of the current workstream.

Email, OneDrive and Telegram remain BLOCKED. They are architected to be
switched on later without a rewrite (see Next plan).

## Data now served

| Source | Rows | Where |
|---|---|---|
| Sep 19 MR (691 p, legacy index) | 292 blocks | `data/mr_index.json` |
| Oct 12 MR (649 p) | 280 blocks | `data/ingested/mr/LMR10122026.json` |
| Sep 19 MR (re-ingested) | 292 blocks | `data/ingested/mr/Sep19.json` |
| Tracker workbook (40 day-sheets) | 2,302 rows | `data/ingested/tracker/` |
| June competitor matrix | 131 rows | `data/ingested/matrix/June2026.json` |
| Jun–Aug + Sep MRs (not yet ingested) | 91 files | `03_Market-Intelligence/` |

## Ingestion (new — runtime, not build-time)

    data/ingest_mr.py       MR PDF  -> dated rig/well index records
    data/ingest_tracker.py  XLSX    -> dated tracker rows (one sheet per day)
    data/ingest_matrix.py   XLSX    -> competitor matrix rows
    data/build_db.py        reads all of the above + legacy JSON -> SQLite

Slow PDF work happens once in the ingest scripts; `build_db.py` only reads
their JSON, so rebuilds stay fast.

**Proven:** `ingest_mr.py` segments the Sep 19 sample to exactly 292 blocks
with 0 first_page mismatches against the known-good index.

## Schema changes (Phase 1)

- `rig_blocks` + `jobs` gained `report_date` (multi-day was impossible before).
- New `reports` table (one row per ingested day).
- New `matrix_rows` table (market-intel track).
- `tracker_rows` gained the real tracker columns + `report_date`.
- `decisions` gained `actor` / `actor_role` (non-repudiable approvals).

## API

New: `/reports`, `/matrix`, `/matrix/export.csv`.
Changed: `/rigs` and `/rigs/{rig}/{well}` take `report_date` (default latest);
`/meta` returns `report_dates`. Hardcoded `2026-09-19` removed.

## UI

- Report-day selector in the top bar (drives Rigs & Wells).
- New **Market Intel** view: month / size / company filters, size x company
  bars, page-lineage column, CSV export.
- Today and the curated cases remain dated to the Sep 19 baseline and say so
  on screen.

## Sync (one command)

    bash tools/sync_ui.sh

Copies repo -> `plugins/` -> `desktop-plugins/` mirror, runs the ESM gate on
the mirror, byte-checks against the repo, and runs the backend suite.
Then: Hermes Desktop -> Ctrl/Cmd+K -> Reload desktop plugins.

## Process rules learned the hard way

1. The app loads ONLY the `desktop-plugins/` mirror copy. Editing the repo
   changes nothing the operator can see. Use `tools/sync_ui.sh`.
2. The shell owns the mirror dir and can delete/stale it (marker
   `.hermes-package.json`). If UI changes "don't appear", check the mirror.
3. Gate every UI edit with `node --input-type=module --check`. Plain
   `node --check` parses CommonJS and gives a FALSE CLEAN on this ESM file
   (root-caused 2026-10-06: stray `]` threw on every load).
4. Backend router mounts at dashboard-server start; `plugins.enabled` is read
   via CLI only (`hermes config set`, never hand-edit).
5. Never claim visual PASS without an operator screenshot. Byte checks are
   not render checks.
6. Compare copies with CRLF-normalized hashes (`tr -d '
' | md5sum`), never
   raw `diff` — the repo is LF and installed copies are CRLF, so raw diff
   reports thousands of phantom differences.
7. Install ONLY via `hermes plugins install <repo> + enable`. Manual copies
   into `plugins/` are pruned by plugin sync.

## Resume commands

```bash
cd "D:/12_projects/Innovex (ajeez)/orio-operations-plugin"
git pull --rebase && git push
# ingest a new report day
python3 data/ingest_mr.py "D:/12_projects/Innovex (ajeez)/01_Morning-Reports/<file>.pdf" \
        --json data/ingested/mr/<file>.json
python3 data/build_db.py
bash tools/sync_ui.sh
```

## Open items

1. **June-131 acceptance test** — full month reproduction from the 80 June MRs,
   with the 2 supervisor-flagged rows surfaced as corrections. Extraction run
   in progress (`05_Architecture/june_matrix.py`).
2. Ingest the remaining 80 Jun–Aug + 11 Sep MRs into the day index.
3. Rows in `matrix_rows` carry `source_page` only when extracted from a report;
   workbook-sourced rows show "workbook". The June extraction closes this.
4. Operator render QA on the new Market Intel view.
5. Phase 2 (channel seams), Phase 3 (hardening), Phase 4 (multi-client) — see
   `06_Working-Notes/next-plan-of-action-2026-10-12.md`.

## Do NOT

- Record video, contact Ajeez's counterparties, or connect external systems
  without explicit owner order.
- Merge market-intel rows into ORIO lifecycle/reconciliation state.


## Paths

- Source of truth: `D:/12_projects/Innovex (ajeez)/orio-operations-plugin/`
  (repo: https://github.com/raqeebsyed0-notacoder/orio.git, package at root)
  - `desktop/plugin.js` — all UI (single ESM file)
  - `dashboard/plugin_api.py` — backend (FastAPI, stdlib only)
  - `plugin.yaml` + `dashboard/manifest.json` + `__init__.py` (no-op register)
  - `data/build_db.py` + `data/mr_index.json` + `data/seed_cases.json` — DB build
  - `tests/run_api.py` — 14-check backend suite (throwaway home)
  - `README.md`, `DEMO_WALKTHROUGH.md` (10-scene recording flow), `DESIGN.md` (UI contract)
- Installed backend: `C:/Users/THinkPad/AppData/Local/hermes/plugins/euphoria-orio-operations/`
- Loaded UI copy: `C:/Users/THinkPad/AppData/Local/hermes/desktop-plugins/euphoria-orio-operations/plugin.js`
- Demo DB: `C:/Users/THinkPad/AppData/Local/hermes/state/orio-ops/orio_demo.db`
- System reference: `D:/12_projects/Innovex (ajeez)/Innovex_Ajeez_90_Day_AI_Operations_Architecture.html`

## Verified

- Backend 14/14 PASS (292 count, HP-707 cycles, SP-32 conflict, SP-262 MDD block,
  approve-mutates-demo, blocked-409, reject/incorrect, MDD missing markers,
  email never sends, CSV 292+ rows, zero network imports).
- `node --check` clean on installed UI file. Zero em-dashes, zero hardcoded
  colors, zero lorem/emoji (grep-verified).
- Screenshot-verified: Today renders with live data, counts 2/8/292/6.

## Process rules learned the hard way

1. The app loads ONLY the `desktop-plugins/` mirror copy. After every UI edit:
   copy source → `plugins/` copy → `desktop-plugins/` mirror, then tell the
   Founder to ⌘K → Reload desktop plugins. Verifying any other copy proves nothing.
2. The shell owns the mirror dir: it can delete/stale it (marker
   `.hermes-package.json`). If UI changes "don't appear", check the mirror
   exists and contains the new CSS string before anything else.
3. Backend router mounts at dashboard-server start; `plugins.enabled` is read
   via CLI only (`hermes config set`, never hand-edit). After install/enable,
   Desktop needs Rescan (Capabilities → Plugins) or full restart, then Reload.
4. 404 `{"detail":"Plugin not found"}` = backend not mounted or plugin unknown
   to discovery (server predates install), not a code bug. See
   `web_server_dashboard.py` mount + runtime gate.
5. Never claim visual PASS without a Founder screenshot. Byte checks are not
   render checks.
6. `node --check` DOES NOT validate this UI file: it parses CommonJS and
   gave a false clean on v6 while the renderer (ESM) threw
   `SyntaxError: Unexpected token ']'` on every load. Gate every UI edit
   with `node --input-type=module --check`. (Root-caused 2026-10-06:
   stray `]` at old line 1187 in ExpansionView, fixed in 0802c0f.)
7. Install ONLY via `hermes plugins install <repo> + enable`. Manual copies
   into `plugins/` are pruned by plugin sync (wiped 2026-10-06 04:48) and
   dropped from `plugins.enabled`. Registered installs survive restarts.
8. Rails stay STATIC (`position:static; align-self:start`), never sticky:
   sticky rails drift out of line with content on scrolled pages (flagged
   2026-10-06 on Rigs/History/Evidence). Panels get `overflow:hidden` so
   nothing ever escapes; rail values wrap (`white-space:normal` beats the
   `-mono` nowrap), legend labels wrap, only bar-row names ellipsize.
9. Donut only where the distribution informs (Today, Lifecycle). Single-ring
   donuts (Actions, Exceptions) become tap-to-filter legend rows with the
   same onPick — same function, no lost-looking ring. (2026-10-06.)

## Open items

1. Table header band: FIXED 2026-10-06 (v3 UI). Headers moved to a real
   thead with sticky solid var(--ui-bg-elevated) band + 2px divider, so the
   strip no longer depends on the near-background tint var. Installed to
   source + both copies, node --check clean, backend 14/14 PASS. Needs
   Founder screenshot to close render QA.
2. Production-ready polish across all 8 views equally (Founder scope).
   v3 UI shipped 2026-10-06: 8 bugs fixed (conditional hooks, thead,
   native prompt, hardcoded 292, dialog error state, nav active state,
   picker overflow, shared note state) + polish (result counts, section
   headings, MISSING callouts, aria, focus-visible). Backend 14/14 PASS,
   node --check clean. Render QA still needs a Founder screenshot.
3. Narrow-pane DECIDED 2026-10-06 (v3 UI): horizontal scroll nav row above
   content under 720px, tiles 2-up. No collapse. Needs Founder screenshot.
6. Today gutter FIXED 2026-10-06 (v4 UI): content widened to 1560px, table
   sits beside a sticky snapshot rail (priority donut + lifecycle bars +
   approvals + pilot card, all tap-interactive, all live data). Installed,
   node --check clean, no backend change. Needs Founder screenshot.
7. All views interactive 2026-10-06 (v5 UI, per Founder): queue donut,
   rigs stage bars, lifecycle donut, exceptions donut, evidence chips,
   history key-milestone segment, expansion company bars. Installed,
   node --check clean, no backend change. Needs Founder screenshot.
8. Rail alignment to Lifecycle reference 2026-10-06 (v6 UI, per Founder):
   toolbars lifted full-width above the grid on Today, Rigs, Expansion;
   Evidence and History gained full rails. Every page now opens content
   and rail at the same line. Installed, node --check clean, no backend
   change. Needs Founder screenshot.
4. Retrospective QA honestly reports no post-Sep-19 data (none supplied).
   Date rule, HP-701 MDD identifiers, SP-32 resolution: Awaiting Ajeez by design.
5. Do NOT record video, contact Ajeez, or connect external systems without
   explicit Founder order.

## Resume commands

```bash
# git repo (source of truth): https://github.com/raqeebsyed0-notacoder/orio.git
cd "D:/12_projects/Innovex (ajeez)/orio-operations-plugin"
git pull --rebase && git push
# edit UI, then sync both copies + syntax check
SRC="D:/12_projects/Innovex (ajeez)/orio-operations-plugin/desktop/plugin.js"
DST1="C:/Users/THinkPad/AppData/Local/hermes/plugins/euphoria-orio-operations/desktop/plugin.js"
DST2="C:/Users/THinkPad/AppData/Local/hermes/desktop-plugins/euphoria-orio-operations/plugin.js"
cp "$SRC" "$DST1" && mkdir -p "$(dirname "$DST2")" && cp "$SRC" "$DST2"
node --check "$DST2"
# backend regression (throwaway home, safe)
<C:/Users/THinkPad/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe> "D:/12_projects/Innovex (ajeez)/orio-operations-plugin/tests/run_api.py"
# clean demo rebuild
python3 "D:/12_projects/Innovex (ajeez)/orio-operations-plugin/data/build_db.py"
```
