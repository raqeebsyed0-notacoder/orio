"""Sec1 isolation tests: benchmark/extracted separation, unknown event
dates, equivalent filters across outputs, changed-input behavior.

Runs against a THROWAWAY database (TMPDIR), never the installed demo DB:
  <venv python> -m pytest tests/test_matrix_separation.py -q

June HOLD is preserved: no test asserts acceptance, only that the two
sources stay separate, unknown dates stay visibly unknown, and every
output filters on the same declared basis.
"""
import io
import json
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG / 'dashboard'))

os.environ['HERMES_HOME'] = tempfile.mkdtemp(prefix='orio-sec1-test-home-')

import plugin_api  # noqa: E402


def _ev(report_date, date_rih):
    return json.dumps({'report_date': report_date, 'date_rih': date_rih,
                       'sources': []})


@pytest.fixture(scope='module')
def client():
    # Pin a private home at fixture time (see test_api.py): whole-dir
    # runs import every suite module before any fixture, so sharing the
    # import-time home would collide with test_api's built database.
    os.environ['HERMES_HOME'] = tempfile.mkdtemp(prefix='orio-sec1-test-home-')
    from clients import db_path, DEFAULT_CLIENT
    from hermes_constants import get_hermes_home
    p = db_path(get_hermes_home(), DEFAULT_CLIENT)
    p.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(p))
    con.execute('CREATE TABLE matrix_rows(id INTEGER PRIMARY KEY, date TEXT,'
                ' rig TEXT, well TEXT, size TEXT, company TEXT, remarks TEXT,'
                ' source_file TEXT, source_page TEXT, extraction TEXT,'
                ' evidence_json TEXT, location TEXT, status TEXT)')
    rows = [
        # benchmark reference (workbook RIH dates, no evidence packet)
        ('2026-06-05', 'AD-83', 'UDYN-80', '9.625', 'HAL', 'wb row 1',
         'june.xlsx', 'workbook', 'workbook', None),
        ('2026-06-20', 'SP-31', 'THRY-561614', '9.625', 'FET', 'wb row 2',
         'june.xlsx', 'workbook', 'workbook', None),
        # extracted candidates: report clock in `date`, event clock in packet
        ('2026-06-05', 'ADC-42L', 'UTMN-3210', '9.625', 'WFD', 'ex unknown',
         'LMR06052026.pdf', '84', 'extracted', _ev('2026-06-05', None)),
        ('2026-06-06', 'ARO-3002', 'SFNY-1009', '13.375', 'WFD', 'ex known',
         'LMR06062026.pdf', '12', 'extracted',
         _ev('2026-06-06', '2026-06-06')),
        ('2026-06-20', 'SP-99', 'HZEM-613402', '9.625', 'HAL', 'ex unknown 2',
         'LMR06202026.pdf', '7', 'extracted', _ev('2026-06-20', None)),
    ]
    con.executemany(
        'INSERT INTO matrix_rows(date,rig,well,size,company,remarks,'
        'source_file,source_page,extraction,evidence_json)'
        ' VALUES (?,?,?,?,?,?,?,?,?,?)', rows)
    con.commit()
    con.close()
    app = FastAPI()
    app.include_router(plugin_api.router,
                       prefix='/api/plugins/euphoria-orio-operations')
    return TestClient(app)


B = '/api/plugins/euphoria-orio-operations'


def test_provenance_filter_separates_sources(client):
    all_r = client.get(B + '/matrix').json()
    assert all_r['total'] == 5
    assert all_r['totals_by_provenance'] == {'workbook': 2, 'extracted': 3,
                                             'adjudicated': 0}
    wb = client.get(B + '/matrix?provenance=workbook').json()
    assert wb['total'] == 2
    assert wb['totals_by_provenance'] == {'workbook': 2, 'extracted': 0,
                                          'adjudicated': 0}
    ex = client.get(B + '/matrix?provenance=extracted').json()
    assert ex['total'] == 3
    assert ex['totals_by_provenance'] == {'workbook': 0, 'extracted': 3,
                                          'adjudicated': 0}
    # benchmark is never folded into the extraction total
    assert ex['total'] != all_r['total']


