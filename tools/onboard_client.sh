#!/usr/bin/env bash
# Onboard a new ORIO client (Phase 4). Dry-run, demo-local only.
#
# Client #2 onboarding = new folder + new profile + credential
# placeholders. No code fork: the same repo code serves every client,
# selected per request via `x-orio-client` / `?client=` (default #1).
#
# What this creates under <HERMES_HOME>/state/<slug>/:
#   client.json        config profile (folders, channels, cadence)
#   orio_demo.db       demo database (built by data/build_db.py)
#   incoming/          drop folder for that client's source files
#   credentials/       README ONLY — real secrets live per-profile in
#                      .env/keyring, never in the repo, never here.
#
# Usage:  bash tools/onboard_client.sh <slug> [display-name]
#   slug: ^[a-z0-9][a-z0-9-]{1,32}$   (e.g. demo-client-2)
#
# Nothing sends, no sockets, no external connect. Refuses to overwrite
# an onboarded client (no --force path: onboarding runs once).
set -euo pipefail

REPO="D:/12_projects/Innovex (ajeez)/orio-operations-plugin"
PY="C:/Users/THinkPad/AppData/Local/hermes/hermes-agent/venv/Scripts/python.exe"

SLUG="${1:-}"
DISPLAY="${2:-$SLUG}"

if ! printf '%s' "$SLUG" | grep -Eq '^[a-z0-9][a-z0-9-]{1,31}$'; then
  echo "ERROR: bad slug '$SLUG' (want ^[a-z0-9][a-z0-9-]{1,32}\$)" >&2
  echo "Usage: bash tools/onboard_client.sh <slug> [display-name]" >&2
  exit 2
fi
if [ "$SLUG" = "orio-ops" ]; then
  echo "ERROR: 'orio-ops' is client #1 (Ajeez) — already onboarded." >&2
  exit 2
fi

# HERMES_HOME is the profile home when run from a profile session
# (e.g. .../profiles/ajeez-orio); falls back to the platform default.
HOME_DIR="${HERMES_HOME:-C:/Users/THinkPad/AppData/Local/hermes}"
STATE="$HOME_DIR/state/$SLUG"

if [ -f "$STATE/client.json" ]; then
  echo "ERROR: client '$SLUG' already onboarded ($STATE/client.json exists)." >&2
  echo "Onboarding runs once per client; nothing was changed." >&2
  exit 1
fi

echo "== onboarding client '$SLUG' ($DISPLAY) =="
echo "   workspace: $STATE"
mkdir -p "$STATE/incoming" "$STATE/credentials"

echo "== writing config profile =="
SLUG="$SLUG" DISPLAY="$DISPLAY" HOME_DIR="$HOME_DIR" "$PY" - <<'EOF'
import os, sys
sys.path.insert(0, os.path.join(
    "D:/12_projects/Innovex (ajeez)/orio-operations-plugin", "dashboard"))
from clients import default_config, save_config
from pathlib import Path
home = Path(os.environ["HOME_DIR"])
cfg = default_config(os.environ["SLUG"], os.environ["DISPLAY"])
p = save_config(home, cfg)
print("profile:", p)
EOF

cat > "$STATE/credentials/README.md" <<EOF
# Credentials for client `$SLUG` — PLACEHOLDER ONLY (dry-run)

No secrets live here, in the repo, or in `client.json`. On unblock day,
per-profile credentials go to:

- email    -> Hermes \`himalaya\` skill via OS keyring (per-profile \`.env\`)
- onedrive -> \`rclone\` config or the \`microsoft365\` catalog plugin
- telegram -> bundled gateway adapter config

All channels are BLOCKED until a Founder order unblocks them.
See \`dashboard/channels.py\` for the documented unblock-day adapters.
EOF
echo "credentials placeholder: $STATE/credentials/README.md"

echo "== building demo database =="
"$PY" "$REPO/data/build_db.py" --client "$SLUG"

echo "== verifying isolation =="
SLUG="$SLUG" HOME_DIR="$HOME_DIR" "$PY" - <<'EOF'
import os, sqlite3
from pathlib import Path
p = Path(os.environ["HOME_DIR"]) / "state" / os.environ["SLUG"] / "orio_demo.db"
con = sqlite3.connect(str(p))
one = lambda q: con.execute(q).fetchone()[0]
print("db:", p)
print("meta.client:", con.execute(
    "SELECT value FROM meta WHERE key='client'").fetchone()[0])
print("reports:", one("SELECT COUNT(*) FROM reports"),
      "| rig_blocks:", one("SELECT COUNT(*) FROM rig_blocks"),
      "| matrix_rows:", one("SELECT COUNT(*) FROM matrix_rows"))
con.close()
EOF

echo
echo "Client '$SLUG' onboarded: folder + profile + credentials placeholder."
echo "Same code, no fork. Select it per request: ?client=$SLUG"
echo "Client #1 (orio-ops) untouched."
