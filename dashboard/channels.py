"""ORIO Operations — Phase 2 channel seams (blocked-channel discipline).

Nothing sends today. Email / OneDrive / Telegram are BLOCKED: every channel
is a ``BlockedChannel`` stub that builds a local delivery payload
(recipient, subject, body, attachments), stores it in the demo database, and
refuses to deliver with a machine-readable blocked+reason receipt.

Unblock day (documented only — no adapter is implemented here):
  - email    -> Hermes ``himalaya`` skill (CLI over IMAP/SMTP, keyring creds).
  - onedrive -> ``rclone`` (winget) or the ``microsoft365`` catalog plugin
                (pre-release; trial on a tenant before trusting writes).
  - telegram -> bundled gateway adapter
                (``hermes-agent/plugins/platforms/telegram/``).

Credentials live per-profile in ``.env``/keyring — never in the repo, never
in a skill, never in this module. This module opens no sockets and imports
no network/mail libraries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


class DeliveryChannel(Protocol):
    """The seam every channel — blocked today, real on unblock day — implements."""

    name: str

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Build a local delivery artifact from a payload. No external effect."""
        ...

    def deliver(self, artifact: dict[str, Any]) -> dict[str, Any]:
        """Hand an artifact to the transport. Blocked stubs refuse here."""
        ...

    def status(self) -> dict[str, Any]:
        """Machine-readable channel state: blocked + reason while stubbed."""
        ...


@dataclass
class BlockedChannel:
    """Stub transport: prepares local artifacts, refuses delivery.

    ``prepare`` succeeds (local-only artifact, safe to store); ``deliver``
    always returns ``{'delivered': False, 'state': 'blocked', ...}`` and
    performs no external action — there is no transport code to call.
    """

    name: str
    reason: str
    unblock_adapter: str
    extra: dict[str, Any] = field(default_factory=dict)

    def prepare(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            'channel': self.name,
            'state': 'blocked',
            'blocked_reason': self.reason,
            'payload': {
                'recipient': payload.get('recipient'),
                'subject': payload.get('subject'),
                'body': payload.get('body'),
                'attachments': list(payload.get('attachments') or []),
                'ref': payload.get('ref'),
            },
            'stored_only': True,
        }

    def deliver(self, artifact: dict[str, Any]) -> dict[str, Any]:
        return {
            'delivered': False,
            'state': 'blocked',
            'channel': self.name,
            'reason': self.reason,
            'unblock_adapter': self.unblock_adapter,
            'artifact_ref': (artifact or {}).get('payload', {}).get('ref'),
        }

    def status(self) -> dict[str, Any]:
        return {
            'channel': self.name,
            'state': 'blocked',
            'reason': self.reason,
            'unblock_adapter': self.unblock_adapter,
        }


CHANNELS: dict[str, BlockedChannel] = {
    'email': BlockedChannel(
        name='email',
        reason='BLOCKED: email transport not enabled. Payloads are prepared '
               'and stored locally only; nothing is sent.',
        unblock_adapter='Hermes himalaya skill (CLI over IMAP/SMTP, keyring creds).',
    ),
    'onedrive': BlockedChannel(
        name='onedrive',
        reason='BLOCKED: OneDrive transport not enabled. Payloads are prepared '
               'and stored locally only; nothing is uploaded.',
        unblock_adapter='rclone (winget) or the microsoft365 catalog plugin '
                        '(pre-release; trial on a tenant before trusting writes).',
    ),
    'telegram': BlockedChannel(
        name='telegram',
        reason='BLOCKED: Telegram transport not enabled. Payloads are prepared '
               'and stored locally only; nothing is posted.',
        unblock_adapter='Bundled gateway adapter '
                        '(hermes-agent/plugins/platforms/telegram/).',
    ),
}


def get_channel(name: str) -> BlockedChannel:
    """Return the stub for a known channel, else raise KeyError (never guess)."""
    try:
        return CHANNELS[name]
    except KeyError:
        raise KeyError('unknown channel: %r (known: %s)'
                       % (name, sorted(CHANNELS))) from None


def all_statuses() -> list[dict[str, Any]]:
    """Machine-readable status for every configured channel."""
    return [ch.status() for ch in CHANNELS.values()]


def build_email_payload(*, recipient: str, subject: str, body: str,
                        attachments: list[Any] | None = None,
                        ref: str | None = None) -> dict[str, Any]:
    """Shape a delivery payload. Pure data — no send, no store, no I/O."""
    return {
        'recipient': recipient,
        'subject': subject,
        'body': body,
        'attachments': list(attachments or []),
        'ref': ref,
    }


