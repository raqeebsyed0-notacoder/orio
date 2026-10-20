"""Lane C check: date-range matrix API + XLSX + ORIO selection seam.

Runs against a THROWAWAY database (scratch TMPDIR), never the installed
demo DB — build/validate in isolation:
  <venv python> tests/lane_c_check.py
Exit non-zero on the first failure. No absolute demo counts are asserted;
every check is relational (narrow < full, shares sum to total, exports
agree with /matrix) or contractual (400s, sheet names, PASS rows).
"""
import io
import os
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG / 'dashboard'))
sys.path.insert(0, str(PKG / 'data'))

SCRATCH = Path(os.environ.get('ORIO_REPAIR_OUT')
               or os.environ.get('TMPDIR')
               or tempfile.gettempdir()).resolve()
SCRATCH.mkdir(parents=True, exist_ok=True)
os.environ['HERMES_HOME'] = tempfile.mkdtemp(prefix='lanec-check-', dir=SCRATCH)

import build_db  # noqa: E402
import plugin_api  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from openpyxl import load_workbook  # noqa: E402

build_db.main(['--home', os.environ['HERMES_HOME'], '--quiet'])
app = FastAPI()
app.include_router(plugin_api.router, prefix='/b')
c = TestClient(app)
B = '/b'
fails = []


def check(name, cond, extra=''):
    print(('PASS' if cond else 'FAIL'), name, extra, flush=True)
    if not cond:
        fails.append(name)


# (1) arbitrary start/end, legacy month alias, separated clocks
# Default dataset is the Ajeez-ruled adjudicated batch: COUNTED rows span
# 2026-06-01..2026-07-01 (rows 130/131 carry the ruled July-1 RIH date per
# R4 and are flagged june_boundary). Selections below are explicit.
FULL = 'start=2026-06-01&end=2026-07-01&status=COUNTED'
JUNE = 'start=2026-06-01&end=2026-06-30&status=COUNTED'
full = c.get(B + '/matrix?' + FULL).json()
r1 = c.get(B + '/matrix?start=2026-06-01&end=2026-06-10&status=COUNTED').json()
r2 = c.get(B + '/matrix?start=2026-06-11&end=2026-07-01&status=COUNTED').json()
check('range-narrows-total', 0 < r1['total'] < full['total'],
      '%d<%d' % (r1['total'], full['total']))
check('ranges-partition-full', r1['total'] + r2['total'] == full['total'],
      '%d+%d==%d' % (r1['total'], r2['total'], full['total']))
check('input-change', r1['total'] != r2['total']
      and r1['by_company'] != r2['by_company'],
      'n=%d vs %d' % (r1['total'], r2['total']))
m = c.get(B + '/matrix?month=2026-06&status=COUNTED').json()
mj = c.get(B + '/matrix?' + JUNE).json()
check('month-alias-equals-range', m['total'] == mj['total'] == full['total'] - 2
      and m['selection']['mode'] == 'month',
      'month=%d june=%d full=%d' % (m['total'], mj['total'], full['total']))
row = r1['rows'][0]
check('clocks-split', 'event_date' in row and 'report_date' in row
      and row['event_date'] and row['report_date'] is None,
      'adjudicated row: event=%s report=%s'
      % (row['event_date'], row['report_date']))
check('run-evidence', isinstance(row.get('evidence'), dict)
      and row['evidence']['provenance'] == 'adjudicated'
      and row.get('status') == 'COUNTED'
      and row.get('location') in ('onshore', 'offshore'))
check('shares-sum-to-one',
      abs(sum(x['share'] for x in r1['by_company']) - 1.0) < 5e-3
      and abs(sum(x['share'] for x in r1['by_size']) - 1.0) < 5e-3,
      'rounded-4dp artifact tolerated')
check('location-sums-to-total',
      sum(x['n'] for x in full['by_location']) == full['total']
      and sum(x['n'] for x in mj['by_location']) == mj['total']
      and {x['location'] for x in full['by_location']} <= {'onshore', 'offshore'},
      str(full['by_location']))
