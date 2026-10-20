"""Served-home DB drift gate (FIX5, 2026-10-21): every served HERMES_HOME needs
its own rebuild — gates that build to a temp home can never see a stale
served DB (default home showed 185 stale rows while temp-home gates were
green). Read-only; exits non-zero on drift.

Usage:  python3 tools/check_served_dbs.py [--home PATH]...
Default homes (served shells):
  C:/Users/THinkPad/AppData/Local/hermes                  (DEFAULT, Founder live shell)
  C:/Users/THinkPad/AppData/Local/hermes/profiles/ajeez-orio   (agent dev home)
"""
import os
import sqlite3
import sys

DEFAULT_HOMES = [
    r'C:/Users/THinkPad/AppData/Local/hermes',
    r'C:/Users/THinkPad/AppData/Local/hermes/profiles/ajeez-orio',
]


def check_home(home):
    db = os.path.join(home, 'state', 'orio-ops', 'orio_demo.db')
    if not os.path.exists(db):
        return ['missing db %s' % db]
    errs = []
    try:
        con = sqlite3.connect('file:%s?mode=ro' % db, uri=True)
    except Exception as e:  # noqa: BLE001
        return ['cannot open %s: %s' % (db, e)]
    try:
        cols = [r[1] for r in con.execute('PRAGMA table_info(matrix_rows)')]
        if 'status' not in cols or 'location' not in cols:
            errs.append('matrix_rows lacks adjudicated schema (no status/location cols)')
            return errs  # further checks are meaningless on the old schema
        total = con.execute('SELECT COUNT(*) FROM matrix_rows').fetchone()[0]
        counts = dict(con.execute(
            "SELECT status, COUNT(*) FROM matrix_rows GROUP BY 1"))
        receipt = dict(con.execute('SELECT key, value FROM meta'))
        # Receipt-vs-content: built_from names the matrix total; the status
        # line must sum to the same total. Self-maintaining across rebuilds.
        built = receipt.get('built_from', '')
        if '%d matrix rows' % total not in built:
            errs.append('meta built_from does not match content total=%d: %r'
                        % (total, built[:100]))
        status_line = receipt.get('matrix_status_counts', '')
        parts = dict(p.split('=') for p in status_line.split(', ') if '=' in p)
        try:
            if sum(int(v) for v in parts.values()) != total:
                errs.append('meta matrix_status_counts sums off total=%d: %r'
                            % (total, status_line))
        except Exception:  # noqa: BLE001
            errs.append('unparseable matrix_status_counts: %r' % status_line)
        for k, v in counts.items():
            if parts.get(k) != str(v):
                errs.append('status %s: content=%d receipt=%s'
                            % (k, v, parts.get(k)))
        if receipt.get('data_tier') != 'demo':
            errs.append('data_tier is %r, want demo' % receipt.get('data_tier'))
        if total == 185:
            errs.append('185 rows: known stale pre-adjudication snapshot')
    finally:
        con.close()
    return errs


def main(argv):
    homes = [a for a in argv if not a.startswith('-')] or DEFAULT_HOMES
    failed = False
    for h in homes:
        errs = check_home(h)
        if errs:
            failed = True
            print('DRIFT %s' % h)
            for e in errs:
                print('  - %s' % e)
        else:
            print('OK %s' % h)
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
