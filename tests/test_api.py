"""Headless tests for the ORIO Operations demo backend.

Runs against a THROWAWAY database (TMPDIR), never the installed demo DB:
  <venv python> -m pytest tests/test_api.py -q
"""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG / 'dashboard'))
sys.path.insert(0, str(PKG / 'data'))

os.environ['HERMES_HOME'] = tempfile.mkdtemp(prefix='orio-test-home-')

import build_db  # noqa: E402
import plugin_api  # noqa: E402


@pytest.fixture(scope='module')
def client():
    build_db.main()
    app = FastAPI()
    app.include_router(plugin_api.router, prefix='/api/plugins/euphoria-orio-operations')
    return TestClient(app)


def test_health(client):
    r = client.get('/api/plugins/euphoria-orio-operations/health')
    assert r.status_code == 200 and r.json()['ok'] is True
    assert r.json()['external_actions'] is False


def test_rig_count_is_292(client):
    r = client.get('/api/plugins/euphoria-orio-operations/rigs?limit=1')
    assert r.json()['total'] == 292


def test_hp707_search_returns_two_cycles(client):
    r = client.get('/api/plugins/euphoria-orio-operations/rigs?q=HP-707')
    wells = {x['well'] for x in r.json()['rows']}
    assert 'THRY-961602' in wells
    r2 = client.get('/api/plugins/euphoria-orio-operations/jobs/hp707now')
    assert r2.json()['well'] == 'THRY-961602'
    r3 = client.get('/api/plugins/euphoria-orio-operations/history')
    assert any('THRY-961612' in e['text'] or '961612' in r3.json()['job'] for e in r3.json()['events'])


def test_sp32_conflict_visible(client):
    r = client.get('/api/plugins/euphoria-orio-operations/jobs/sp32')
    j = r.json()
    assert j['lifecycle'] == 'CONFLICT'
    texts = ' '.join(e['text'] for e in j['evidence'])
    assert 'SLB KSV' in texts and 'Qty 2' in texts


def test_sp262_blocks_mdd(client):
    r = client.get('/api/plugins/euphoria-orio-operations/jobs/sp262')
    assert r.json()['lifecycle'] == 'INSUFFICIENT EVIDENCE'
    assert not any(a['kind'] == 'Prepare MDD' for a in r.json()['actions'])


def test_approve_db_update_mutates_demo_only(client):
    r = client.post('/api/plugins/euphoria-orio-operations/actions/a-hp701-db/decision',
                    json={'decision': 'approve', 'note': 'test'})
    assert r.json()['ok'] is True and r.json()['demo_only'] is True
    j = client.get('/api/plugins/euphoria-orio-operations/jobs/hp701').json()
    assert j['lifecycle'] == 'RIH CONFIRMED'


def test_blocked_action_cannot_approve(client):
    # fresh db state per module run: reset a-hp701-mdd to blocked first
    db = Path(os.environ['HERMES_HOME']) / 'state' / 'orio-ops' / 'orio_demo.db'
    con = sqlite3.connect(str(db))
    con.execute("UPDATE actions SET state='blocked' WHERE id='a-hp701-mdd'")
    con.commit()
    con.close()
    r = client.post('/api/plugins/euphoria-orio-operations/actions/a-hp701-mdd/decision',
                    json={'decision': 'approve'})
    assert r.status_code == 409


def test_reject_and_incorrect(client):
    r = client.post('/api/plugins/euphoria-orio-operations/actions/a-sp93-dispatch/decision',
                    json={'decision': 'reject', 'note': 'not yet'})
    assert r.json()['state'] == 'rejected'
    r = client.post('/api/plugins/euphoria-orio-operations/actions/a-ad74-dispatch/decision',
                    json={'decision': 'incorrect'})
    assert r.json()['state'] == 'incorrect'


def test_mdd_preview_marks_missing(client):
    r = client.get('/api/plugins/euphoria-orio-operations/mdd/preview?job=hp701')
    body = ' '.join(v for _, v in r.json()['lines'])
    assert 'MISSING - REQUIRES AJEEZ / SOURCE DATA' in body
    assert 'PO 4508154877 belongs to HP-704' in r.json()['cross_check']
    assert r.json()['send_enabled'] is False


def test_email_draft_never_sends(client):
    r = client.post('/api/plugins/euphoria-orio-operations/drafts/email', json={'job': 'hp701'})
    assert r.json()['sent'] is False
    assert 'MISSING' in r.json()['body']


def test_export_csv(client):
    r = client.get('/api/plugins/euphoria-orio-operations/export.csv')
    assert r.status_code == 200 and 'text/csv' in r.headers['content-type']
    assert r.text.count('\n') > 292  # header + 292 rows


def test_no_network_imports():
    src = (PKG / 'plugins' / 'euphoria-orio-operations' / 'dashboard' / 'plugin_api.py').read_text()
    for mod in ['socket', 'urllib', 'httpx', 'requests', 'smtplib', 'email.mime']:
        assert f'import {mod}' not in src and f'from {mod}' not in src, mod
