"""Lane F offline channel checks (no pytest in the hermes venv).

Covers ONLY what can be done without live credentials or network:
config validation, payload/manifest validation, retry policy math,
error classification, blocked-delivery discipline, activation
checklists, and fixture agreement. NOTHING here sends, uploads, or
posts — and nothing here may be read as a live-channel test.
Exit non-zero on failure.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG / 'dashboard'))

import channels as ch

def main():
    fails = []
    passed = []


    def check(name, cond, extra=''):
        print(('PASS' if cond else 'FAIL'), name, extra)
        (passed if cond else fails).append(name)


    FIX = HERE / 'fixtures' / 'channels'

    # ---- config validation ----
    good_email = {'himalaya_profile': 'orio-test', 'from_address': 'orio@test.invalid',
                  'test_recipient': 'probe@test.invalid'}
    check('cfg-email-good', ch.validate_channel_config('email', good_email) == [],
          str(ch.validate_channel_config('email', good_email)))
    errs = ch.validate_channel_config('email', {})
    check('cfg-email-missing', len(errs) == 3 and all('never a secret' in e for e in errs), str(errs))
    bad = dict(good_email, from_address='not-an-address')
    check('cfg-email-bad-from', any('from_address' in e for e in
          ch.validate_channel_config('email', bad)), str(bad))
    active = dict(good_email, state='active')
    check('cfg-email-active-rejected', any('unblock' in e for e in
          ch.validate_channel_config('email', active)))
    good_od = {'adapter': 'rclone', 'test_folder': '/ORIO-TEST-lane-f'}
    check('cfg-onedrive-good', ch.validate_channel_config('onedrive', good_od) == [])
    for folder, label in [('/', 'root'), ('root', 'root-word'), ('/a/../b', 'dotdot'),
                          ('', 'empty'), (None, 'none')]:
        bad_od = {'adapter': 'rclone', 'test_folder': folder}
        check('cfg-onedrive-%s-rejected' % label,
              any('folder' in e for e in ch.validate_channel_config('onedrive', bad_od)),
              repr(folder))
    good_tg = {'gateway_profile': 'orio-test', 'bot_token_ref': 'keyring:orio-tg-bot',
               'test_chat_ref': 'test-chat'}
    check('cfg-telegram-good', ch.validate_channel_config('telegram', good_tg) == [])
    check('cfg-unknown-channel', any('unknown channel' in e for e in
          ch.validate_channel_config('fax', {})))
    check('cfg-non-dict', any('mapping' in e for e in
          ch.validate_channel_config('email', ['not', 'a', 'dict'])))

    # ---- payload validation ----
    payload = ch.build_email_payload(recipient='r@test.invalid', subject='s',
                                     body='b', attachments=[], ref='t')
    check('payload-email-good', ch.validate_payload(payload) == [])
    check('payload-email-missing', len(ch.validate_payload({})) == 3,
          str(ch.validate_payload({})))
    tg_payload = dict(payload, subject='')
    check('payload-telegram-no-subject-ok',
          ch.validate_payload(tg_payload, channel='telegram') == [])
    check('payload-email-needs-subject',
          any('subject' in e for e in ch.validate_payload(tg_payload)))
    check('payload-bad-attachments',
          any('attachments' in e for e in
              ch.validate_payload(dict(payload, attachments='nope')))
          and any('attachments[1]' in e for e in
                  ch.validate_payload(dict(payload, attachments=['a.pdf', '', None]))))
    check('payload-non-dict', ch.validate_payload(None) == ['payload must be a mapping'])

    # ---- upload manifest ----
    manifest = {'name': 'lane-f-harmless-probe.txt', 'size_bytes': 64,
                'remote_folder': '/ORIO-TEST-lane-f'}
    check('manifest-good', ch.validate_upload_manifest(manifest) == [])
    check('manifest-bad', len(ch.validate_upload_manifest(
        {'name': '', 'size_bytes': -1, 'remote_folder': '/'})) == 3)
    check('manifest-bool-size-rejected',
          any('size_bytes' in e for e in
              ch.validate_upload_manifest(dict(manifest, size_bytes=True))))
    check('manifest-non-dict', ch.validate_upload_manifest(None) != [])

    # ---- retry policy ----
    p = ch.RetryPolicy()
    check('backoff-exact',
          [ch.backoff_delay(p, a) for a in (1, 2, 3, 4, 5)] == [2.0, 4.0, 8.0, 16.0, 32.0])
    check('backoff-cap', ch.backoff_delay(p, 10) == 300.0)
    check('backoff-zero', ch.backoff_delay(p, 0) == 0.0)
    for kwargs in ({'max_attempts': 0}, {'base_delay_s': 0}, {'max_delay_s': 1.0}):
        try:
            ch.RetryPolicy(**dict({'base_delay_s': 2.0, 'max_delay_s': 300.0,
                                   'max_attempts': 5}, **kwargs))
            check('policy-rejects-%s' % sorted(kwargs), False)
        except ValueError:
            check('policy-rejects-%s' % sorted(kwargs), True)
    check('retry-yes', ch.should_retry(p, 'timeout', 1) is True
          and ch.should_retry(p, 'rate_limited', 4) is True)
    check('retry-exhausted', ch.should_retry(p, 'timeout', 5) is False
          and ch.should_retry(p, 'timeout', 6) is False)
    for kind in ('blocked', 'auth', 'validation', 'config', 'unknown', 'mystery'):
        check('retry-never-%s' % kind, ch.should_retry(p, kind, 1) is False)
    custom = ch.RetryPolicy(retryable=('timeout',))
    check('retry-custom-scope', ch.should_retry(custom, 'timeout', 1) is True
          and ch.should_retry(custom, 'unavailable', 1) is False)

    # ---- error classification (fixture-driven) ----
    cases = json.loads((FIX / 'classification_cases.json').read_text())
    bad_cases = [c for c in cases
                 if ch.classify_error(c['message']) != c['kind']]
    check('classify-fixture', not bad_cases and len(cases) == 10, str(bad_cases))
    check('classify-none', ch.classify_error(None) == 'unknown')

    # ---- blocked discipline still holds ----
    for name in ('email', 'onedrive', 'telegram'):
        chan = ch.get_channel(name)
        art = chan.prepare(payload)
        rcpt = chan.deliver(art)
        check('blocked-%s' % name,
              art['state'] == 'blocked' and rcpt['delivered'] is False
              and rcpt['state'] == 'blocked' and bool(rcpt['reason']))
    try:
        ch.get_channel('fax')
        check('unknown-channel-raises', False)
    except KeyError:
        check('unknown-channel-raises', True)

    # ---- activation checklists (exact remaining steps, all unverified) ----
    for name in ('email', 'onedrive', 'telegram'):
        steps = ch.activation_checklist(name)
        check('checklist-%s' % name,
              len(steps) >= 3 and any('unblock' in s for s in steps)
              and any('uthoriz' in s or 'Ajeez' in s for s in steps),
              '%d steps' % len(steps))
    try:
        ch.activation_checklist('fax')
        check('checklist-unknown-raises', False)
    except KeyError:
        check('checklist-unknown-raises', True)

    # ---- loopback outbox (offline fixture, not a transport) ----
    box = ch.LoopbackOutbox()
    r0 = box.store(ch.get_channel('email').prepare(payload))
    r1 = box.store(ch.get_channel('telegram').prepare(tg_payload))
    check('loopback-store', r0 == {'stored': True, 'state': 'blocked', 'index': 0}
          and r1['index'] == 1 and len(box.records) == 2)

    # ---- fixtures agree with validators ----
    email_fix = json.loads((FIX / 'email_draft.json').read_text())
    od_fix = json.loads((FIX / 'onedrive_upload.json').read_text())
    tg_fix = json.loads((FIX / 'telegram_message.json').read_text())
    check('fixture-email', ch.validate_payload(email_fix) == [])
    check('fixture-onedrive', ch.validate_upload_manifest(
        {'name': od_fix['name'], 'size_bytes': od_fix['size_bytes'],
         'remote_folder': od_fix['remote_folder']}) == [])
    check('fixture-telegram', ch.validate_payload(tg_fix, channel='telegram') == [])

    # ---- failure/retry walk-through on the loopback (no network) ----
    policy = ch.RetryPolicy(max_attempts=3, base_delay_s=2.0)
    script = ['timeout', 'rate_limited', 'auth']  # kinds the "transport" reports
    waits, stopped = [], None
    for attempt, kind in enumerate(script, start=1):
        if ch.should_retry(policy, kind, attempt):
            waits.append(ch.backoff_delay(policy, attempt))
        else:
            stopped = (kind, attempt)
            break
    check('retry-walk', waits == [2.0, 4.0] and stopped == ('auth', 3),
          'waits=%s stopped=%s' % (waits, stopped))

    # ---- static guards: still no network imports, no secret material ----
    chsrc = (PKG / 'dashboard' / 'channels.py').read_text()
    check('channels-no-net',
          all(('import ' + m) not in chsrc and ('from ' + m) not in chsrc
              for m in ['socket', 'urllib', 'httpx', 'requests', 'smtplib',
                        'email.mime']))
    check('channels-no-creds', 'api_key' not in chsrc.lower()
          and 'passwd' not in chsrc.lower() and 'BEGIN ' not in chsrc)

    print('LANE-F-CHANNELS: %d passed, %d failed' % (len(passed), len(fails)))
    print('FAILURES:', fails if fails else 'none')
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