# ------------------------------------------------- Lane F offline seams
# Adapter config validation + payload validation + retry policy + error
# classification. Pure data + pure functions: no sockets, no mail/network
# imports, no secret values. Configs hold REFERENCES (keyring entry names,
# profile names, test folder paths) — never secret material. Delivery stays
# BLOCKED: nothing in this section can send, upload, or post. Anything that
# needs live credentials or a network round-trip is listed per channel in
# ``activation_checklist`` and is explicitly NOT verified here.

#: Required config keys per channel. Values are references, not secrets.
CHANNEL_CONFIG_SCHEMA: dict[str, tuple[str, ...]] = {
    'email': ('himalaya_profile', 'from_address', 'test_recipient'),
    'onedrive': ('adapter', 'test_folder'),
    'telegram': ('gateway_profile', 'bot_token_ref', 'test_chat_ref'),
}

#: Error kinds that must never be retried (fail closed, surface to operator).
FATAL_KINDS = frozenset({'blocked', 'auth', 'validation', 'config'})


@dataclass(frozen=True)
class RetryPolicy:
    """Offline retry contract shared by all future transports.

    ``attempt`` is 1-based: the failed attempt that just completed.
    All math is deterministic (no jitter) so tests pin exact delays.
    """

    max_attempts: int = 5
    base_delay_s: float = 2.0
    max_delay_s: float = 300.0
    retryable: tuple[str, ...] = ('timeout', 'rate_limited', 'unavailable')

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError('max_attempts must be >= 1')
        if self.base_delay_s <= 0 or self.max_delay_s <= 0:
            raise ValueError('delays must be > 0')
        if self.max_delay_s < self.base_delay_s:
            raise ValueError('max_delay_s must be >= base_delay_s')


def backoff_delay(policy: RetryPolicy, attempt: int) -> float:
    """Seconds to wait before the next try after failed ``attempt``.

    Exponential (base * 2**(attempt-1)) capped at ``max_delay_s``.
    ``attempt`` < 1 answers 0.0 (nothing has failed yet).
    """
    if attempt < 1:
        return 0.0
    return min(policy.max_delay_s,
               policy.base_delay_s * (2.0 ** (attempt - 1)))


def should_retry(policy: RetryPolicy, error_kind: str, attempt: int) -> bool:
    """True only for a retryable kind with attempts remaining.

    Fatal kinds (blocked/auth/validation/config) never retry. Unknown
    kinds never retry either — fail closed, surface to the operator.
    """
    if error_kind in FATAL_KINDS:
        return False
    if attempt >= policy.max_attempts:
        return False
    return error_kind in policy.retryable


_ERROR_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ('rate_limited', ('429', 'rate limit', 'throttl', 'too many requests')),
    ('timeout', ('timeout', 'timed out', 'deadline exceeded')),
    ('unavailable', ('503', '502', 'unavailable', 'connection reset',
                      'temporarily', 'service down')),
    ('auth', ('401', '403', 'unauthorized', 'forbidden', 'invalid token',
              'expired token', 'bad credentials')),
)


def classify_error(message: Any) -> str:
    """Map an adapter error string to a retry-kind label. Pure matching.

    Answers one of timeout/rate_limited/unavailable/auth, else 'unknown'
    (which ``should_retry`` treats as fatal — fail closed).
    """
    text = str(message or '').lower()
    for kind, needles in _ERROR_PATTERNS:
        if any(n in text for n in needles):
            return kind
    return 'unknown'


def _folder_errors(folder: Any) -> list[str]:
    """Dedicated-test-folder rule shared by OneDrive config + manifests."""
    if not isinstance(folder, str) or not folder.strip():
        return ['test folder must be a non-empty path (never root)']
    f = folder.strip()
    if f in ('/', '\\', 'root'):
        return ['test folder must be a dedicated folder, never %r' % f]
    if '..' in f.replace('\\', '/').split('/'):
        return ['test folder must not contain ".." (%r)' % f]
    return []


