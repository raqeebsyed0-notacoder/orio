"""Standalone backend check (no pytest in the hermes venv). Exit non-zero on failure."""
import os
import sqlite3
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG / 'plugins' / 'euphoria-orio-operations' / 'dashboard'))
sys.path.insert(0, str(PKG / 'data'))
os.environ['HERMES_HOME'] = tempfile.mkdtemp(prefix='orio-test-home-')

import build_db
import plugin_api
from fastapi import FastAPI
from fastapi.testclient import TestClient

build_db.main()
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
check('rigs=292', c.get(B + '/rigs?limit=1').json()['total'] == 292)
wells = {x['well'] for x in c.get(B + '/rigs?q=HP-707').json()['rows']}
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
csv = c.get(B + '/export.csv')
check('csv', csv.status_code == 200 and csv.text.count('\n') > 292)
src = (PKG / 'plugins' / 'euphoria-orio-operations' / 'dashboard' / 'plugin_api.py').read_text()
check('no-net', all(('import ' + m) not in src and ('from ' + m) not in src
                    for m in ['socket', 'urllib', 'httpx', 'requests', 'smtplib', 'email.mime']))
print('FAILURES:', fails if fails else 'none')
sys.exit(1 if fails else 0)
