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
cp "$REPO/dashboard/manifest.json"    "$PLUGINS/dashboard/manifest.json"
cp "$REPO/plugin.yaml"                "$PLUGINS/plugin.yaml"
for f in build_db.py ingest_mr.py ingest_tracker.py ingest_matrix.py \
         mr_index.json seed_cases.json; do
  [ -f "$REPO/data/$f" ] && cp "$REPO/data/$f" "$PLUGINS/data/$f"
done

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
