"""Standalone backend check (no pytest in the hermes venv). Exit non-zero on failure."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG / 'dashboard'))
sys.path.insert(0, str(PKG / 'data'))
import tempfile as _tf
SCRATCH = Path(os.environ.get('ORIO_REPAIR_OUT') or os.environ.get('TMPDIR') or _tf.gettempdir()).resolve()
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ['HERMES_HOME'] = tempfile.mkdtemp(prefix='orio-test-home-', dir=SCRATCH)
MATRIX_DIR = os.environ.get('ORIO_TEST_MATRIX_DIR')
BUILD_ARGS = ['--home', os.environ['HERMES_HOME']] + (['--matrix-dir', MATRIX_DIR] if MATRIX_DIR else [])

import build_db
import plugin_api
from fastapi import FastAPI
from fastapi.testclient import TestClient

build_db.main(BUILD_ARGS)
app = FastAPI()
app.include_router(plugin_api.router, prefix='/api/plugins/euphoria-orio-operations')
c = TestClient(app)
B = '/api/plugins/euphoria-orio-operations'
fails = []


def check(name, cond, extra=''):
    print(('PASS' if cond else 'FAIL'), name, extra)
    if not cond:
        fails.append(name)


check('health', c.get(B + '/health').json()['ok'] is True)
check('rigs=292', c.get(B + '/rigs?limit=1&report_date=2026-09-19').json()['total'] == 292)
check('rigs-oct12=280', c.get(B + '/rigs?limit=1&report_date=2026-10-12').json()['total'] == 280)
reps = c.get(B + '/reports').json()['reports']
rep_dates = [r['report_date'] for r in reps]
check('all-report-days', len(reps) == 92 and '2026-06-01' in rep_dates
      and '2026-09-01' in rep_dates and '2026-10-12' in rep_dates
      and all(r['block_count_actual'] == r['block_count'] for r in reps),
      'n=%d' % len(reps))
new_day = c.get(B + '/rigs?limit=1&report_date=2026-06-01').json()
check('rigs-new-day', new_day['total'] == 287, str(new_day['total']))
met = c.get(B + '/meta').json()
check('meta-latest-day', met['demo_date'] == '2026-10-12'
      and len(met['report_dates']) == 92 and met['report_dates'][0] == '2026-10-12')
wells = {x['well'] for x in c.get(B + '/rigs?q=HP-707&report_date=2026-09-19').json()['rows']}
check('hp707-new-cycle', 'THRY-961602' in wells, str(sorted(wells)))
hist = c.get(B + '/history').json()
check('history-job', 'THRY-961612' in hist['job'] and len(hist['events']) == 12)
sp32 = c.get(B + '/jobs/sp32').json()
txt = ' '.join(e['text'] for e in sp32['evidence'])
check('sp32-conflict', sp32['lifecycle'] == 'CONFLICT' and 'SLB KSV' in txt and 'Qty 2' in txt)
sp262 = c.get(B + '/jobs/sp262').json()
check('sp262-blocked', sp262['lifecycle'] == 'INSUFFICIENT EVIDENCE'
      and not any(a['kind'] == 'Prepare MDD' for a in sp262['actions']))
r = c.post(B + '/actions/a-hp701-db/decision', json={'decision': 'approve', 'note': 't'})
check('approve-demo', r.json()['ok'] and r.json()['demo_only']
      and c.get(B + '/jobs/hp701').json()['lifecycle'] == 'RIH CONFIRMED')
db = Path(os.environ['HERMES_HOME']) / 'state' / 'orio-ops' / 'orio_demo.db'
con = sqlite3.connect(str(db))
con.execute("UPDATE actions SET state='blocked' WHERE id='a-hp701-mdd'")
con.commit(); con.close()
check('blocked-409', c.post(B + '/actions/a-hp701-mdd/decision',
                            json={'decision': 'approve'}).status_code == 409)
check('reject', c.post(B + '/actions/a-sp93-dispatch/decision',
                       json={'decision': 'reject'}).json()['state'] == 'rejected')
check('incorrect', c.post(B + '/actions/a-ad74-dispatch/decision',
                          json={'decision': 'incorrect'}).json()['state'] == 'incorrect')
mdd = c.get(B + '/mdd/preview?job=hp701').json()
check('mdd-missing', 'MISSING - REQUIRES AJEEZ / SOURCE DATA' in ' '.join(v for _, v in mdd['lines'])
      and mdd['send_enabled'] is False)
em = c.post(B + '/drafts/email', json={'job': 'hp701'}).json()
check('email-never-sends', em['sent'] is False and 'MISSING' in em['body'])

# ---- Phase 2 channel seams (blocked-channel discipline) ----
ch = c.get(B + '/channels/status').json()
check('channels-all-blocked',
      len(ch['channels']) == 3
      and all(x['state'] == 'blocked' and x['reason'] for x in ch['channels']),
      str([(x['channel'], x['state']) for x in ch['channels']]))
check('channels-config',
      sorted(x['channel'] for x in ch['channels'])
      == ['email', 'onedrive', 'telegram'])
check('email-payload-stored',
      em['outbox_state'] == 'blocked'
      and em['channel']['state'] == 'blocked'
      and set(em['delivery_payload']) >= {'recipient', 'subject', 'body',
                                          'attachments'},
      str(sorted(em.get('delivery_payload', {}))))
ob = c.get(B + '/delivery/outbox').json()
check('outbox-stored-locally',
      ob['send_enabled'] is False and len(ob['outbox']) == 1
      and ob['outbox'][0]['state'] == 'blocked'
      and ob['outbox'][0]['channel'] == 'email'
      and ob['outbox'][0]['payload']['ref'] == 'draft:%d' % em['draft_id'],
      str(ob['outbox'])[:200])
mdd2 = c.get(B + '/mdd/preview?job=hp701').json()
check('mdd-delivery-payload',
      mdd2['send_enabled'] is False
      and mdd2['channel']['state'] == 'blocked'
      and set(mdd2['delivery_payload']) >= {'recipient', 'subject', 'body',
                                            'attachments'})
import channels as chmod
art = chmod.get_channel('email').prepare(
    {'recipient': 'r', 'subject': 's', 'body': 'b', 'attachments': [],
     'ref': 't'})
rcpt = chmod.get_channel('email').deliver(art)
check('blocked-deliver-refuses',
      rcpt['delivered'] is False and rcpt['state'] == 'blocked'
      and bool(rcpt['reason']), str(rcpt))

# ---- Phase 3 hardening: attributed approvals + gateway bind + ops log ----
ap = c.post(B + '/actions/a-sp93-dispatch/decision',
            json={'decision': 'approve', 'actor': 'Probe', 'actor_role': 'supervisor'}).json()
check('approve-writes-actor',
      ap['actor'] == 'Probe' and ap['actor_role'] == 'supervisor'
      and ap['actor_source'] == 'client', str(ap))
acts = c.get(B + '/actions').json()['actions']
last = next(a['last_decision'] for a in acts if a['id'] == 'a-sp93-dispatch')
check('actor-persisted',
      last['actor'] == 'Probe' and last['actor_role'] == 'supervisor'
      and last['actor_source'] == 'client', str(last))
gw = c.post(B + '/actions/a-ad74-dispatch/decision',
            json={'decision': 'reject'},
            headers={'x-hermes-user': 'Ajeez',
                     'x-hermes-user-role': 'supervisor'}).json()
check('gateway-bind-wins',
      gw['actor'] == 'Ajeez' and gw['actor_role'] == 'supervisor'
      and gw['actor_source'] == 'gateway', str(gw))
forge = c.post(B + '/actions/a-ad74-dispatch/decision',
               json={'decision': 'reject', 'actor': 'SomeoneElse'},
               headers={'x-hermes-user': 'Ajeez'})
check('forgery-rejected', forge.status_code == 400, str(forge.status_code))
dflt = c.post(B + '/actions/a-ad74-dispatch/decision',
              json={'decision': 'incorrect'}).json()
check('default-actor',
      dflt['actor'] == 'Ajeez' and dflt['actor_role'] == 'operator'
      and dflt['actor_source'] == 'default', str(dflt))
rs = c.post(B + '/exceptions/1/resolve',
            json={'note': 'phase3 probe', 'actor': 'Probe'}).json()
check('resolve-writes-actor',
      rs['actor'] == 'Probe' and rs['actor_source'] == 'client', str(rs))
db3 = sqlite3.connect(str(db))
db3.row_factory = sqlite3.Row
res = db3.execute(
    'SELECT actor, actor_role, actor_source FROM decisions'
    " WHERE action_id='exception:1' ORDER BY id DESC LIMIT 1").fetchone()
check('resolve-actor-persisted',
      res['actor'] == 'Probe' and res['actor_source'] == 'client', str(dict(res)))
db3.close()
log = c.get(B + '/ops/log').json()
ops = {(e['op'], e['status']) for e in log['entries']}
check('ops-log-visible',
      ('decision', 'approved') in ops
      and ('decision', 'rejected-forgery') in ops
      and ('exception-resolve', 'resolved') in ops
      and ('draft-email', 'blocked-stored') in ops,
      str(sorted(ops)))
csv = c.get(B + '/export.csv')
check('csv', csv.status_code == 200 and csv.text.count('\n') > 292)

# ---- market intelligence track (Ajeez-ruled June, adjudicated v2) ----
# Expected values are DERIVED from the frozen adjudicated batch, never
# hard-coded: data/ingested/matrix/June2026-adjudicated-v2.json
# (provenance=adjudicated, 135 rows with ruling status + location; the 13
# innovex_own jobs fenced out of matrix_rows). The stale v1 workbook
# (June2026.json) is retired; *-extracted.json never loads by default.
import json
import csv as _csv
import io as _io
from collections import Counter as _Counter
from pathlib import Path as _Path
_mdir = _Path(MATRIX_DIR) if MATRIX_DIR else PKG / 'data/ingested/matrix'
_v2 = _mdir / 'June2026-adjudicated-v2.json'
if not _v2.exists():
    _v2 = PKG / 'data/ingested/matrix/June2026-adjudicated-v2.json'
adj = json.loads(_v2.read_text())
adj_rows = adj['rows']
counted = [r for r in adj_rows if r['status'] == 'COUNTED']
exp_total = len(counted)
exp_all = len(adj_rows)
exp_comp = dict(_Counter(r['company'] for r in counted if r['company'] != 'UNPROVEN'))
exp_size = dict(_Counter(r['size'] for r in counted))
exp_loc = dict(_Counter(r['location'] for r in counted if r['location']))
exp_unproven = sum(1 for r in counted if r['company'] == 'UNPROVEN')
exp_status = dict(_Counter(r['status'] for r in adj_rows))
exp_boundary = sum(1 for r in counted if r.get('june_boundary'))
exp_june = sum(1 for r in counted if (r['date'] or '')[:7] == '2026-06')
mx = c.get(B + '/matrix?provenance=adjudicated&status=COUNTED').json()
check('matrix-total', mx['total'] == exp_total,
      'total=%s exp=%s' % (mx['total'], exp_total))
check('matrix-sizes', {s['size']: s['n'] for s in mx['by_size']} == exp_size,
      str({s['size']: s['n'] for s in mx['by_size']}))
check('matrix-companies',
      {s['company']: s['n'] for s in mx['by_company']} == exp_comp,
      str({s['company']: s['n'] for s in mx['by_company']}))
check('matrix-locations',
      {s['location']: s['n'] for s in mx['by_location']} == exp_loc,
      str({s['location']: s['n'] for s in mx['by_location']}))
check('matrix-unproven', mx['unproven_company_rows'] == exp_unproven,
      'unproven=%s exp=%s' % (mx['unproven_company_rows'], exp_unproven))
check('matrix-innovex-fenced', mx['innovex_own']['count'] == adj['innovex_own_count']
      and not any(r['company'] == 'INNOVEX' for r in mx['rows']),
      str(mx['innovex_own']))
check('matrix-prov-totals',
      mx['totals_by_provenance'].get('adjudicated') == exp_total
      and mx['totals_by_provenance'].get('extracted') == 0,
      str(mx['totals_by_provenance']))
mxall = c.get(B + '/matrix').json()
check('matrix-all-statuses',
      {s['status']: s['n'] for s in mxall['by_status']} == exp_status,
      str({s['status']: s['n'] for s in mxall['by_status']}))
check('matrix-all-total', mxall['total'] == exp_all,
      'total=%s exp=%s' % (mxall['total'], exp_all))
mxf = c.get(B + '/matrix?provenance=adjudicated&status=COUNTED&size=13.375&company=HAL').json()
check('matrix-filter', mxf['total'] > 0 and all(
    r['size'] == '13.375' and r['company'] == 'HAL' for r in mxf['rows']))
june1 = sum(1 for r in counted if r['date'] == '2026-06-01')
mxj = c.get(B + '/matrix?month=2026-06&provenance=adjudicated&status=COUNTED').json()
check('matrix-june-june1',
      sum(1 for r in mxj['rows'] if r['date'] == '2026-06-01') == june1
      and mxj['total'] == exp_june,
      'june1=%d june=%d' % (june1, mxj['total']))
mxc = c.get(B + '/matrix/export.csv?provenance=adjudicated&status=COUNTED')
mbody = list(_csv.reader(_io.StringIO(mxc.text)))
check('matrix-csv', mxc.status_code == 200 and len(mbody) == exp_total + 1,
      'lines=%d exp=%d' % (len(mbody), exp_total + 1))
check('matrix-csv-header',
      mbody[0][-4:] == ['Source Page', 'Location', 'Status', 'Provenance'], str(mbody[0]))
check('matrix-csv-provenance-col', all(row[-1] == 'adjudicated' for row in mbody[1:]))
bad_cells = [cell for row in mbody[1:] for cell in row
             if cell and cell[:1] in '=+@-\t\r']
check('matrix-csv-formula-safe', not bad_cells, str(bad_cells[:5]))
# B4 alias wiring: report spellings resolve to canonical companies;
# Resp.Co codes are rejected, never silently matched.
hal_n = c.get(B + '/matrix?provenance=adjudicated&status=COUNTED&company=HAL').json()['total']
check('matrix-alias-howco',
      c.get(B + '/matrix?provenance=adjudicated&status=COUNTED&company=HOWCO').json()['total'] == hal_n
      and c.get(B + '/matrix?company=HLB').json()['selection']['company'] == 'HAL',
      'hal=%d' % hal_n)
fet_n = c.get(B + '/matrix?provenance=adjudicated&status=COUNTED&company=FET').json()['total']
check('matrix-alias-davis',
      c.get(B + '/matrix?provenance=adjudicated&status=COUNTED&company=DAVIS-LYNCH').json()['total'] == fet_n,
      'fet=%d' % fet_n)
check('matrix-never-company',
      c.get(B + '/matrix?company=WDV').status_code == 400
      and c.get(B + '/matrix?company=HDV').status_code == 400
      and c.get(B + '/matrix?company=TOD').status_code == 400)
check('matrix-location-filter',
      c.get(B + '/matrix?provenance=adjudicated&status=COUNTED&location=offshore').json()['total']
      == exp_loc.get('offshore', 0))
check('matrix-status-filters',
      c.get(B + '/matrix?provenance=adjudicated&status=PENDING_FILE').json()['total']
      == exp_status.get('PENDING_FILE', 0)
      and c.get(B + '/matrix?provenance=adjudicated&status=PENDING_RULING').json()['total']
      == exp_status.get('PENDING_RULING', 0)
      and c.get(B + '/matrix?provenance=adjudicated&status=EXCLUDED').json()['total']
      == exp_status.get('EXCLUDED', 0))
check('matrix-june-boundary',
      sum(1 for r in c.get(B + '/matrix?provenance=adjudicated&status=COUNTED&limit=5000').json()['rows']
          if r.get('june_boundary')) == exp_boundary,
      'boundary=%d' % exp_boundary)
# ---- Gate2-fix: single-bound ranges are open-ended, never a 400 ----
sb1 = c.get(B + '/matrix?start=2026-06-15')
check('matrix-single-start-open',
      sb1.status_code == 200 and sb1.json()['selection']['mode'] == 'range-open'
      and sb1.json()['selection']['start'] == '2026-06-15'
      and sb1.json()['selection']['end'] is None
      and sb1.json()['period_compare'] is None, str(sb1.status_code))
sb2 = c.get(B + '/matrix?end=2026-06-15')
check('matrix-single-end-open',
      sb2.status_code == 200 and sb2.json()['selection']['mode'] == 'range-open'
      and sb2.json()['selection']['end'] == '2026-06-15'
      and sb2.json()['selection']['start'] is None, str(sb2.status_code))
sb3 = c.get(B + '/matrix?start=2026-06-15&end=2026-07-01')
sb4 = c.get(B + '/matrix?start=2026-06-01&end=2026-06-15')
check('matrix-open-superset-closed',
      sb3.status_code == 200 and sb4.status_code == 200
      and sb1.json()['total'] >= sb3.json()['total']
      and sb2.json()['total'] >= sb4.json()['total'],
      'open-start=%d closed-after=%d open-end=%d closed-before=%d'
      % (sb1.json()['total'], sb3.json()['total'],
         sb2.json()['total'], sb4.json()['total']))
sbev = c.get(B + '/matrix?date_basis=event&start=2026-06-15')
check('matrix-single-start-event-open',
      sbev.status_code == 200
      and sbev.json()['selection']['mode'] == 'range-open', str(sbev.status_code))
check('matrix-reversed-still-400',
      c.get(B + '/matrix?start=2026-07-01&end=2026-06-01').status_code == 400)
check('matrix-bad-date-still-400',
      c.get(B + '/matrix?start=2026-13-40').status_code == 400)
sbx = c.get(B + '/matrix/export.csv?start=2026-06-15&envelope=json')
check('matrix-export-open-name',
      sbx.status_code == 200
      and sbx.json()['filename'] == 'orio_market_intel_2026-06-15_to_open.csv',
      str(sbx.json().get('filename') if sbx.status_code == 200 else sbx.status_code))
# M4: lane-7 currency — suppliers + corrections serve the v2 ruled data
# with no stale flag; upcoming + tool-problems still read the pre-v2
# day-event registers (v2 rows carry no report context text) and stay
# visibly marked until a context-carrying v2 register exists.
sup7 = c.get(B + '/intelligence/suppliers/first-seen').json()
check('lane7-suppliers-fresh', 'stale' not in sup7
      and {s['supplier_code']: s['repeat_use']['observations']
           for s in sup7['suppliers']}
      == {s['company']: s['n'] for s in mx['by_company']},
      str([(s['supplier_code'], s['repeat_use']['observations'])
           for s in sup7['suppliers']]))
check('lane7-suppliers-ruled',
      {s['supplier_code']: s['repeat_use']['observations']
       for s in sup7['suppliers']}
      == {'WFD': 47, 'HAL': 39, 'FET': 26, 'TAM': 10}
      and sum(s['repeat_use']['observations'] for s in sup7['suppliers'])
      + sup7['unproven_company_rows'] == exp_total == 123,
      'ruled WFD47/HAL39/FET26/TAM10 (+1 UNPROVEN = 123 COUNTED)')
check('lane7-suppliers-display',
      {s['supplier_code']: s['supplier_display'] for s in sup7['suppliers']}
      == {'WFD': 'WEATHERFORD (WFD)', 'HAL': 'HALLIBURTON (HAL)',
          'FET': 'FORUM ENERGY TECHNOLOGIES (FET)', 'TAM': 'TAM (TAM)'}
      and sup7['unproven_company_rows'] == exp_unproven)
cor7 = c.get(B + '/intelligence/corrections').json()
check('lane7-corrections-fresh', 'stale' not in cor7
      and cor7['ruling']['authority'] == 'Ajeez'
      and cor7['ruling']['date'] == '2026-10-20')
check('lane7-corrections-ruled',
      len(cor7['applied_corrections']) == 2
      and {a['row'] for a in cor7['applied_corrections']} == {65, 79}
      and all(a['status'] == 'APPLIED' and a['history_preserved']
              for a in cor7['applied_corrections'])
      and len(cor7['kept_at_tam']) == 3
      and len(cor7['provisional_rows']) == 3
      and len(cor7['codified_rules']) == 2)
check('lane7-context-views-stale',
      all(c.get(B + u).json().get('stale') is True
          for u in ('/intelligence/upcoming', '/intelligence/tool-problems')))
# m3: /matrix serves FULL NAME (CODE) display alongside the canonical
# code; filtering by code / report alias still resolves to the code.
mxd = c.get(B + '/matrix?provenance=adjudicated&status=COUNTED&limit=5000').json()
check('matrix-display-on-rows',
      all(r.get('company_display') for r in mxd['rows'])
      and all(r['company'] in ('WFD', 'HAL', 'FET', 'TAM', 'UNPROVEN')
              for r in mxd['rows']))
hal_rows = [r for r in mxd['rows'] if r['company'] == 'HAL']
tam_rows = [r for r in mxd['rows'] if r['company'] == 'TAM']
check('matrix-display-hal-tam',
      hal_rows and all(r['company_display'] == 'HALLIBURTON (HAL)'
                       for r in hal_rows)
      and tam_rows and all(r['company_display'] == 'TAM (TAM)'
                           for r in tam_rows))
check('matrix-display-groupings',
      {g['company']: g['company_display'] for g in mxd['by_company']}
      == {g['company']: g['company_display']
          for g in mx['by_company']}
      and all(g.get('company_display') for g in mxd['by_company'])
      and all(g.get('company_display') for g in mxd['by_size_company']))
check('matrix-display-filter-keeps-code',
      all(r['company'] == 'HAL'
          and r['company_display'] == 'HALLIBURTON (HAL)'
          for r in mxf['rows']) and mxf['rows'])
# ---- T3 source_page lineage (no-invent rule) ----
# Ajeez-ruled rows carry the ruled report citation verbatim (provenance
# 'adjudicated', authority in evidence_json). No NULLs. Extracted rows
# stay quarantined: a default build loads zero of them (M7).
db2 = sqlite3.connect(str(db))
db2.row_factory = sqlite3.Row
null_pages = db2.execute(
    'SELECT COUNT(*) c FROM matrix_rows WHERE source_page IS NULL').fetchone()['c']
check('matrix-no-null-page', null_pages == 0, 'nulls=%d' % null_pages)
check('matrix-extractions-honest', {r[0] for r in db2.execute(
    'SELECT DISTINCT extraction FROM matrix_rows')} == {'adjudicated'})
check('matrix-quarantine-default', db2.execute(
    "SELECT COUNT(*) c FROM matrix_rows WHERE extraction = 'extracted'").fetchone()['c'] == 0)
db_status = {r[0]: r[1] for r in db2.execute(
    "SELECT COALESCE(status, 'NULL'), COUNT(*) FROM matrix_rows GROUP BY 1")}
check('matrix-db-status', db_status == exp_status, str(db_status))
db_comp = sorted((r['date'], r['rig'].upper(), r['well'].upper(), r['size'],
                r['company'].upper(), r['location'], r['status'])
               for r in db2.execute(
    "SELECT date,rig,well,size,company,location,status FROM matrix_rows"))
src_comp = sorted((r['date'], r['rig'].upper(), r['well'].upper(), r['size'],
                 r['company'].upper(), r['location'], r['status'])
                for r in adj_rows)
check('matrix-db-matches-batch', db_comp == src_comp,
      '%d vs %d rows' % (len(db_comp), len(src_comp)))
check('matrix-db-companies', {r[4] for r in db_comp} <= {'WFD', 'HAL', 'FET', 'TAM', 'UNPROVEN'},
      str({r[4] for r in db_comp}))
check('matrix-db-no-respco', not ({r[4] for r in db_comp} & {'WDV', 'HDV', 'TOD'}))
check('matrix-innovex-table', db2.execute(
    'SELECT COUNT(*) c FROM innovex_own').fetchone()['c'] == adj['innovex_own_count'])
db2.close()
exp_with_page = sum(1 for r in counted if str(r['source_page']).isdigit())
check('matrix-lineage-honest',
      mx['lineage'] == {'with_source_page': exp_with_page,
                        'total': exp_total},
      str(mx['lineage']))
# Regressions are independent of the held generated JSON (test_jev_repair.py).
allmx = c.get(B + '/matrix?limit=5000').json()
check('tr3-matrix-api-adjudicated', len([r for r in allmx['rows']
      if r.get('extraction') == 'adjudicated']) == exp_all)
check('tr3-matrix-api-no-extracted', not [r for r in allmx['rows']
      if r.get('extraction') == 'extracted'])
check('tr3-csv-guard', plugin_api._csv_cell('=1+1').startswith(chr(39))
      and plugin_api._csv_cell('9.625') == '9.625')

# ---- Phase 4 multi-client (one codebase, one workspace per client) ----
import clients as clmod
check('client-default', clmod.DEFAULT_CLIENT == 'orio-ops')
try:
    clmod.check_slug('../evil')
    bad_slug_ok = False
except ValueError:
    bad_slug_ok = True
check('client-slug-rejects', bad_slug_ok)
r404 = c.get(B + '/health?client=no-such-client-zzz')
check('client-unknown-404', r404.status_code == 404, str(r404.status_code))
rbad = c.get(B + '/health?client=../evil')
check('client-badslug-400', rbad.status_code == 400, str(rbad.status_code))
h0 = c.get(B + '/health').json()
check('client-default-health',
      h0['client'] == 'orio-ops' and h0['ok'] is True
      and h0['db'].replace('\\', '/').endswith('state/orio-ops/orio_demo.db'),
      str(h0))
# second client DB in the same throwaway home: same code, separate file
import build_db as _bd
_bd.main(BUILD_ARGS + ['--client', 'demo-client-2', '--quiet'])
db2 = Path(os.environ['HERMES_HOME']) / 'state' / 'demo-client-2' / 'orio_demo.db'
check('client2-db-built', db2.exists(), str(db2))
clmod.save_config(Path(os.environ['HERMES_HOME']),
                  clmod.default_config('demo-client-2', 'Suite Probe 2'))
h2 = c.get(B + '/health?client=demo-client-2').json()
check('client2-health',
      h2['ok'] is True and h2['client'] == 'demo-client-2'
      and 'demo-client-2' in h2['db'].replace('\\', '/'), str(h2))
m2 = c.get(B + '/meta?client=demo-client-2').json()
check('client2-meta',
      m2['client'] == 'demo-client-2' and m2['demo_date'] == '2026-10-12'
      and len(m2['report_dates']) == 92, str(m2['demo_date']))
hh = c.get(B + '/health?client=orio-ops',
           headers={'x-orio-client': 'demo-client-2'}).json()
check('client-header-wins', hh['client'] == 'demo-client-2', str(hh))
# write isolation: a client-2 approval must not touch client #1
ap2 = c.post(B + '/actions/a-sp93-dispatch/decision?client=demo-client-2',
             json={'decision': 'approve', 'actor': 'Client2Probe'}).json()
last0 = next(a['last_decision']
             for a in c.get(B + '/actions').json()['actions']
             if a['id'] == 'a-sp93-dispatch')
last2 = next(a['last_decision']
             for a in c.get(B + '/actions?client=demo-client-2').json()['actions']
             if a['id'] == 'a-sp93-dispatch')
check('client-write-isolated',
      ap2['actor'] == 'Client2Probe'
      and last2['actor'] == 'Client2Probe'
      and last0['actor'] == 'Probe',
      'c1=%s c2=%s' % (last0['actor'], last2['actor']))
cls = c.get(B + '/clients').json()
slugs = {x['client'] for x in cls['clients']}
check('clients-list',
      cls['default'] == 'orio-ops'
      and {'orio-ops', 'demo-client-2'} <= slugs, str(sorted(slugs)))
cp = c.get(B + '/clients/demo-client-2').json()
check('clients-profile',
      cp['profile']['client'] == 'demo-client-2'
      and cp['profile']['channels']['email']['state'] == 'blocked'
      and cp['db_exists'] is True, str(cp['profile']['client']))
check('clients-unknown-404',
      c.get(B + '/clients/no-such-client-zzz').status_code == 404)
clsrc = (PKG / 'dashboard' / 'clients.py').read_text()
check('clients-no-net', all(('import ' + m) not in clsrc and ('from ' + m) not in clsrc
                            for m in ['socket', 'urllib', 'httpx', 'requests', 'smtplib', 'email.mime']))
check('clients-no-creds', 'api_key' not in clsrc.lower()
      and 'passwd' not in clsrc.lower()
      and 'BEGIN ' not in clsrc)
obsrc = (PKG / 'tools' / 'onboard_client.sh').read_text()
check('onboard-no-net', all(t not in obsrc for t in ['curl', 'wget', 'ssh '])
      and 'api_key' not in obsrc.lower(), 'static scan')

src = (PKG / 'dashboard' / 'plugin_api.py').read_text()
check('no-net', all(('import ' + m) not in src and ('from ' + m) not in src
                    for m in ['socket', 'urllib', 'httpx', 'requests', 'smtplib', 'email.mime']))
chsrc = (PKG / 'dashboard' / 'channels.py').read_text()
check('channels-no-net', all(('import ' + m) not in chsrc and ('from ' + m) not in chsrc
                             for m in ['socket', 'urllib', 'httpx', 'requests', 'smtplib', 'email.mime']))
check('channels-no-creds', 'api_key' not in chsrc.lower()
      and 'passwd' not in chsrc.lower()
      and 'BEGIN ' not in chsrc)
print('FAILURES:', fails if fails else 'none')
sys.exit(1 if fails else 0)