check('innovex-fenced', full['innovex_own']['count'] == 13
      and full['totals_by_provenance'].get('adjudicated') == full['total'])
pc = r1['period_compare']
check('period-compare', pc and pc['current']['n'] == r1['total']
      and pc['previous']['n'] == 0 and pc['delta'] == r1['total']
      and pc['pct_change'] is None)
cov = r1['coverage']
check('coverage-last-update', cov['event_min'] <= cov['event_max']
      and cov['distinct_event_days'] > 0 and cov['last_update'],
      str(cov))
check('filters-combine',
      c.get(B + '/matrix?' + FULL + '&size=9.625').json()['total']
      + c.get(B + '/matrix?' + FULL + '&size=13.375').json()['total']
      + c.get(B + '/matrix?' + FULL + '&size=18.625').json()['total']
      == full['total'])
# (2) genuine .xlsx: opens, 5 sheets, totals agree, reconciliation PASS
sel = 'start=2026-06-01&end=2026-07-01&status=COUNTED'
x = c.get(B + '/matrix/export.xlsx?' + sel)
check('xlsx-status', x.status_code == 200
      and 'spreadsheetml.sheet' in x.headers['content-type'])
wb = load_workbook(io.BytesIO(x.content))
check('xlsx-sheets', wb.sheetnames == ['Summary', 'Details', 'Evidence',
                                       'Coverage', 'Reconciliation'],
      str(wb.sheetnames))
details = wb['Details'].max_row - 1
jm = c.get(B + '/matrix?' + sel + '&limit=5000').json()
check('xlsx-details-agree', details == jm['total'] == full['total'],
      'details=%d api=%d' % (details, jm['total']))
rec = list(wb['Reconciliation'].iter_rows(values_only=True))
check('xlsx-reconciliation',
      len(rec) > 1 and all(r[3] == 'PASS' for r in rec[1:]),
      '; '.join('%s=%s' % (r[0], r[3]) for r in rec[1:]))
csv_n = len(c.get(B + '/matrix/export.csv?' + sel).text.strip().split('\n')) - 1
check('csv-agrees', csv_n == full['total'], 'csv=%d' % csv_n)
xs = c.get(B + '/matrix/export.xlsx?start=2026-06-01&end=2026-06-10&company=WFD')
wb2 = load_workbook(io.BytesIO(xs.content))
d2 = wb2['Details'].max_row - 1
j2 = c.get(B + '/matrix/query?start=2026-06-01&end=2026-06-10&company=WFD').json()
check('xlsx-filtered-agrees', d2 == j2['total'] > 0, 'n=%d' % d2)

# (3) ORIO selection seam: GET + POST, same selection as UI
q = c.get(B + '/matrix/query?start=2026-06-01&end=2026-06-10&size=9.625').json()
check('query-get', q['total'] > 0
      and all(q['selection'].get(k) == v for k, v in
              {'mode': 'range', 'start': '2026-06-01',
               'end': '2026-06-10', 'size': '9.625',
               'company': None}.items())
      and q['exports']['xlsx'] == '/matrix/export.xlsx')
qp = c.post(B + '/matrix/query',
            json={'start': '2026-06-01', 'end': '2026-06-10',
                  'size': '9.625'}).json()
check('query-post-matches-get', qp['total'] == q['total']
      and qp['shares'] == q['shares'])
check('query-total-matches-matrix',
      q['total'] == c.get(B + '/matrix?start=2026-06-01&end=2026-06-10&size=9.625').json()['total'])

# no-network rule still holds (demo safety)
src = (PKG / 'dashboard' / 'plugin_api.py').read_text()
check('no-network-imports',
      all(('import ' + m) not in src and ('from ' + m) not in src
          for m in ['socket', 'urllib', 'httpx', 'requests', 'smtplib',
                    'email.mime']))

print('LANE-C %s (%d failures)' % ('PASS' if not fails else 'FAIL', len(fails)))
sys.exit(1 if fails else 0)
