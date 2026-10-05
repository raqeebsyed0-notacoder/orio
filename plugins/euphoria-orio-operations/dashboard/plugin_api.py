# ruff: noqa: BLE001
"""ORIO Operations demo backend — local SQLite, zero external calls.

Mounted at ``/api/plugins/euphoria-orio-operations/`` by the Hermes
dashboard plugin system (``dashboard/manifest.json`` declares
``api=plugin_api.py``; the plugin must be listed in ``plugins.enabled``
before the serve process imports it).

Demo safety: this module opens NO sockets, sends NO mail, touches NO
production system. Every read and write targets the demo database at
``<HERMES_HOME>/state/orio-ops/orio_demo.db`` (WAL), built by
``data/build_db.py`` from Ajeez's supplied Sep 19 files. Approving an
action mutates DEMO STATE ONLY.

Production path: replace the ``_db``/query layer with the production
adapters (OneDrive ingestion -> operational datastore). The route shapes
stay the same so the desktop UI does not change.
"""

from __future__ import annotations

import csv
import io
import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response

try:  # available in-gateway; tests get it via the hermes-agent venv
    from hermes_constants import get_hermes_home
except Exception:  # pragma: no cover - defensive fallback
    def get_hermes_home() -> Path:  # type: ignore[misc]
        return Path(os.environ.get('HERMES_HOME') or Path.home() / '.hermes')


def _db_path() -> Path:
    return Path(get_hermes_home()) / 'state' / 'orio-ops' / 'orio_demo.db'


@contextmanager
def _db() -> Iterator[sqlite3.Connection]:
    p = _db_path()
    if not p.exists():
        raise HTTPException(503, 'Demo database not built yet. Run data/build_db.py.')
    con = sqlite3.connect(str(p))
    con.row_factory = sqlite3.Row
    try:
        yield con
    finally:
        con.close()


def _row(r: sqlite3.Row) -> dict[str, Any]:
    return dict(r)


router = APIRouter()


@router.get('/health')
def health() -> dict[str, Any]:
    p = _db_path()
    return {'ok': p.exists(), 'db': str(p), 'demo': True, 'external_actions': False}


@router.get('/meta')
def meta() -> dict[str, Any]:
    with _db() as con:
        m = {r['key']: r['value'] for r in con.execute('SELECT * FROM meta')}
    return {'demo_date': '2026-09-19', 'built_from': m.get('built_from', '?'),
            'banner': 'DEMO - LOCAL DATA ONLY. NO EXTERNAL ACTIONS ENABLED.'}


PRIORITY_RANK = {'critical': 0, 'high': 1, 'medium': 2, 'info': 3}


@router.get('/today')
def today() -> dict[str, Any]:
    with _db() as con:
        jobs = [_row(r) for r in con.execute('SELECT * FROM jobs')]
        actions = [_row(r) for r in con.execute("SELECT * FROM actions WHERE state='awaiting'")]
        exc = con.execute("SELECT COUNT(*) c FROM exceptions WHERE state='open'").fetchone()['c']
    jobs.sort(key=lambda j: PRIORITY_RANK.get(j['priority'], 9))
    cards = [
        {'key': 'attention', 'label': 'Requires Attention',
         'value': sum(1 for j in jobs if j['priority'] in ('critical', 'high'))},
        {'key': 'dispatch', 'label': 'Dispatch Checks',
         'value': sum(1 for j in jobs if j['lifecycle'] == 'DISPATCH CHECK')},
        {'key': 'rih', 'label': 'RIH Confirmed',
         'value': sum(1 for j in jobs if 'RIH CONFIRMED' in j['lifecycle'])},
        {'key': 'landing', 'label': 'Landing Confirmed',
         'value': sum(1 for j in jobs if 'LAND' in j['lifecycle'])},
        {'key': 'mdd', 'label': 'MDD Due',
         'value': sum(1 for a in actions if a['kind'] == 'Prepare MDD')},
        {'key': 'conflict', 'label': 'Product Conflicts',
         'value': sum(1 for j in jobs if j['lifecycle'] == 'CONFLICT')},
    ]
    items = [{
        'job_id': j['id'], 'priority': j['priority'], 'rig': j['rig'], 'well': j['well'],
        'stage': j['lifecycle'], 'finding': j['finding'],
        'action_required': next((a['title'] for a in actions if a['job_id'] == j['id']), 'Monitor'),
        'evidence_state': _evidence_state(con_job_evidence(j['id'])),
        'source_page': j['first_page'],
        'approval': _approval_of(j['id'], actions),
    } for j in jobs]
    return {'cards': cards, 'items': items, 'open_exceptions': exc,
            'date_rule': 'SOURCE TIME shown. DATE NORMALIZATION: AWAITING RULE CONFIRMATION.'}


