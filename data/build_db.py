"""Build the ORIO Operations SQLite database (multi-day, Phase 1).

Sources (read-only, never modified):
  - <pkg>/data/mr_index.json        legacy Sep 19 Rig+Well index (292 blocks)
  - <pkg>/data/seed_cases.json      curated verified cases, MDD, actions, etc.
  - <pkg>/data/ingested/mr/*.json       per-report MR indexes (ingest_mr.py)
  - <pkg>/data/ingested/tracker/*.json  dated tracker rows (ingest_tracker.py)
  - <pkg>/data/ingested/matrix/*.json   competitor matrix rows (ingest_matrix.py)

Slow PDF extraction happens once in the ingest_* scripts; this build only
reads their JSON, so a rebuild stays fast.

Target (demo state only; inputs validated and build staged before replacement):
  - <HERMES_HOME>/state/<client>/orio_demo.db   (WAL mode;
    <client> is `orio-ops` for client #1, Ajeez's pilot)

Usage:  python3 build_db.py [--home PATH] [--db PATH] [--client SLUG] [--quiet]
  --client defaults to `orio-ops`. Client slugs match ^[a-z0-9][a-z0-9-]{1,32}$
  (canonical rule lives in dashboard/clients.py; repeated here so this
  script stays runnable standalone).
"""
import json
import os
import re
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
INGESTED = HERE / 'ingested'

DEFAULT_CLIENT = 'orio-ops'
_SLUG_RE = re.compile(r'^[a-z0-9][a-z0-9-]{0,31}$')


def check_client_slug(slug: str) -> str:
    if not isinstance(slug, str) or not _SLUG_RE.match(slug):
        raise SystemExit('bad --client %r (want ^[a-z0-9][a-z0-9-]{1,32}$)'
                         % (slug,))
    return slug


def _flag(argv: list[str], name: str) -> Path | None:
    for i, a in enumerate(argv):
        if a == name and i + 1 < len(argv):
            return Path(argv[i + 1])
    return None


def resolve_home(argv: list[str] | None = None) -> Path:
    src = sys.argv[1:] if argv is None else argv
    hit = _flag(src, '--home')
    if hit is not None:
        return hit
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
  source_page TEXT, extraction TEXT, evidence_json TEXT);
CREATE TABLE IF NOT EXISTS mdd_docs(
  po TEXT PRIMARY KEY, item TEXT, ref TEXT, descr TEXT, qty_ordered INTEGER,
  qty_outstanding INTEGER, shipment TEXT, vendor TEXT, rig TEXT, well TEXT,
  foreman TEXT, signed INTEGER, note TEXT);
CREATE TABLE IF NOT EXISTS actions(
  id TEXT PRIMARY KEY, job_id TEXT, kind TEXT, state TEXT,
  title TEXT, why TEXT, proposal TEXT, effect TEXT);
