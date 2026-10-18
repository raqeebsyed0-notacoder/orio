# ORIO Training Report — T1-T7 (Phase 1-4 proof log)

Date: 2026-10-15. Author: ajeez-orio agent (supervised pilot).
Scope: training proof only. No video, no counterparty contact, no external
connect. All paths below are demo-local unless marked as source input.

How to read this: one proof line per training task — skill used, evidence
file, gate hit, block raised. Counts quoted are each run's self-reported
gate as recorded in its kanban completion metadata, re-verified today only
where stated. T7 (this task) re-verified end state live: suite 62/62 PASS,
sync clean (see T7 line).

## T1 — June-131 acceptance (t_ff00f0a1) — CLOSED (serving; remainder to T1b)

- Skill used: orio-operations-core, orio-market-intelligence, orio-validation.
- Evidence file: `03_Market-Intelligence/Market Intelligence Competitors-June
  jobs.xlsx` (Sheet1, 135 physical rows, 131 after blank-row filter) ->
  `orio-operations-plugin/data/ingested/matrix/June2026.json` (131 rows;
  sizes 9.625=66 / 13.375=63 / 18.625=2; WFD=48 HAL=45 FET=27 TAM=11) ->
  live DB `matrix_rows`=131. Disproof kept:
  `06_Working-Notes/june-matrix-run.json` (v1 extractor: 11/131 matched,
  117 missing, 1017 over-extracted).
- Gate hit: backend suite 24/24 PASS + `sync_ui.sh` ESM_OK + IN SYNC
  (ff05c1b7). Render QA explicitly NOT claimed (operator screenshot pending).
- Block raised: YES — `needs_input` (run 139): "2 supervisor-flagged rows"
  unidentifiable in any file/sheet/note (INSUFFICIENT EVIDENCE, not guessed)
  + MR page-lineage + date rule awaiting Ajeez. Founder accepted serving,
  split remainder to T1b (t_5f7af65d); T1b later CONFIRMED the v1 anchor flaw.
- Lesson (no skill store — recorded here): run the suite ONLY with
  `hermes-agent/venv/Scripts/python.exe` (system python3 has no fastapi);
  cross-check physical vs filtered row counts (135 vs 131) before claiming
  a sheet match.

## T2 — Ingest remaining 91 MRs (t_8cd9045b) — CLOSED

- Skill used: orio-morning-report + orio-validation.
- Evidence file: `data/ingested/mr/_ingest_run_20261015.log` (SHA256 per
  file; 90/90 PDFs OK, 0 fail) + `data/ingested/mr/*.json`. DB after build:
  92 report days (2026-06-01 to 2026-10-12), 26,415 blocks (282-297/day,
  consistent with the Sep-19 292 baseline). Matrix untouched (131).
- Gate hit: backend suite 27/27 PASS (2 stale 2-day-era assertions updated
  to multi-day) + `sync_ui.sh` ESM_OK + IN SYNC.
- Block raised: NONE (completed). Two exceptions documented without
  blocking: 2026-06-26 `LMR06262026.pdf` (117 MB, Print-To-PDF raster, 0
  extractable chars -> 0 blocks, reports row kept) needs an Ajeez decision
  (re-source or accept); the 80th Jun-Aug item is a `.docx`, not an MR PDF.
  Market-intel rows never merged into lifecycle state.
- Lesson (recorded here): stale hardcoded suite counts fail cosmetically
  after a data-world change — update the assertion to the new world, don't
  force data to the old count.

## T3 — source_page lineage fix (t_ed20d406) — CLOSED (HANDOFF item 3)

- Skill used: orio-validation (no-invent rule: page cite or "workbook").
- Evidence file: SQL spot-check on live DB (0 NULL `source_page`, 131x
  `'workbook'`, 131x `extraction='workbook'`, lineage 0/131 with page, CSV
  pages all `'workbook'`); June split verified against T1 output
  (`june-matrix-run.json`) + `06_Working-Notes/T1b-cross-verification-2026-10-15.md`
  (workbook 131 / report-confirmed 0 — no invented numbers).
- Gate hit: backend suite 32/32 PASS (27 prior + 5 T3 checks) +
  `sync_ui.sh` ESM_OK + IN SYNC (52fe8c33).
- Block raised: NONE.
- Lesson (recorded here): NULL lineage reads as missing evidence and
  IS-NOT-NULL counts lie after any backfill — use an honest string marker
  (`'workbook'`) so provenance stays queryable and counts stay truthful.

## T4 — DB rebuild + render-QA prep (t_866e34e6) — CLOSED

- Skill used: orio-operations-core (installer-only rule, CRLF-normalized
  hash compare — never raw diff).
- Evidence file: live DB `profiles/ajeez-orio/state/orio-ops/orio_demo.db`
  rebuilt 2026-10-15 (~6.6 MB; 92 days, 26415 blocks, 131 matrix rows, 0
  NULL pages); CRLF-normalized md5 `plugin.js` 52fe8c33 identical x3 copies,
  `plugin_api.py` 5a8a106c identical x2. Stale-DB flag: unscoped
  `hermes/state/orio-ops/orio_demo.db` is the Oct-5 pre-Phase-1 leftover,
  unread by the runtime (T7 HANDOFF now documents per-client paths and
  recommends deleting it).
- Gate hit: backend suite 30/30 PASS + `sync_ui.sh` ESM_OK + IN SYNC.
  (Count step T3-32 -> T4-30: each run's self-report as recorded; T7
  re-verified today that all five T3 lineage checks are present in
  `tests/run_api.py` and PASS inside the current 62/62 — INSUFFICIENT
  EVIDENCE for the exact cause of the step, current state CONFIRMED.)