def validate_channel_config(name: str, cfg: Any) -> list[str]:
    """Offline config check. Answers a list of problems (empty = usable).

    A config claiming any state other than 'blocked' is rejected: no
    transport is wired, so 'active' would be a lie ``deliver()`` would
    immediately contradict.
    """
    if name not in CHANNEL_CONFIG_SCHEMA:
        return ['unknown channel: %r (known: %s)'
                % (name, sorted(CHANNEL_CONFIG_SCHEMA))]
    if not isinstance(cfg, dict):
        return ['config for %r must be a mapping' % name]
    errors = ['config for %r is missing %r (a reference, never a secret)'
              % (name, key)
              for key in CHANNEL_CONFIG_SCHEMA[name] if not cfg.get(key)]
    if name == 'email' and cfg.get('from_address') \
            and '@' not in str(cfg['from_address']):
        errors.append('email from_address must be an address (%r is not)'
                      % cfg['from_address'])
    if name == 'onedrive':
        errors.extend('onedrive ' + e for e in
                      _folder_errors(cfg.get('test_folder')))
    if cfg.get('state', 'blocked') != 'blocked':
        errors.append(
            'state %r is not activatable: no transport is wired and '
            'deliver() refuses. Activation needs an explicit unblock '
            'order (see activation_checklist).' % (cfg.get('state'),))
    return errors


def validate_payload(payload: Any, channel: str = 'email') -> list[str]:
    """Offline payload check. Answers a list of problems (empty = shippable).

    Telegram/OneDrive payloads carry no subject line; email requires one.
    """
    if not isinstance(payload, dict):
        return ['payload must be a mapping']
    errors = []
    for key in ('recipient', 'body'):
        if not payload.get(key):
            errors.append('payload is missing %r' % key)
    if channel == 'email' and not payload.get('subject'):
        errors.append("email payload is missing 'subject'")
    attachments = payload.get('attachments') or []
    if not isinstance(attachments, list):
        errors.append('attachments must be a list')
    else:
        for i, a in enumerate(attachments):
            if isinstance(a, str) and a.strip():
                continue
            if isinstance(a, dict) and a.get('name'):
                continue
            errors.append('attachments[%d] must be a name or {name: ...}' % i)
    return errors


def validate_upload_manifest(entry: Any) -> list[str]:
    """Offline OneDrive upload-manifest check (harmless test files only)."""
    if not isinstance(entry, dict):
        return ['manifest entry must be a mapping']
    errors = []
    if not entry.get('name'):
        errors.append('manifest entry is missing name')
    size = entry.get('size_bytes')
    if not isinstance(size, int) or isinstance(size, bool) or size < 0:
        errors.append('size_bytes must be a non-negative int')
    errors.extend('remote ' + e for e in
                  _folder_errors(entry.get('remote_folder')))
    return errors


def activation_checklist(name: str) -> list[str]:
    """Exact steps still required to activate a channel. All UNVERIFIED.

    Nothing here has been exercised against a live account: no message
    sent, no file uploaded, no post published. Each step needs explicit
    destination authorization before it runs.
    """
    if name == 'email':
        return [
            'Ajeez names the Outlook mailbox and a test recipient address '
            '(explicit destination authorization).',
            'Store the himalaya IMAP/SMTP profile credentials in the OS '
            'keyring (never in the repo); record only the profile name in '
            'the client config.',
            'Wire the himalaya send path behind an explicit unblock order; '
            'deliver() keeps refusing until then.',
            'Round-trip test: send one draft to the test recipient, confirm '
            'receipt out-of-band, log the evidence.',
        ]
    if name == 'onedrive':
        return [
            'Ajeez authorizes a dedicated OneDrive test folder (never root, '
            'never an existing docs folder); record the path in config.',
            'Choose the adapter (rclone via winget, or the microsoft365 '
            'catalog plugin after a tenant trial) and authenticate the '
            'harness profile only.',
            'Round-trip test: upload + download + delete HARMLESS fixture '
            'files inside the test folder; touch nothing else.',
            'Wire the upload path behind an explicit unblock order; '
            'deliver() keeps refusing until then.',
        ]
    if name == 'telegram':
        return [
            'Ajeez names the destination chat (explicit destination '
            'authorization) and provides the bot token via the gateway '
            'profile store (config holds only the reference).',
            'Wire the bundled gateway adapter '
            '(hermes-agent/plugins/platforms/telegram/) behind an explicit '
            'unblock order; deliver() keeps refusing until then.',
            'Round-trip test: one harmless test message to the test chat; '
            'confirm receipt out-of-band, log the evidence.',
        ]
    raise KeyError('unknown channel: %r (known: %s)'
                   % (name, sorted(CHANNEL_CONFIG_SCHEMA)))


@dataclass
class LoopbackOutbox:
    """In-memory recorder for OFFLINE TESTS ONLY. Not a transport.

    Lets failure/retry tests exercise prepare -> store -> retry-decision
    without any network, account, or side effect.
    """

    records: list[dict[str, Any]] = field(default_factory=list)

    def store(self, artifact: dict[str, Any]) -> dict[str, Any]:
        self.records.append(artifact)
        return {'stored': True, 'state': (artifact or {}).get('state'),
                'index': len(self.records) - 1}