CREATE TABLE IF NOT EXISTS decisions(
  id INTEGER PRIMARY KEY AUTOINCREMENT, action_id TEXT, decision TEXT,
  note TEXT, actor TEXT, actor_role TEXT, actor_source TEXT,
  at TEXT DEFAULT (datetime('now')));
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
CREATE TABLE IF NOT EXISTS delivery_outbox(
  id INTEGER PRIMARY KEY AUTOINCREMENT, channel TEXT, ref TEXT,
  payload_json TEXT, state TEXT DEFAULT 'blocked', reason TEXT,
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


def _matrix_source_page(r: dict) -> str:
    extracted = (r.get('extraction') or r.get('provenance')) == 'extracted'
    if not extracted:
        if r.get('source_page') not in (None, 'workbook') or r.get('source_pages'):
            raise ValueError('workbook cannot carry extracted physical pages')
        return 'workbook'
    sources = r.get('sources')
    if r.get('physical_page_verified') is not True:
        raise ValueError('extracted row has no physical-page verification receipt')
    if not isinstance(sources, list) or not sources:
        raise ValueError('extracted row needs associated file/page/field support')
    for s in sources:
        if (not isinstance(s, dict) or not s.get('source_file')
                or ';' in s['source_file'] or not s['source_file'].lower().endswith('.pdf')
                or type(s.get('source_page')) is not int or s['source_page'] <= 0
                or not all(s.get(k) for k in ('quote', 'size_span', 'supplier_span'))
                or s.get('physical_page_verified') is not True
                or not re.fullmatch(r'[a-f0-9]{64}', str(s.get('source_sha256', '')))):
            raise ValueError('invalid extracted source association')
    from jev_consume import direct_support
    company = r.get('owner', r.get('company'))
    if any(not any(t['size'] == r.get('size') and t['owner'] == company
                   for t in direct_support(s['quote'])) for s in sources):
        raise ValueError('extracted source quote does not support size/supplier tuple')
    pages = r.get('source_pages')
    if (not isinstance(pages, list) or not pages or any(type(x) is not int or x <= 0 for x in pages)
            or set(pages) != {s['source_page'] for s in sources}):
        raise ValueError('invalid extracted page list')
    if r.get('source_page') is not None and (type(r['source_page']) is not int or r['source_page'] not in pages):
        raise ValueError('invalid representative page')
    if r.get('source_file') not in {s['source_file'] for s in sources}:
        raise ValueError('representative file not associated')
    if r.get('source_page') is not None and not any(
            s['source_file'] == r['source_file'] and s['source_page'] == r['source_page']
            for s in sources):
        raise ValueError('representative file/page pair not associated')
    if not r.get('owner', r.get('company')) or not str(r.get('date', '')).startswith('2026-06-'):
        raise ValueError('extracted row needs supplier and June scope')
    return str(r.get('source_page') or next(s['source_page'] for s in sources
                                          if s['source_file'] == r['source_file']))


def validate_matrix(batches):
    for batch in batches:
        for r in batch.get('rows', []):
            provenance = r.get('extraction') or r.get('provenance')
            if provenance is None:
                # Only actual workbook source files receive workbook provenance.
                if not str(r.get('source_file', batch.get('source_file', ''))).lower().endswith('.xlsx'):
                    raise ValueError('missing explicit provenance; not a workbook')
            elif provenance not in ('workbook', 'extracted'):
                raise ValueError('unknown matrix provenance')
            _matrix_source_page(r)


def main(argv: list[str] | None = None) -> None:
    src = sys.argv[1:] if argv is None else argv
    quiet = '--quiet' in src
    db_arg = _flag(src, '--db')
    client_hit = _flag(src, '--client')
    client = check_client_slug(str(client_hit) if client_hit is not None
                               else DEFAULT_CLIENT)
    home = resolve_home(src)
    db_path = db_arg or (home / 'state' / client / 'orio_demo.db')

    legacy = json.loads((HERE / 'mr_index.json').read_text())
    seed = json.loads((HERE / 'seed_cases.json').read_text())
    mr_batches = _load_dir('mr')
    tracker_batches = _load_dir('tracker')
    matrix_dir = _flag(src, '--matrix-dir')
    if matrix_dir is None:
        # June acceptance hold: old generated extracted JSON is NOT published.
        matrix_batches = [json.loads(p.read_text(encoding='utf-8'))
                          for p in sorted((INGESTED / 'matrix').glob('*.json'))
                          if not p.name.endswith('-extracted.json')]
    else:
        matrix_batches = [json.loads(p.read_text(encoding='utf-8'))
                          for p in sorted(matrix_dir.glob('*.json'))]
    validate_matrix(matrix_batches)  # before touching the destination
    if any(Path(str(db_path) + suffix).exists() for suffix in ('-wal', '-shm')):
        raise ValueError('destination has SQLite sidecars; stop readers/writers before rebuild')
    db_path.parent.mkdir(parents=True, exist_ok=True)
    fd, staging = tempfile.mkstemp(prefix='orio-build-', suffix='.db', dir=db_path.parent)
    os.close(fd)
    con = sqlite3.connect(staging)
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
    # No-invent rule: source_page is an integer report page ONLY for rows a
    # verified MR extraction proved came from a report. Everything else —
    # including all workbook-ingested rows — carries the honest marker
    # 'workbook', never NULL and never a guessed page number.
    # Two provenance classes share matrix_rows, kept honest end-to-end:
    #   workbook   — Ajeez's hand-built sheet (June2026.json, 131 rows)
    #   extracted  — MR rows proven by Jev adjudication (*-extracted.json,
    #                from data/jev_consume.py; eligibility + span audit there)
    # Extracted rows use the adapter's spec keys (owner / provenance /
    # source_pages); workbook rows use company / extraction / source_page.
    n_matrix = 0
    for batch in matrix_batches:
        src = batch.get('source_file', '?')
        for r in batch.get('rows', []):
            company = r.get('company')
            if company is None:
                company = r.get('owner')
            extraction = (r.get('extraction') or r.get('provenance')
                          or 'workbook')
            sp = _matrix_source_page(r)
            if extraction == 'extracted' and (
                    company is None or not str(sp).isdigit()):
                # CA-10: never let a malformed extracted row into a fresh
                # build — fail loudly instead of corrupting matrix_rows.
                raise SystemExit(
                    'bad extracted matrix row in %s: %r (need owner + '
                    'integer page)' % (src, r))
            con.execute(
                'INSERT INTO matrix_rows(date,rig,well,size,company,remarks,'
                'source_file,source_page,extraction,evidence_json) VALUES (?,?,?,?,?,?,?,?,?,?)',
                (r.get('date'), r.get('rig'), r.get('well'), r.get('size'),
                 company, r.get('remarks'), r.get('source_file', src),
                 sp, extraction, json.dumps(r, ensure_ascii=False, allow_nan=False)))
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
    con.execute('INSERT INTO meta VALUES (?,?)', ('client', client))
    con.commit()

    cur = con.cursor()
    if not quiet:
        print('client:', client)
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
    con.execute('PRAGMA wal_checkpoint(TRUNCATE)')
    con.close()
    os.replace(staging, db_path)  # old database survives every earlier failure


if __name__ == '__main__':
    main()
