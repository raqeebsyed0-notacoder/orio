"""Ingest the Ajeez-ruled June fixture into a matrix batch (B3 fix path).

Reads (read-only, never modified):
    06_Working-Notes/reviews/pipeline-v2-2026-10-19/phase7-ajeez-rulings/adjudicated-rows-v2.json

Writes:
    data/ingested/matrix/June2026-adjudicated-v2.json

Every fixture row becomes one matrix row with provenance='adjudicated';
ruling status (COUNTED / PENDING_FILE / PENDING_RULING / EXCLUDED),
location (onshore / offshore / null), authority, quote and note are
preserved verbatim inside evidence_json. The 13 innovex_own jobs travel in
the batch under 'innovex_own' and are fenced OUT of matrix_rows at build
time (build_db writes them to a separate innovex_own table, never counted
in competitor totals).

M5 fence (rules-v2 R1 corollary, orchestrator decision — extractor frozen):
a lone Resp.Co / work-marking code (WDV / HDV / TOD) with no tool brand
proves no company. The fixture already rules row 106 UNPROVEN; this
converter re-applies the guard so a future fixture carrying a bare code
normalises to UNPROVEN instead of a company.

June-boundary rows (130/131, ruled RIH date 2026-07-01 per R4) keep their
ruled date verbatim and carry june_boundary=true in evidence — labelled
separately, never silently folded into June.

Usage:
    python3 ingest_adjudicated.py [--json OUT]
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
PLUGIN_ROOT = HERE.parent
PROJECT_ROOT = PLUGIN_ROOT.parent
DEFAULT_FIXTURE = (PROJECT_ROOT / '06_Working-Notes' / 'reviews' /
                   'pipeline-v2-2026-10-19' / 'phase7-ajeez-rulings' /
                   'adjudicated-rows-v2.json')
DEFAULT_OUT = HERE / 'ingested' / 'matrix' / 'June2026-adjudicated-v2.json'

PROVENANCE = 'adjudicated'
STATUSES = ('COUNTED', 'PENDING_FILE', 'PENDING_RULING', 'EXCLUDED')
COMPANIES = ('WFD', 'HAL', 'FET', 'TAM', 'KSV', 'SLB', 'UNPROVEN')
# M5: Resp.Co / work-marking codes that are never companies alone.
NEVER_COMPANY = ('WDV', 'HDV', 'TOD')
LOCATIONS = ('onshore', 'offshore')
SIZE_BY_LABEL = {'9-5/8': '9.625', '13-3/8': '13.375', '18-5/8': '18.625'}


def _txt(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def normalise_company(raw: str | None) -> str:
    """M5 fence: a lone Resp.Co code is UNPROVEN, never a company."""
    code = (raw or '').strip().upper()
    if code in NEVER_COMPANY:
        return 'UNPROVEN'
    if code not in COMPANIES:
        raise ValueError('unknown company %r (want %s or %s)' %
                         (raw, COMPANIES, NEVER_COMPANY))
    return code


def convert_row(r: dict) -> dict:
    status = r.get('status')
    if status not in STATUSES:
        raise ValueError('row %r has unknown status %r' % (r.get('sno'), status))
    label = r.get('size_label')
    size = SIZE_BY_LABEL.get(label)
    if size is None:
        raise ValueError('row %r has unknown size_label %r' %
                         (r.get('sno'), label))
    try:
        numeric = float(r.get('size'))
    except (TypeError, ValueError):
        raise ValueError('row %r has non-numeric size %r' % (r.get('sno'), r.get('size')))
    if abs(numeric - float(size)) > 1e-6:
        raise ValueError('row %r size %r disagrees with label %r' %
                         (r.get('sno'), r.get('size'), label))
    loc = r.get('location')
    if loc is not None:
        loc = str(loc).strip().lower()
        if loc not in LOCATIONS:
            raise ValueError('row %r has unknown location %r' % (r.get('sno'), r.get('location')))
    company = normalise_company(r.get('company'))
    page = r.get('page')
    date_rih = _txt(r.get('date_rih'))
    out = {
        'sno': r.get('sno'),
        'date': date_rih,
        'rig': (_txt(r.get('rig')) or '').upper(),
        'well': (_txt(r.get('well')) or '').upper(),
        'size': size,
        'company': company,
        'location': loc,
        'status': status,
        'remarks': _txt(r.get('note')),
        'source_file': _txt(r.get('report_file')),
        'source_page': None if page is None else str(page),
        'extraction': PROVENANCE,
        'provenance': PROVENANCE,
        'authority': _txt(r.get('authority')),
        'quote': _txt(r.get('quote')),
        'june_boundary': bool(date_rih is not None and date_rih[:7] != '2026-06'),
    }
    return out


def ingest_fixture(path: Path = DEFAULT_FIXTURE) -> dict:
    raw = path.read_bytes()
    fixture = json.loads(raw.decode('utf-8'))
    rows = [convert_row(r) for r in fixture.get('rows', [])]
    counted = [r for r in rows if r['status'] == 'COUNTED']
    by_company = dict(Counter(r['company'] for r in counted if r['company'] != 'UNPROVEN'))
    by_size = dict(Counter(r['size'] for r in counted))
    by_location = dict(Counter(r['location'] for r in counted if r['location']))
    by_status = dict(Counter(r['status'] for r in rows))
    unproven = sum(1 for r in counted if r['company'] == 'UNPROVEN')
    boundary = [r['sno'] for r in counted if r['june_boundary']]
    own = fixture.get('innovex_own', [])
    return {
        'source_file': 'June2026-adjudicated-v2.json',
        'generator': 'data/ingest_adjudicated.py (FIX stage t_bdc51095)',
        'generated_at': dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'fixture': str(path),
        'fixture_sha256': hashlib.sha256(raw).hexdigest(),
        'fixture_totals_counted': fixture.get('totals_counted'),
        'row_count': len(rows),
        'status_counts': by_status,
        'counted': {'n': len(counted), 'by_company': by_company,
                    'by_size': by_size, 'by_location': by_location,
                    'unproven_company_rows': unproven,
                    'june_boundary_snos': boundary},
        'innovex_own_count': len(own),
        'rows': rows,
        'innovex_own': own,
    }


def main() -> None:
    out = ingest_fixture()
    print('fixture   :', DEFAULT_FIXTURE)
    print('sha256    :', out['fixture_sha256'][:16] + '...')
    print('rows      :', out['row_count'])
    print('statuses  :', out['status_counts'])
    print('counted   :', out['counted'])
    print('innovex   :', out['innovex_own_count'], '(fenced, not in matrix_rows)')
    if '--json' in sys.argv:
        dest = Path(sys.argv[sys.argv.index('--json') + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=1, ensure_ascii=False))
        print('wrote     :', dest)


if __name__ == '__main__':
    main()
