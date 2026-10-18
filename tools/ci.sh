#!/usr/bin/env bash
# ORIO plugin CI: backend suite + ESM gate. Runs on commit (see
# .git/hooks/pre-commit, installed locally, not committed) and on demand:
#   bash tools/ci.sh
set -euo pipefail

REPO="D:/12_projects/Innovex (ajeez)/orio-operations-plugin"
PY="C:/Users/THinkPad/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"

echo "== backend suite =="
"$PY" "$REPO/tests/run_api.py" | tail -n 3

echo "== ESM gate on repo UI file =="
node --input-type=module --check < "$REPO/desktop/plugin.js" && echo "ESM_OK"

echo "CI clean. Then sync copies: bash tools/sync_ui.sh"
