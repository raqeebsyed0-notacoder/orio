"""Build the ORIO Operations SQLite database (multi-day, Phase 1).

Sources (read-only, never modified):
  - <pkg>/data/mr_index.json        legacy Sep 19 Rig+Well index (292 blocks)
  - <pkg>/data/seed_cases.json      curated verified cases, MDD, actions, etc.
  - <pkg>/data/ingested/mr/*.json       per-report MR indexes (ingest_mr.py)
  - <pkg>/data/ingested/tracker/*.json  dated tracker rows (ingest_tracker.py)
  - <pkg>/data/ingested/matrix/*.json   competitor matrix rows (ingest_matrix.py)

Slow PDF extraction happens once in the ingest_* scripts; this build only
reads their JSON, so a rebuild stays fast.

Target (demo state only, safe to delete and rebuild):
  - <HERMES_HOME>/state/orio-ops/orio_demo.db   (WAL mode)

Usage:  python3 build_db.py [--home PATH] [--db PATH] [--quiet]
"""
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
INGESTED = HERE / 'ingested'


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
    t = ((last24 or '') + ' ' + (next24 or '')).upper()
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
CREATE TABLE IF NOT EXISTS reports(
  report_date TEXT PRIMARY KEY, source_file TEXT, pdf_pages INTEGER,
  block_count INTEGER, ingested_at TEXT DEFAULT (datetime('now')));
CREATE TABLE IF NOT EXISTS rig_blocks(
  report_date TEXT, rig TEXT, well TEXT, first_page INTEGER, pages INTEGER,
  last24 TEXT, next24 TEXT, stage TEXT, orio_relevance TEXT, source_file TEXT);
CREATE TABLE IF NOT EXISTS jobs(
  id TEXT PRIMARY KEY, report_date TEXT, rig TEXT, well TEXT, cycle TEXT,
  first_page INTEGER, pages INTEGER, foreman TEXT,
  lifecycle TEXT, priority TEXT, finding TEXT, last24 TEXT, next24 TEXT);
CREATE TABLE IF NOT EXISTS evidence(
  id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT, kind TEXT,
  page INTEGER, status TEXT, text TEXT);
CREATE TABLE IF NOT EXISTS tracker_rows(
  report_date TEXT, rig TEXT, well TEXT, qty TEXT, note TEXT,
  drss TEXT, mdd TEXT, cal_done TEXT, ship_date TEXT, rih_date TEXT,
  rih_time TEXT, l_date TEXT, l_time TEXT, op_hrs TEXT, mdd_signed TEXT,
  rig_activity TEXT, current_well TEXT, source_file TEXT);
CREATE TABLE IF NOT EXISTS matrix_rows(
  id INTEGER PRIMARY KEY AUTOINCREMENT, date TEXT, rig TEXT, well TEXT,
  size TEXT, company TEXT, remarks TEXT, source_file TEXT,
  source_page INTEGER, extraction TEXT);
CREATE TABLE IF NOT EXISTS mdd_docs(
  po TEXT PRIMARY KEY, item TEXT, ref TEXT, descr TEXT, qty_ordered INTEGER,
  qty_outstanding INTEGER, shipment TEXT, vendor TEXT, rig TEXT, well TEXT,
  foreman TEXT, signed INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS actions(
  id TEXT PRIMARY KEY, job_id TEXT, kind TEXT, state TEXT,
  title TEXT, why TEXT, proposal TEXT, effect TEXT);
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT, decision TEXT,
  note TEXT, actor TEXT, actor_role TEXT, at TEXT DEFAULT (datetime('now')));
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


def _load_dir(sub: str) -> list:
    d = INGESTED / sub
    if not d.is_dir():
        return []
    out = []
    for p in sorted(d.glob('*.json')):
        try:
            out.append(json.loads(p.read_text()))
        except Exception as e:  # noqa: BLE001
            print('  WARN unreadable %s: %s' % (p.name, e))
    return out