def con_job_evidence(job_id: str) -> list[dict[str, Any]]:
    with _db() as con:
        return [_row(r) for r in
                con.execute('SELECT * FROM evidence WHERE job_id=?', (job_id,))]


def _evidence_state(ev: list[dict[str, Any]]) -> str:
    states = {e['status'] for e in ev}
    if 'CONFLICTING' in states:
        return 'CONFLICT'
    if 'INSUFFICIENT' in states:
        return 'INSUFFICIENT EVIDENCE'
    if 'AWAITING AJEEZ' in states:
        return 'AWAITING AJEEZ'
    return 'CONFIRMED'


def _approval_of(job_id: str, actions: list[dict[str, Any]]) -> str:
    mine = [a for a in actions if a['job_id'] == job_id]
    if not mine:
        return 'Monitoring'
    if any(a['state'] == 'blocked' for a in mine):
        return 'Blocked'
    return 'Awaiting Ajeez'


@router.get('/actions')
def action_list() -> dict[str, Any]:
    with _db() as con:
        actions = [_row(r) for r in con.execute('SELECT * FROM actions')]
        for a in actions:
            dec = con.execute(
                'SELECT decision, note, at FROM decisions WHERE action_id=?'
                ' ORDER BY id DESC LIMIT 1', (a['id'],)).fetchone()
            a['last_decision'] = dict(dec) if dec else None
            if a['job_id']:
                j = con.execute('SELECT rig, well FROM jobs WHERE id=?',
                                (a['job_id'],)).fetchone()
                a['scope'] = ('%s / %s' % (j['rig'], j['well'])) if j else 'General'
            else:
                a['scope'] = 'General'
    return {'actions': actions}


@router.post('/actions/{action_id}/decision')
def decide(action_id: str, body: dict[str, Any]) -> dict[str, Any]:
    decision = (body.get('decision') or '').lower()
    note = (body.get('note') or '').strip()[:500]
    if decision not in ('approve', 'reject', 'incorrect'):
        raise HTTPException(400, 'decision must be approve, reject, or incorrect')
    with _db() as con:
        a = con.execute('SELECT * FROM actions WHERE id=?', (action_id,)).fetchone()
        if not a:
            raise HTTPException(404, 'unknown action')
        a = _row(a)
        if decision == 'approve' and a['state'] == 'blocked':
            raise HTTPException(409, 'Action is blocked: identifiers missing. Resolve first.')
        new_state = {'approve': 'approved', 'reject': 'rejected',
                     'incorrect': 'incorrect'}[decision]
        con.execute('UPDATE actions SET state=? WHERE id=?', (new_state, action_id))
        con.execute('INSERT INTO decisions(action_id,decision,note) VALUES (?,?,?)',
                    (action_id, decision, note or None))
        applied = None
        if decision == 'approve' and action_id == 'a-hp701-db':
            con.execute("UPDATE jobs SET lifecycle='RIH CONFIRMED' WHERE id='hp701'")
            con.execute("UPDATE actions SET state='awaiting' WHERE id='a-hp701-mdd'"
                        ' AND state=\'blocked\'')
            applied = ('HP-701 lifecycle recorded as RIH CONFIRMED in demo DB. '
                       'MDD preparation unblocked for drafting (identifiers still missing).')
        con.commit()
    return {'ok': True, 'action': action_id, 'state': new_state,
            'demo_only': True, 'applied': applied}


@router.get('/rigs')
def rigs(q: str = Query(''), limit: int = Query(60, le=292),
         offset: int = Query(0, ge=0)) -> dict[str, Any]:
    with _db() as con:
        if q:
            like = '%' + q.upper() + '%'
            total = con.execute(
                'SELECT COUNT(*) c FROM rig_blocks WHERE UPPER(rig) LIKE ?'
                ' OR UPPER(well) LIKE ?', (like, like)).fetchone()['c']
            rows = [_row(r) for r in con.execute(
                'SELECT rig, well, first_page, pages, stage, orio_relevance FROM rig_blocks'
                ' WHERE UPPER(rig) LIKE ? OR UPPER(well) LIKE ?'
                ' ORDER BY rig, well LIMIT ? OFFSET ?', (like, like, limit, offset))]
        else:
            total = con.execute('SELECT COUNT(*) c FROM rig_blocks').fetchone()['c']
            rows = [_row(r) for r in con.execute(
                'SELECT rig, well, first_page, pages, stage, orio_relevance FROM rig_blocks'
                ' ORDER BY rig, well LIMIT ? OFFSET ?', (limit, offset))]
    return {'total': total, 'rows': rows}


