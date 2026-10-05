"""Build the ORIO Operations demo SQLite database.

Sources (read-only, never modified):
  - <pkg>/data/mr_index.json   full Sep 19 Rig+Well index (extracted from the
    supplied 691-page PDF; copied here from scratch at build time)
  - <pkg>/data/seed_cases.json curated verified cases, tracker rows, MDD,
    actions, exceptions, history, expansion rows

Target (demo state only, safe to delete and rebuild):
  - <HERMES_HOME>/state/orio-ops/orio_demo.db   (WAL mode)

Usage:  python3 build_db.py [--home PATH] [--db PATH]
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def resolve_home() -> Path:
    for i, a in enumerate(sys.argv):
        if a == '--home' and i + 1 < len(sys.argv):
            return Path(sys.argv[i + 1])
    try:
        from hermes_constants import get_hermes_home
        return Path(get_hermes_home())
    except Exception:
        return Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')


def stage_of(last24: str, next24: str) -> str:
    t = (last24 + ' ' + next24).upper()
    if 'RIG RELEASE' in t:
        return 'Rig released'
    if 'PRE-SPUD' in t or 'RIG UP' in t:
        return 'Mobilization / pre-spud'
    if 'COMPLETION' in t and ('RIH' in t or 'RUN ' in t):
        return 'Completion RIH'
    if 'CEMENT' in t and '9 5/8' in t:
        return '9-5/8 casing cement'
    if 'DRILL' in t and '8-1/2' in t:
        return '8-1/2 drilling'
    if 'LOG' in t:
        return 'Logging / evaluation'
    if 'CEMENT' in t:
        return 'Cementing'
    if 'DRILL' in t:
        return 'Drilling'
    if 'RIH' in t:
        return 'RIH operations'
    return 'General operations'


SCHEMA = '''
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT);
CREATE TABLE IF NOT EXISTS rig_blocks(
  rig TEXT, well TEXT, first_page INTEGER, pages INTEGER,
  last24 TEXT, next24 TEXT, stage TEXT, orio_relevance TEXT);
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY, rig TEXT, well TEXT, cycle TEXT,
  first_page INTEGER, pages INTEGER, foreman TEXT,
  lifecycle TEXT, priority TEXT, finding TEXT, last24 TEXT, next24 TEXT);
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, kind TEXT,
  page INTEGER, status TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS tracker_rows(rig TEXT, well TEXT, qty TEXT, note TEXT);
CREATE TABLE IF NOT EXISTS mdd_docs(
  po TEXT PRIMARY KEY, item TEXT, ref TEXT, descr TEXT, qty_ordered INTEGER,
  qty_outstanding INTEGER, shipment TEXT, vendor TEXT, rig TEXT, well TEXT,
  foreman TEXT, signed INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS actions(
  id TEXT PRIMARY KEY, job_id TEXT, kind TEXT, state TEXT,
  title TEXT, why TEXT, proposal TEXT, effect TEXT);
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT, decision TEXT,
  note TEXT, at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS exceptions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, issue TEXT,
  source_a TEXT, source_b TEXT, risk TEXT, resolution TEXT, state TEXT DEFAULT 'open');
CREATE TABLE IF NOT EXISTS history(
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_ref TEXT, date TEXT,
  source TEXT, stage TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS expansion(
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, rig TEXT, well TEXT,
  size TEXT, company TEXT, remarks TEXT);
CREATE TABLE IF NOT EXISTS drafts(
  id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT, ref TEXT, body TEXT,
  at TEXT DEFAULT (datetime('now')));
'''


def main() -> None:
    db_arg = None
    for i, a in enumerate(sys.argv):
        if a == '--db' and i + 1 < len(sys.argv):
            db_arg = Path(sys.argv[i + 1])
    db_path = db_arg or (resolve_home() / 'state' / 'orio-ops' / 'orio_demo.db')
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()  # demo rebuild is always clean

    mr = json.loads((HERE / 'mr_index.json').read_text())
    seed = json.loads((HERE / 'seed_cases.json').read_text())

    con = sqlite3.connect(str(db_path))
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript(SCHEMA)

    case_keys = {(j['rig'], j['well']) for j in seed['jobs']}
    n_blocks = 0
    for r in mr['records']:
        known = (r['rig'], r['well']) in case_keys
        con.execute(
            'INSERT INTO rig_blocks VALUES (?,?,?,?,?,?,?,?)',
            (r['rig'], r['well'], r['first_page'], r['pages'],
             r['last24'], r['next24'],
             stage_of(r['last24'], r['next24']),
             'verified case' if known else 'unassessed'))
        n_blocks += 1

    for j in seed['jobs']:
        con.execute(
            'INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (j['id'], j['rig'], j['well'], j['cycle'], j['first_page'],
             j['pages'], j['foreman'], j['lifecycle'], j['priority'],
             j['finding'], j['last24'], j['next24']))
        for e in j['evidence']:
            con.execute(
                'INSERT INTO evidence(job_id,kind,page,status,text) VALUES (?,?,?,?,?)',
                (j['id'], e['kind'], e['page'], e['status'], e['text']))

    for t in seed['tracker_rows']:
        con.execute('INSERT INTO tracker_rows VALUES (?,?,?,?)',
                    (t['rig'], t['well'],
                     str(t['qty']) if t['qty'] is not None else None, t['note']))
    for m in seed['mdd_docs']:
        con.execute('INSERT INTO mdd_docs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (m['po'], m['item'], m['ref'], m['desc'], m['qty_ordered'],
                     m['qty_outstanding'], m['shipment'], m['vendor'], m['rig'],
                     m['well'], m['foreman'], 1 if m['signed'] else 0, m['note']))
    for a in seed['actions']:
        con.execute('INSERT INTO actions VALUES (?,?,?,?,?,?,?,?)',
                    (a['id'], a['job'], a['kind'], a['state'], a['title'],
                     a['why'], a['proposal'], a['effect']))
    for e in seed['exceptions']:
        con.execute(
            'INSERT INTO exceptions(job_id,issue,source_a,source_b,risk,resolution)'
            ' VALUES (?,?,?,?,?,?)',
            (e['job'], e['issue'], e['source_a'], e['source_b'],
             e['risk'], e['resolution']))
    for h in seed['history_hp707']:
        con.execute(
            'INSERT INTO history(job_ref,date,source,stage,text) VALUES (?,?,?,?,?)',
            ('HP-707 / THRY-961612', h['date'], h['source'], h['stage'], h['text']))
    for x in seed['expansion_rows']:
        con.execute(
            'INSERT INTO expansion(date,rig,well,size,company,remarks)'
            ' VALUES (?,?,?,?,?,?)',
            (x['date'], x['rig'], x['well'], x['size'], x['company'], x['remarks']))

    con.execute('INSERT INTO meta VALUES (?,?)',
                ('built_from', 'mr %d pages / %d blocks; seed %s'
                 % (mr['pdf_pages'], len(mr['records']), seed['demo_date'])))
    con.commit()

    # verification printout (every figure from code, not memory)
    cur = con.cursor()
    print('db:', db_path)
    print('rig_blocks:', cur.execute('SELECT COUNT(*) FROM rig_blocks').fetchone()[0])
    print('jobs:', cur.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])
    print('evidence:', cur.execute('SELECT COUNT(*) FROM evidence').fetchone()[0])
    print('actions:', cur.execute('SELECT COUNT(*) FROM actions').fetchone()[0])
    print('exceptions:', cur.execute('SELECT COUNT(*) FROM exceptions').fetchone()[0])
    print('history:', cur.execute('SELECT COUNT(*) FROM history').fetchone()[0])
    print('expansion:', cur.execute('SELECT COUNT(*) FROM expansion').fetchone()[0])
    print('hp704_block:', cur.execute(
        "SELECT rig||'/'||well FROM rig_blocks WHERE rig='HP-704'").fetchall())
    con.close()


if __name__ == '__main__':
    main()
