"""ORIO Operations — Phase 4 per-client workspace (Ajeez = client #1, no fork).

One codebase serves every client. The only per-client state is a folder::

    <HERMES_HOME>/state/<client>/orio_demo.db   demo database (WAL)
    <HERMES_HOME>/state/<client>/client.json    config profile
    <HERMES_HOME>/state/<client>/incoming/      drop folder for new source files
    <HERMES_HOME>/state/<client>/credentials/   placeholder only (see below)

Onboarding client #2 is: new folder + new profile (``client.json``) +
credential placeholders. No code fork, no new service, no rewrite.

Credentials live per-profile in ``.env``/keyring — never in the repo, never
in this module, never in ``client.json``. The ``credentials/`` folder holds
only a README saying where the real secrets live. This module opens no
sockets and imports no network/mail libraries.

Client #1 is ``orio-ops`` (Ajeez Sebastian's 90-day pilot). The backend and
``data/build_db.py`` both default to it, so every pre-Phase-4 caller keeps
working unchanged.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

try:  # available in-gateway; tests get it via the hermes-agent venv
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover - defensive fallback
    def get_hermes_home() -> Path:  # type: ignore[misc]
        return Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')


#: Client #1 — Ajeez Sebastian's pilot. The default everywhere.
DEFAULT_CLIENT = 'orio-ops'

#: Client slugs are filesystem + URL path segments. Lowercase, short.
_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,31}$')

DB_FILENAME = 'orio_demo.db'
CONFIG_FILENAME = 'client.json'


class UnknownClient(ValueError):
    """Raised when a slug is well-formed but has no onboarded workspace."""


def check_slug(slug: str) -> str:
    """Validate a client slug. Returns it unchanged; raises ValueError."""
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        raise ValueError(
            'bad client slug %r (want ^[a-z0-9][a-z0-9-]{1,32}$)' % (slug,))
    return slug


def state_dir(home: Path | str, client: str = DEFAULT_CLIENT) -> Path:
    """Per-client workspace folder: ``<home>/state/<client>/``."""
    return Path(home) / 'state' / check_slug(client)


def db_path(home: Path | str, client: str = DEFAULT_CLIENT) -> Path:
    """Per-client demo database path."""
    return state_dir(home, client) / DB_FILENAME


def config_path(home: Path | str, client: str = DEFAULT_CLIENT) -> Path:
    """Per-client config profile path."""
    return state_dir(home, client) / CONFIG_FILENAME


def default_config(client: str, display_name: str = '') -> dict:
    """Fresh config profile for a new client. Pure data — no I/O."""
    check_slug(client)
    return {
        'client': client,
        'display_name': display_name or client,
        'folders': {
            'incoming': 'incoming/',
            'ingested_reports': 'ingested/mr/',
            'ingested_tracker': 'ingested/tracker/',
            'ingested_matrix': 'ingested/matrix/',
        },
        'channels': {
            'email': {'state': 'blocked',
                      'adapter': 'Hermes himalaya skill (keyring creds)'},
            'onedrive': {'state': 'blocked',
                         'adapter': 'rclone or microsoft365 catalog plugin'},
            'telegram': {'state': 'blocked',
                         'adapter': 'bundled gateway adapter'},
        },
        'cadence': {
            'report_timezone': 'Asia/Riyadh',
            'daily_ingest': '05:00-05:00 report period',
            'mdd_followup_days': 7,
        },
        'note': ('Demo-local profile. Channels stay BLOCKED until a Founder '
                 'order unblocks them. Credentials live per-profile in '
                 '.env/keyring, never here.'),
    }


def load_config(home: Path | str, client: str) -> dict:
    """Read an onboarded client's profile. Raises UnknownClient if absent."""
    check_slug(client)
    p = config_path(home, client)
    if client != DEFAULT_CLIENT and not p.exists():
        raise UnknownClient('client %r is not onboarded '
                            '(no %s)' % (client, p))
    if p.exists():
        try:
            cfg = json.loads(p.read_text(encoding='utf-8'))
        except Exception as e:  # noqa: BLE001 - corrupt profile, say so
            raise UnknownClient('client %r profile unreadable: %s'
                                % (client, e)) from None
        if not isinstance(cfg, dict) or cfg.get('client') != client:
            raise UnknownClient('client %r profile mismatch '
                                '(client.json names %r)'
                                % (client, (cfg or {}).get('client')))
        return cfg
    # Backward compat: client #1 predates profiles; synthesize its defaults.
    return default_config(client, 'Ajeez Sebastian (ORIO pilot, client #1)')


def save_config(home: Path | str, cfg: dict) -> Path:
    """Write a client's profile. Returns the path written."""
    client = check_slug((cfg or {}).get('client') or '')
    p = config_path(home, client)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cfg, indent=2) + '\n', encoding='utf-8')
    return p


def list_clients(home: Path | str) -> list[dict]:
    """Every onboarded client. Client #1 is always listed (synthesized
    defaults when it has no profile file yet)."""
    home = Path(home)
    found: dict[str, dict] = {}
    state = home / 'state'
    if state.is_dir():
        for child in sorted(state.iterdir()):
            if child.is_dir() and _SLUG_RE.match(child.name):
                if (child / CONFIG_FILENAME).exists():
                    try:
                        found[child.name] = load_config(home, child.name)
                    except UnknownClient:
                        continue
    if DEFAULT_CLIENT not in found:
        found[DEFAULT_CLIENT] = load_config(home, DEFAULT_CLIENT)
    return [{'client': slug,
             'display_name': cfg.get('display_name', slug),
             'onboarded': (state_dir(home, slug) / CONFIG_FILENAME).exists(),
             'has_db': (state_dir(home, slug) / DB_FILENAME).exists()}
            for slug, cfg in sorted(found.items())]


def resolve_client(raw: str | None, home: Path | str) -> str:
    """Map a request claim (header/query) to an onboarded client slug.

    Empty/None -> client #1 (backward compat). Well-formed but not
    onboarded -> UnknownClient (callers answer 404, never auto-create).
    """
    slug = (raw or '').strip() or DEFAULT_CLIENT
    check_slug(slug)
    load_config(home, slug)  # raises UnknownClient when absent
    return slug
