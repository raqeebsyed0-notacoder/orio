# Handoff — ORIO Operations demo plugin (Innovex 90-Day AI Operations Pilot)

Date: 2026-10-06. Status: installed, backend healthy, UI live in Hermes Desktop.
Final visual sign-off by Founder still pending.

## What this is

Functional demo of the ORIO Operations experience for Ajeez Sebastian's
90-Day AI Operations Pilot (SAR 7,500 ex VAT, ORIO workflow, supervised
approvals). Real data only: 292 Rig+Well blocks extracted from the supplied
691-page Sep 19 Morning Report, 6 verified job cases, HP-707 history from
17 daily reports, MDD PO 4508154877, 6-row competitor demo (out of scope).
Nothing invented. No external actions exist anywhere in the code.

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