def main() -> None:
    quiet = '--quiet' in sys.argv
    db_arg = None
    for i, a in enumerate(sys.argv):
        if a == '--db' and i + 1 < len(sys.argv):
            db_arg = Path(sys.argv[i + 1])
    db_path = db_arg or (resolve_home() / 'state' / 'orio-ops' / 'orio_demo.db')
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()  # demo rebuild is always clean

    legacy = json.loads((HERE / 'mr_index.json').read_text())
    seed = json.loads((HERE / 'seed_cases.json').read_text())
    mr_batches = _load_dir('mr')
    tracker_batches = _load_dir('tracker')
    matrix_batches = _load_dir('matrix')

    con = sqlite3.connect(str(db_path))
    con.execute('PRAGMA journal_mode=WAL')
    con.executescript(SCHEMA)

    case_keys = {(j['rig'], j['well']) for j in seed['jobs']}
    seed_date = seed.get('demo_date', '2026-09-19')

    # ---- legacy Sep 19 index (kept so the proven baseline stays intact) ----
    seen_pairs = set()
    for r in legacy['records']:
        known = (r['rig'], r['well']) in case_keys
        con.execute(
            'INSERT INTO rig_blocks VALUES (?,?,?,?,?,?,?,?,?,?)',
            (seed_date, r['rig'], r['well'], r['first_page'], r['pages'],
             r['last24'], r['next24'], stage_of(r['last24'], r['next24']),
             'verified case' if known else 'unassessed', 'mr_index.json'))
        seen_pairs.add((seed_date, r['rig'], r['well']))
    con.execute('INSERT OR REPLACE INTO reports VALUES (?,?,?,?,datetime("now"))',
                (seed_date, 'mr_index.json', legacy.get('pdf_pages'),
                 len(legacy['records'])))

    # ---- ingested reports (any number of days) ----
    n_ingested = 0
    for batch in mr_batches:
        rdate = batch.get('report_date')
        src = batch.get('source_file', '?')
        if not rdate:
            continue
        con.execute(
            'INSERT OR REPLACE INTO reports VALUES (?,?,?,?,datetime("now"))',
            (rdate, src, batch.get('pdf_pages'), len(batch.get('records', []))))
        for r in batch.get('records', []):
            key = (rdate, r['rig'], r['well'])
            if key in seen_pairs:
                continue
            seen_pairs.add(key)
            known = (r['rig'], r['well']) in case_keys
            con.execute(
                'INSERT INTO rig_blocks VALUES (?,?,?,?,?,?,?,?,?,?)',
                (rdate, r['rig'], r['well'], r['first_page'], r['pages'],
                 r.get('last24', ''), r.get('next24', ''),
                 stage_of(r.get('last24', ''), r.get('next24', '')),
                 'verified case' if known else 'unassessed',
                 r.get('source_file', src)))
            n_ingested += 1

    # ---- curated cases (unchanged contract) ----
    for j in seed['jobs']:
        con.execute(
            'INSERT INTO jobs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)',
            (j['id'], seed_date, j['rig'], j['well'], j['cycle'],
             j['first_page'], j['pages'], j['foreman'], j['lifecycle'],
             j['priority'], j['finding'], j['last24'], j['next24']))
        for e in j['evidence']:
            con.execute(
                'INSERT INTO evidence(job_id,kind,page,status,text) VALUES (?,?,?,?,?)',
                (j['id'], e['kind'], e['page'], e['status'], e['text']))

    # ---- legacy tracker rows (4 curated rows, kept) ----
    for t in seed['tracker_rows']:
        con.execute(
            'INSERT INTO tracker_rows(report_date,rig,well,qty,note,source_file)'
            ' VALUES (?,?,?,?,?,?)',
            (seed_date, t['rig'], t['well'],
             str(t['qty']) if t['qty'] is not None else None,
             t['note'], 'seed_cases.json'))

    # ---- ingested tracker rows ----
    n_tracker = 0
    for batch in tracker_batches:
        src = batch.get('source_file', '?')
        for sh in batch.get('sheets', []):
            for r in sh.get('rows', []):
                con.execute(
                    'INSERT INTO tracker_rows VALUES'
                    ' (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)',
                    (r.get('report_date'), r.get('rig'), r.get('well'),
                     r.get('qty'), None, r.get('drss'), r.get('mdd'),
                     r.get('cal_done'), r.get('ship_date'), r.get('rih_date'),
                     r.get('rih_time'), r.get('l_date'), r.get('l_time'),
                     r.get('op_hrs'), r.get('mdd_signed'), r.get('rig_activity'),
                     r.get('current_well'), src))
                n_tracker += 1

    # ---- competitor matrix rows (market-intelligence track) ----
    n_matrix = 0
    for batch in matrix_batches:
        src = batch.get('source_file', '?')
        for r in batch.get('rows', []):
            con.execute(
                'INSERT INTO matrix_rows(date,rig,well,size,company,remarks,'
                'source_file,source_page,extraction) VALUES (?,?,?,?,?,?,?,?,?)',
                (r.get('date'), r.get('rig'), r.get('well'), r.get('size'),
                 r.get('company'), r.get('remarks'), r.get('source_file', src),
                 r.get('source_page'), r.get('extraction', 'workbook')))
            n_matrix += 1

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

    n_days = con.execute('SELECT COUNT(*) FROM reports').fetchone()[0]
    con.execute('INSERT INTO meta VALUES (?,?)',
                ('built_from', 'legacy %d blocks; ingested %d blocks; '
                 '%d tracker rows; %d matrix rows; %d report days'
                 % (len(legacy['records']), n_ingested, n_tracker,
                    n_matrix, n_days)))
    con.execute('INSERT INTO meta VALUES (?,?)', ('seed_date', seed_date))
    con.commit()

    cur = con.cursor()
    if not quiet:
        print('db:', db_path)
        print('reports:', n_days)
        print('rig_blocks:', cur.execute('SELECT COUNT(*) FROM rig_blocks').fetchone()[0])
        print('jobs:', cur.execute('SELECT COUNT(*) FROM jobs').fetchone()[0])
        print('evidence:', cur.execute('SELECT COUNT(*) FROM evidence').fetchone()[0])
        print('tracker_rows:', cur.execute('SELECT COUNT(*) FROM tracker_rows').fetchone()[0])
        print('matrix_rows:', cur.execute('SELECT COUNT(*) FROM matrix_rows').fetchone()[0])
        print('actions:', cur.execute('SELECT COUNT(*) FROM actions').fetchone()[0])
        print('exceptions:', cur.execute('SELECT COUNT(*) FROM exceptions').fetchone()[0])
        print('history:', cur.execute('SELECT COUNT(*) FROM history').fetchone()[0])
        print('--- rig_blocks by day ---')
        for r in cur.execute('SELECT report_date, COUNT(*) FROM rig_blocks'
                             ' GROUP BY report_date ORDER BY report_date'):
            print('   %s  %d' % (r[0], r[1]))
    con.close()


if __name__ == '__main__':
    main()