- Block raised: NONE (completed to release T5; render QA left as a human
  step with an exact screenshot list in task comment, not a worker block).
  Render QA deliberately NOT claimed — awaiting Founder screenshot.
- Lesson: none triggered (all checks first-try, no errors — anti-loop rule
  3 not engaged).

## T5 — Phase 2 channel seams (t_6cebb14d) — CLOSED

- Skill used: orio-operations-core (blocked-channel discipline per
  `06_Working-Notes/next-plan-of-action-2026-10-12.md` Phase 2).
- Evidence file: `dashboard/channels.py` (new; `DeliveryChannel` protocol +
  `BlockedChannel` x3 with reason + unblock-day adapter); live read-only
  probe vs live DB (channels blocked x3, MDD payload keys
  recipient/subject/body/attachments/ref, outbox 0 rows — no demo
  pollution). No credentials in repo; no network imports.
- Gate hit: backend suite 38/38 PASS (30 prior + 8 channel checks) + ESM +
  sync IN SYNC. New reads: `GET /channels/status`, `GET /delivery/outbox`.
- Block raised: NONE.
- Lesson: none triggered (zero retries).

## T6 — Phase 3 hardening (t_a82fbac5) — CLOSED

- Skill used: orio-operations-core (approval attribution + ops discipline).
- Evidence file: `dashboard/plugin_api.py` (actor bind: `x-hermes-user`
  header wins as `gateway`, forged client claim vs header rejected 400 +
  logged, else `client`/`default`; `GET /ops/log`); `data/build_db.py`
  (`decisions.actor_source`); `tools/ci.sh` + `.git/hooks/pre-commit`
  (local-only); `README.md` real; live DB rebuilt (92 days, 26415 blocks,
  131 matrix, `actor_source` column, outbox 0 rows).
- Gate hit: backend suite 46/46 PASS (38 prior + 8 Phase 3 checks) + ESM +
  sync IN SYNC (4fd07385) + `ci.sh` clean.
- Block raised: NONE.
- Lesson (recorded here): escaped quotes passed through the patch tool
  land literally — use file-native quote style.

## T7 — Phase 4 multi-client + this report (t_a0b46c1a) — DONE (this run)

- Skill used: orio-operations-core (routing + evidence discipline; no UI
  change, so no render claim exists to gate).
- Evidence files (new/changed, all in
  `orio-operations-plugin/`): `dashboard/clients.py` (new; slugs, paths,
  profiles; no sockets, no creds), `dashboard/plugin_api.py` (21 routes
  client-scoped via `x-orio-client` > `?client=` > #1; unknown 404; new
  `GET /clients`, `GET /clients/{slug}`), `data/build_db.py` (`--client`,
  `main(argv)`, `meta.client`), `tools/onboard_client.sh` (new),
  `tests/run_api.py` (+16 Phase 4 checks), `tools/sync_ui.sh` (copies
  `clients.py`), `README.md` / `HANDOFF.md` (per-client paths), this file.
- Client-2 dry-run onboard CLEAN 2026-10-15 (observed, not inferred):
  `profiles/ajeez-orio/state/demo-client-2/` holds `client.json`
  (folders + channels all blocked + cadence), `credentials/README.md`
  (placeholder only — secrets to keyring/.env, never here),
  `incoming/`, `orio_demo.db` (`meta.client=demo-client-2`, 92 days /
  26415 blocks / 131 matrix rows). Client #1 DB timestamp unchanged
  (21:18, untouched by onboarding); live #1 DB then rebuilt with the new
  builder (same counts + `meta.client=orio-ops`, outbox 0).
- Gate hit (all observed this run): backend suite 62/62 PASS
  (`FAILURES: none`; 46 prior + 16 Phase 4: default/#2 health+meta,
  header-wins, unknown-404, badslug-400, write-isolation
  c1=Probe/c2=Client2Probe, clients list/profile, clients/channels/onboard
  no-net/no-creds) + `node --input-type=module --check` ESM_OK +
  `sync_ui.sh` IN SYNC + `ci.sh` clean. Installed `plugins/` copy holds
  `clients.py` (CRLF-normalized md5 9110c08a, identical to repo).
- Block raised: NONE. No fork: `git status` shows only the intended file
  set; client selection is per-request, never a branch.
- Lesson (recorded here): thread per-request tenancy through one
  header-wins/query-fallback/default helper so all routes stay uniform
  without changing route shapes the UI already calls (new params optional);
  refactor `build_db.main(argv)` so the suite builds a second client DB
  in-process instead of shelling out.

## Skills updated across T1-T7

NONE via tooling — `skill_manage` does not exist in this runtime (recorded
independently in T1, T2, T3, T5, T6, and confirmed again in T7: no skill
write tool is available to this profile). Every lesson above is preserved
in its task's kanban comment/metadata and in this report. Recommended
follow-up for the Founder: apply the seven lessons to the `orio-*` skills
from a session that has skill-write access.

## Standing open items (for Ajeez / Founder — unchanged by training)

1. Render QA screenshots (Market Intel, Today gutter, Rigs day-selector,
   narrow pane) — never claimed by any run.
2. The 2 supervisor-flagged June rows (T1b) — identify or rule out.
3. Date normalization rule (05:00-05:00 vs report date) — awaiting Ajeez.
4. Jun-26 `LMR06262026.pdf` has no text layer — re-source or accept gap.
5. HP-701 MDD identifiers (PO, shipment, signature contact) + SP-32
   resolution — source data required.
6. Stale unscoped `hermes/state/orio-ops/orio_demo.db` (Oct 5) — delete it.
7. Optional next: UI client switcher (`?client=` selector in toolbar);
   Phase 4 backend already supports it — deliberately left out of T7 to
   keep the gate to backend + sync.