def test_unknown_event_dates_stay_unknown(client):
    r = client.get(B + '/matrix?provenance=extracted').json()
    by_rig = {x['rig']: x for x in r['rows']}
    assert by_rig['ADC-42L']['event_date'] is None
    assert by_rig['ADC-42L']['report_date'] == '2026-06-05'
    assert by_rig['ARO-3002']['event_date'] == '2026-06-06'
    # workbook rows: event clock is the sheet RIH date, no report clock
    w = client.get(B + '/matrix?provenance=workbook').json()
    assert w['rows'][0]['event_date'] == w['rows'][0]['date']
    assert w['rows'][0]['report_date'] is None
    assert r['unknown_event_dates'] == 2


def test_event_basis_excludes_unknowns_but_discloses_them(client):
    rep = client.get(
        B + '/matrix?start=2026-06-01&end=2026-06-10').json()
    assert rep['total'] == 3  # w1 + e1 + e2 on report basis
    ev = client.get(
        B + '/matrix?start=2026-06-01&end=2026-06-10'
        '&date_basis=event').json()
    assert ev['total'] == 2  # w1 + e2; e1 (unknown) excluded, not backfilled
    assert ev['unknown_event_dates'] == 2  # still disclosed at filter scope
    assert ev['selection']['date_basis'] == 'event'


def test_query_csv_xlsx_agree_on_same_selection(client):
    qs = 'start=2026-06-01&end=2026-06-30&provenance=extracted'
    q = client.get(B + '/matrix/query?' + qs).json()
    m = client.get(B + '/matrix?' + qs).json()
    assert q['total'] == m['total'] == 3
    assert (q['totals_by_provenance'] == m['totals_by_provenance']
            == {'workbook': 0, 'extracted': 3, 'adjudicated': 0})
    assert q['unknown_event_dates'] == m['unknown_event_dates'] == 2
    qp = client.post(B + '/matrix/query',
                     json={'start': '2026-06-01', 'end': '2026-06-30',
                           'provenance': 'extracted'}).json()
    assert qp['total'] == 3
    csv_r = client.get(B + '/matrix/export.csv?' + qs)
    assert csv_r.status_code == 200
    lines = csv_r.text.strip().splitlines()
    assert len(lines) == 4  # header + 3 rows
    assert lines[0].startswith('Date RIH,Report Date')
    xlsx_r = client.get(B + '/matrix/export.xlsx?' + qs)
    assert xlsx_r.status_code == 200
    wb = load_workbook(io.BytesIO(xlsx_r.content))
    assert wb['Details'].max_row - 1 == 3
    rec = {r[0]: r[3] for r in
           wb['Reconciliation'].iter_rows(min_row=2, values_only=True)}
    assert all(v == 'PASS' for v in rec.values()), rec


def test_changed_input_changes_output(client):
    base = client.get(
        B + '/matrix?start=2026-06-01&end=2026-06-30').json()['total']
    narrow = client.get(
        B + '/matrix?start=2026-06-01&end=2026-06-10').json()['total']
    assert narrow < base
    wfd = client.get(B + '/matrix?company=WFD').json()['total']
    assert wfd == 2
    bad = client.get(B + '/matrix?provenance=accepted')
    assert bad.status_code == 400
    bad2 = client.get(B + '/matrix?date_basis=spud')
    assert bad2.status_code == 400


def test_company_aliases_and_never_company_guards(client):
    # B4: report spellings resolve through company_aliases.json ...
    assert (client.get(B + '/matrix?company=HOWCO').json()['selection']['company']
            == 'HAL')
    assert (client.get(B + '/matrix?company=DAVIS-LYNCH').json()['selection']['company']
            == 'FET')
    # ... while Resp.Co codes never resolve to a company (R1 corollary).
    for code in ('WDV', 'HDV', 'TOD'):
        assert client.get(B + '/matrix?company=' + code).status_code == 400
    # status/location vocab is closed; unknown values are 400, never 500.
    assert client.get(B + '/matrix?status=APPROVED').status_code == 400
    assert client.get(B + '/matrix?location=jackup').status_code == 400
