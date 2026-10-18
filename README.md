# ORIO Operations plugin (Innovex pilot → real product)

ORIO operations console for Ajeez Sebastian's 90-day AI operations pilot,
built as a real product. Ajeez is client #1, not the only client.

Two tracks live side by side and never mix:

1. **ORIO operations** — rig/well/job-cycle lifecycle, reconciliation, MDD.
   Evidence states, approval gates, page lineage.
2. **Market intelligence** — competitor tool-size x company rows mined from
   morning reports. Market observations only, never operational claims.

## Safety (demo-local)

- Local SQLite only (`<HERMES_HOME>/state/<client>/orio_demo.db`, WAL).
  Client #1 is `orio-ops` (Ajeez); each further client gets its own folder
  (see `tools/onboard_client.sh`). No hardcoded client path in code.
- Email / OneDrive / Telegram are BLOCKED stubs: payloads are prepared and
  stored locally, `deliver()` refuses with a blocked+reason receipt.
- Approving an action mutates DEMO STATE ONLY. Nothing sends, no sockets,
  no credentials in the repo.
- Identity of a job is Rig + Well + Job Cycle — never rig alone.

## Layout

- `desktop/plugin.js` — all UI (single ESM file; the app loads ONLY the
  `desktop-plugins/` mirror copy).
- `dashboard/plugin_api.py` — backend (FastAPI, stdlib only; mounts at
  `/api/plugins/euphoria-orio-operations/`). Every route is client-scoped
  (`x-orio-client` header or `?client=`; default #1; unknown 404).
- `dashboard/clients.py` — Phase 4 per-client workspace: slugs, DB/config
  paths, config profiles (folders, channels, cadence). No sockets, no creds.
- `dashboard/channels.py` — `DeliveryChannel` protocol + `BlockedChannel`
  stubs (email/onedrive/telegram; unblock-day adapters documented only).
- `data/build_db.py` + `data/ingest_*.py` + `data/ingested/` — DB build.
- `tests/run_api.py` — backend suite (throwaway home, safe).
- `tools/onboard_client.sh` — onboard a client: folder + profile +
  credential placeholders + demo DB. Same code, no fork.
- `tools/sync_ui.sh` — the ONLY sync path. `tools/ci.sh` — the CI command.
- `HANDOFF.md` — session handoff (resume commands, open items). It is the
  running log, not documentation: read it to resume, not to learn the product.

## Commands

```bash
cd "D:/12_projects/Innovex (ajeez)/orio-operations-plugin"

# CI: backend suite + ESM gate (also runs on commit via .git/hooks/pre-commit)
bash tools/ci.sh

# Sync repo -> plugins/ -> desktop-plugins/ mirror + ESM gate + backend suite
bash tools/sync_ui.sh
# then: Hermes Desktop -> Ctrl/Cmd+K -> Reload desktop plugins

# Ingest a new report day, then rebuild + sync
python3 data/ingest_mr.py "<file>.pdf" --json data/ingested/mr/<file>.json
python3 data/build_db.py
bash tools/sync_ui.sh

# Onboard a new client (folder + profile + creds placeholder + DB, no fork)
bash tools/onboard_client.sh <slug> "[display name]"
# Rebuild one client's DB only
python3 data/build_db.py --client <slug>
```

Config via `hermes config set` only — never hand-edit config files.
UI edits gate on `node --input-type=module --check` (plain `--check`
parses CommonJS and gives a false clean on this ESM file).

## API (selected)

Reads: `/health`, `/meta`, `/reports`, `/rigs`, `/rigs/{rig}/{well}`,
`/jobs/{job_id}`, `/lifecycle`, `/today`, `/actions`, `/exceptions`,
`/history`, `/expansion`, `/matrix`, `/matrix/export.csv`, `/export.csv`,
`/drafts`, `/mdd/preview`, `/channels/status`, `/delivery/outbox`,
`/ops/log` (approval writes + errors; reads are not logged),
`/clients`, `/clients/{slug}` (per-client profiles; client #1 = Ajeez).

Writes (demo only, attributed): `POST /actions/{id}/decision`
(approve/reject/incorrect; actor bound from `x-hermes-user` gateway header,
else client claim marked `client`, else local default — a forged claim
against a gateway header is rejected 400),
`POST /exceptions/{id}/resolve`, `POST /drafts/email` (stored blocked).