@router.get('/rigs/{rig}/{well}')
def rig_detail(rig: str, well: str) -> dict[str, Any]:
    with _db() as con:
        b = con.execute('SELECT * FROM rig_blocks WHERE rig=? AND well=?',
                        (rig.upper(), well.upper())).fetchone()
        if not b:
            raise HTTPException(404, 'Rig+Well not in Sep 19 index')
        b = _row(b)
        job = con.execute('SELECT * FROM jobs WHERE rig=? AND well=?',
                          (rig.upper(), well.upper())).fetchone()
        out = dict(b)
        if job:
            job = _row(job)
            job['evidence'] = [_row(r) for r in con.execute(
                'SELECT * FROM evidence WHERE job_id=?', (job['id'],))]
            job['actions'] = [_row(r) for r in con.execute(
                'SELECT * FROM actions WHERE job_id=?', (job['id'],))]
            out['job'] = job
        else:
            out['job'] = None
    return out


@router.get('/jobs/{job_id}')
def job_detail(job_id: str) -> dict[str, Any]:
    with _db() as con:
        j = con.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not j:
            raise HTTPException(404, 'unknown job')
        j = _row(j)
        j['evidence'] = [_row(r) for r in con.execute(
            'SELECT * FROM evidence WHERE job_id=? ORDER BY page', (job_id,))]
        j['actions'] = [_row(r) for r in con.execute(
            'SELECT * FROM actions WHERE job_id=?', (job_id,))]
        j['tracker'] = [_row(r) for r in con.execute(
            'SELECT * FROM tracker_rows WHERE rig=? AND well=?', (j['rig'], j['well']))]
        j['exceptions'] = [_row(r) for r in con.execute(
            'SELECT * FROM exceptions WHERE job_id=?', (job_id,))]
    return j


@router.get('/lifecycle')
def lifecycle() -> dict[str, Any]:
    with _db() as con:
        jobs = [_row(r) for r in con.execute(
            'SELECT id, rig, well, cycle, lifecycle, priority, finding, first_page FROM jobs')]
    order = ['CONFLICT', 'DISPATCH CHECK', 'INSUFFICIENT EVIDENCE', 'LANDING EVIDENCE',
             'RIH CONFIRMED', 'MONITORING']
    jobs.sort(key=lambda j: order.index(j['lifecycle']) if j['lifecycle'] in order else 99)
    return {'jobs': jobs,
            'note': 'States are assigned only where source evidence supports them.'}


@router.get('/exceptions')
def exceptions() -> dict[str, Any]:
    with _db() as con:
        rows = [_row(r) for r in con.execute('SELECT * FROM exceptions ORDER BY id')]
    return {'exceptions': rows}


