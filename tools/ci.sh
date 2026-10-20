#!/usr/bin/env bash
# ORIO plugin CI: the WHOLE suite + ESM gates + mirror-sync gate (M1).
# Runs on commit (see .git/hooks/pre-commit, installed locally, not
# committed) and on demand:
#   bash tools/ci.sh
#
# Green CI means green plugin: run_api (backend incl. June adjudicated
# acceptance), test_api, test_matrix_separation, lane-7, channels,
# lane-C, jev_repair. The jev repair suite needs no env setup:
# ORIO_REPAIR_OUT defaults to the system temp dir when unset.
set -euo pipefail

REPO="D:/12_projects/Innovex (ajeez)/orio-operations-plugin"
MIRROR="C:/Users/THinkPad/AppData/Local/hermes/desktop-plugins/euphoria-orio-operations"
PLUGINS="C:/Users/THinkPad/AppData/Local/hermes/plugins/euphoria-orio-operations"
PY="C:/Users/THinkPad/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"

echo "== backend suite (run_api) =="
"$PY" "$REPO/tests/run_api.py"

echo "== pytest: test_api =="
"$PY" -m pytest "$REPO/tests/test_api.py" -q

echo "== pytest: test_matrix_separation =="
"$PY" -m pytest "$REPO/tests/test_matrix_separation.py" -q

echo "== pytest: test_empty_states (F1/F2) =="
"$PY" -m pytest "$REPO/tests/test_empty_states.py" -q

echo "== pytest: test_day_picker (FIX6) =="
"$PY" -m pytest "$REPO/tests/test_day_picker.py" -q

echo "== pytest: test_jev_repair =="
"$PY" -m pytest "$REPO/tests/test_jev_repair.py" -q

echo "== lane-7 intelligence =="
"$PY" "$REPO/tests/test_intelligence_lane7.py" | tail -n 3

echo "== channels =="
"$PY" "$REPO/tests/test_channels_offline.py" | tail -n 3

echo "== lane-C =="
"$PY" "$REPO/tests/lane_c_check.py" | tail -n 30

echo "== whole-dir pytest collection (M2 gate) =="
cd "$REPO" && "$PY" -m pytest tests/ --collect-only -q

echo "== ESM gate on repo UI file =="
node --input-type=module --check < "$REPO/desktop/plugin.js" && echo "ESM_OK"

echo "== mirror-sync gate (m1): served mirror must match repo =="
a=$(tr -d '\r' < "$MIRROR/plugin.js" | md5sum | cut -d' ' -f1)
b=$(tr -d '\r' < "$REPO/desktop/plugin.js" | md5sum | cut -d' ' -f1)
if [ "$a" = "$b" ]; then echo "IN SYNC  ($a)"; else echo "MISMATCH ($a vs $b) — run bash tools/sync_ui.sh"; exit 1; fi

echo "== backend-sync gate (m1b): installed backend must match repo =="
drift=0
for f in dashboard/plugin_api.py dashboard/channels.py dashboard/clients.py \
         dashboard/intelligence.py dashboard/manifest.json plugin.yaml \
         data/company_aliases.json data/intelligence_questions.json \
         data/registers/dv-june-adjudicated.json \
         data/registers/lane4-reconciliation-round2.json \
         data/registers/lane4-timing-ledger.json \
         data/registers/coverage-ledger.json \
         data/registers/adjudication-table.json \
         data/ingested/matrix/June2026-adjudicated-v2.json; do
  if [ ! -f "$PLUGINS/$f" ]; then echo "MISSING installed $f"; drift=1; continue; fi
  a=$(tr -d '\r' < "$PLUGINS/$f" | md5sum | cut -d' ' -f1)
  b=$(tr -d '\r' < "$REPO/$f" | md5sum | cut -d' ' -f1)
  if [ "$a" != "$b" ]; then echo "DRIFT $f"; drift=1; fi
done
if [ -f "$PLUGINS/data/ingested/matrix/June2026.json" ]; then
  echo "STALE installed data/ingested/matrix/June2026.json (v1 retired upstream)"
  drift=1
fi
if [ "$drift" != "0" ]; then echo "backend out of sync — run bash tools/sync_ui.sh"; exit 1; fi
echo "BACKEND IN SYNC"

echo "== served-home DB drift gate (fix5): served shells must not run stale data =="
"$PY" "$REPO/tools/check_served_dbs.py"

echo "CI clean."
