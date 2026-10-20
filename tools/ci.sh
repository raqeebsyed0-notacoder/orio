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
PY="C:/Users/THinkPad/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"

echo "== backend suite (run_api) =="
"$PY" "$REPO/tests/run_api.py"

echo "== pytest: test_api =="
"$PY" -m pytest "$REPO/tests/test_api.py" -q

echo "== pytest: test_matrix_separation =="
"$PY" -m pytest "$REPO/tests/test_matrix_separation.py" -q

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

echo "CI clean."