@router.post('/exceptions/{exc_id}/resolve')
def resolve_exception(exc_id: int, body: dict[str, Any]) -> dict[str, Any]:
    note = (body.get('note') or '').strip()[:500]
    if not note:
        raise HTTPException(400, 'A resolution note is required (demo annotation).')
    with _db() as con:
        cur = con.execute("UPDATE exceptions SET state='resolved' WHERE id=?", (exc_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, 'unknown exception')
        con.execute('INSERT INTO decisions(action_id,decision,note) VALUES (?,?,?)',
                    ('exception:%d' % exc_id, 'resolve', note))
        con.commit()
    return {'ok': True, 'demo_only': True}


@router.get('/history')
def history() -> dict[str, Any]:
    with _db() as con:
        rows = [_row(r) for r in con.execute('SELECT * FROM history ORDER BY date')]
    return {'job': 'HP-707 / THRY-961612',
            'note': 'Benchmark reconstructed ONLY from Ajeez-supplied daily reports. '
                    'File labelled Sep 14 MR 3 pages.pdf is HP-703 / HZEM-491812: '
                    'SOURCE MISMATCH, excluded.',
            'events': rows}


@router.get('/expansion')
def expansion() -> dict[str, Any]:
    with _db() as con:
        rows = [_row(r) for r in con.execute('SELECT * FROM expansion ORDER BY date, rig')]
    return {'scope': 'OUTSIDE CURRENT ORIO PILOT SCOPE',
            'statement': ('The current pilot may demonstrate that the Morning Report extraction '
                          'foundation can support this workflow. Full competitor-intelligence '
                          'automation requires separate scope approval.'),
            'fields': ['Date RIH', 'Rig', 'Well', 'Size', 'Company', 'Special Remarks'],
            'rows': rows}


@router.get('/export.csv')
def export_csv() -> Response:
    buf = io.StringIO()
    with _db() as con:
        rows = con.execute('SELECT * FROM rig_blocks ORDER BY first_page')
        w = csv.writer(buf)
        w.writerow(['rig', 'well', 'first_page', 'pages', 'stage', 'orio_relevance',
                    'last_24h', 'next_24h'])
        for r in rows:
            w.writerow([r['rig'], r['well'], r['first_page'], r['pages'],
                        r['stage'], r['orio_relevance'], r['last24'], r['next24']])
    return Response(content=buf.getvalue(), media_type='text/csv',
                    headers={'Content-Disposition':
                             'attachment; filename="orio_demo_rig_index_2026-09-19.csv"'})


@router.get('/mdd/preview')
def mdd_preview(job: str = Query('hp701')) -> dict[str, Any]:
    with _db() as con:
        j = con.execute('SELECT * FROM jobs WHERE id=?', (job,)).fetchone()
        if not j:
            raise HTTPException(404, 'unknown job')
        j = _row(j)
        docs = [_row(r) for r in con.execute('SELECT * FROM mdd_docs')]
        hp704 = con.execute("SELECT well FROM rig_blocks WHERE rig='HP-704'").fetchall()
    lines = [
        ('Job', '%s / %s' % (j['rig'], j['well'])),
        ('RIH evidence', 'Confirmed Sep 19 MR pp%d-%d' % (j['first_page'], j['first_page'] + j['pages'] - 1)
         if job == 'hp701' else 'See job evidence'),
        ('RIH date / time', 'SOURCE: Sep 19 MR 05:00-05:00 period. Normalized date AWAITING RULE CONFIRMATION.'),
        ('Foreman', j['foreman'] or 'MISSING - REQUIRES AJEEZ / SOURCE DATA'),
        ('PO number', 'MISSING - REQUIRES AJEEZ / SOURCE DATA'),
        ('Shipment number', 'MISSING - REQUIRES AJEEZ / SOURCE DATA'),
        ('Signature contact', 'MISSING - REQUIRES AJEEZ / SOURCE DATA'),
    ]
    cross = ('Supplied MDD PO 4508154877 belongs to HP-704 / THRY-95140. Sep 19 shows HP-704 on '
             + (hp704[0]['well'] if hp704 else 'a different well')
             + ' (normal rig move). It cannot be reused for this job.')
    return {'job': '%s / %s' % (j['rig'], j['well']), 'lines': lines,
            'supplied_mdd': docs, 'cross_check': cross, 'send_enabled': False,
            'send_note': 'Production connection disabled in demo. Preview only.'}


@router.post('/drafts/email')
def draft_email(body: dict[str, Any]) -> dict[str, Any]:
    job_id = body.get('job') or 'hp701'
    with _db() as con:
        j = con.execute('SELECT * FROM jobs WHERE id=?', (job_id,)).fetchone()
        if not j:
            raise HTTPException(404, 'unknown job')
        j = _row(j)
        text = ('To: MISSING - REQUIRES AJEEZ / SOURCE DATA\n'
                'Subject: ORIO %s / %s - %s\n\nFinding: %s\n'
                'Evidence: Sep 19 MR pages %d-%d. Foreman: %s.\n'
                'Date rule: SOURCE TIME. Normalization AWAITING CONFIRMATION.\n'
                'This is a LOCAL DEMO PREVIEW. Nothing was sent.'
                % (j['rig'], j['well'], j['lifecycle'], j['finding'],
                   j['first_page'], j['first_page'] + j['pages'] - 1, j['foreman']))
        cur = con.execute("INSERT INTO drafts(kind,ref,body) VALUES ('email',?,?)",
                          (job_id, text))
        con.commit()
        did = cur.lastrowid
    return {'ok': True, 'draft_id': did, 'body': text, 'sent': False}


@router.get('/drafts')
def drafts() -> dict[str, Any]:
    with _db() as con:
        rows = [_row(r) for r in con.execute('SELECT * FROM drafts ORDER BY id DESC LIMIT 20')]
    return {'drafts': rows, 'send_enabled': False}
