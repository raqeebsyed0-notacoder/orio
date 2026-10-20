#!/usr/bin/env bash
# Sync the ORIO plugin from the repo to BOTH installed copies, then gate.
#
# Why this exists: the desktop app loads ONLY the desktop-plugins mirror, and
# the gateway loads the plugins/ copy. Editing the repo alone changes nothing
# the operator can see. Manual copying caused past outages; this makes the
# three-copy ritual one command.
#
# Usage:  bash tools/sync_ui.sh [--no-backend]
set -euo pipefail

REPO="D:/12_projects/Innovex (ajeez)/orio-operations-plugin"
PLUGINS="C:/Users/THinkPad/AppData/Local/hermes/plugins/euphoria-orio-operations"
MIRROR="C:/Users/THinkPad/AppData/Local/hermes/desktop-plugins/euphoria-orio-operations"

echo "== syncing repo -> plugins/ =="
mkdir -p "$PLUGINS/desktop" "$PLUGINS/dashboard" "$PLUGINS/data"
cp "$REPO/desktop/plugin.js"          "$PLUGINS/desktop/plugin.js"
cp "$REPO/dashboard/plugin_api.py"    "$PLUGINS/dashboard/plugin_api.py"
cp "$REPO/dashboard/channels.py"      "$PLUGINS/dashboard/channels.py"
cp "$REPO/dashboard/clients.py"       "$PLUGINS/dashboard/clients.py"
cp "$REPO/dashboard/intelligence.py"  "$PLUGINS/dashboard/intelligence.py"
cp "$REPO/dashboard/manifest.json"    "$PLUGINS/dashboard/manifest.json"
cp "$REPO/plugin.yaml"                "$PLUGINS/plugin.yaml"
for f in build_db.py ingest_mr.py ingest_tracker.py ingest_matrix.py ingest_adjudicated.py jev_consume.py \
         mr_index.json seed_cases.json company_aliases.json intelligence_questions.json; do
  [ -f "$REPO/data/$f" ] && cp "$REPO/data/$f" "$PLUGINS/data/$f"
done
mkdir -p "$PLUGINS/data/registers"
for f in dv-june-adjudicated.json lane4-reconciliation-round2.json lane4-timing-ledger.json coverage-ledger.json adjudication-table.json; do
  [ -f "$REPO/data/registers/$f" ] && cp "$REPO/data/registers/$f" "$PLUGINS/data/registers/$f"
done
mkdir -p "$PLUGINS/data/ingested/matrix/_retired-v1"
cp "$REPO/data/ingested/matrix/June2026-adjudicated-v2.json" "$PLUGINS/data/ingested/matrix/" 2>/dev/null || true
cp "$REPO/data/ingested/matrix/_retired-v1/"* "$PLUGINS/data/ingested/matrix/_retired-v1/" 2>/dev/null || true
# The stale v1 workbook (June2026.json, 131 hand-built rows) was retired
# upstream to data/ingested/matrix/_retired-v1/ (lineage README there).
# A leftover top-level copy in the installed tree would load into a
# gateway-side build — remove it once the retired copy is in place.
if [ -f "$PLUGINS/data/ingested/matrix/_retired-v1/June2026.json" ]; then
  rm -f "$PLUGINS/data/ingested/matrix/June2026.json"
fi

echo "== syncing repo tests -> plugins/tests =="
mkdir -p "$PLUGINS/tests"
for f in lane_c_check.py run_api.py test_api.py test_jev_repair.py test_matrix_separation.py test_intelligence_lane7.py test_channels_offline.py; do
  [ -f "$REPO/tests/$f" ] && cp "$REPO/tests/$f" "$PLUGINS/tests/$f"
done
[ -d "$REPO/tests/fixtures" ] && mkdir -p "$PLUGINS/tests/fixtures" && cp -r "$REPO/tests/fixtures/." "$PLUGINS/tests/fixtures/" 2>/dev/null || true

echo "== syncing repo -> desktop-plugins mirror =="
mkdir -p "$MIRROR"
cp "$REPO/desktop/plugin.js" "$MIRROR/plugin.js"

echo "== ESM gate on the mirror (the copy the app actually loads) =="
node --input-type=module --check < "$MIRROR/plugin.js" && echo "ESM_OK"

echo "== byte check: mirror vs repo (CRLF-normalized) =="
a=$(tr -d '\r' < "$MIRROR/plugin.js" | md5sum | cut -d' ' -f1)
b=$(tr -d '\r' < "$REPO/desktop/plugin.js" | md5sum | cut -d' ' -f1)
if [ "$a" = "$b" ]; then echo "IN SYNC  ($a)"; else echo "MISMATCH ($a vs $b)"; exit 1; fi

if [ "${1:-}" != "--no-backend" ]; then
  echo "== backend suite =="
  PY="C:/Users/THinkPad/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"
  "$PY" "$REPO/tests/run_api.py" | tail -n 3
fi

echo
echo "Next: in Hermes Desktop press Cmd/Ctrl+K -> Reload desktop plugins."
