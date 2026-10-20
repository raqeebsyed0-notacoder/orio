"""June-only Jev consumer. Outputs are UNACCEPTED repair candidates, never publication.

Legacy chosen-company verification is invalid under v4. Preserve its scores,
route to review, and retain source-audited candidates separately. No calibration
or PDF-to-Excel performance is inferred from cache replay.
"""
from __future__ import annotations
import argparse
import contextlib
import hashlib
import json
import re
import sys
import time
import uuid
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
NOTES = ROOT / '06_Working-Notes'
sys.path.insert(0, str(ROOT / '05_Architecture'))
import jev_adjudicate as ja

SIZE_CANON = {'9.625': r'9(?:\.625|[- ]5/8)',
              '13.375': r'13(?:\.375|[- ]3/8)',
              '18.625': r'18(?:\.625|[- ]5/8)'}
COMPANY_TOKENS = {'WFD': r'WFD|WEATHERFORD',
                  # Rules-v2 R3: HOWCO on a DV tool string is the Halliburton
                  # alias (row 25). KSV entry covers SLB/KSV Schlumberger
                  # markings. WDV/HDV/TOD are DELIBERATELY absent: R1 corollary
                  # says a lone Resp.Co code proves no company (row 106
                  # UNPROVEN) — see company_aliases.json never_company.
                  'HAL': r'HLB|HALL|HAL|HALLIBURTON|HALIBURTON|HOWCO',
                  'FET': r'FET|DAVIS[- ]LYNCH', 'TAM': r'TAM',
                  'KSV': r'KSV|SLB|SCHLUMBERGER'}
DV = re.compile(r'\bDV(?:S)?\b(?:\s+(?:TOOL|ASSY|ASSEMBL|PACKER|PUP|GAS))?', re.I)
# Surface preparation/installation alone never establishes a downhole run.
# M/U and INSTALL stay observed-run verbs: the June corpus phrases genuine
# time-log DV steps as M/U/INSTALL without a second RIH token (35 June
# CONFIRMED clusters measured 2026-10-16); the defect was surface-qualified
# or negated makeup, gated by BAD plus whole-piece carry below.
OBSERVED = re.compile(r'\b(?:RIH|RAN|RUNNING|RUN INTO (?:THE )?HOLE|INSTALL(?:ED)?|M/U|M/UP|MADE UP|MAKE UP)\b', re.I)
BAD = re.compile(
    r'\b(?:PLAN(?:NED)?|WILL|NEXT|TO BE|DRILL[ -]?OUT|DRILLING OUT|CLEANOUT|'
    r'ON[ -]?BOARD|INVENTORY|ON\s+SURFACE|FUNCTION TEST|NOT(?:\s+YET)?\s+(?:RUN|RAN|RIH)|'
    r'(?:RUN|RIH)\s+NOT|NO DV|DID NOT|HAS NOT|HAVE NOT|NEVER RUN)\b', re.I)
TIME = re.compile(r'\b([0-2]\d[0-5]\d)\s*-\s*([0-2]\d[0-5]\d)\b')


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextlib.contextmanager
def source_phase(source, ledger, phase, run_id, measurement_scope):
    """Measure actual caller processing, including hash I/O; failures always logged."""
    source = Path(source)
    rec = {'source_file': str(source), 'source_sha256': None,
           'attempt_id': str(uuid.uuid4()), 'run_id': run_id, 'phase': phase,
           'measurement_scope': measurement_scope, 'start_utc': datetime.now(timezone.utc).isoformat(),
           'status': 'ok'}
    started = time.perf_counter()
    try:
        rec['source_sha256'] = sha256(source)
        yield rec
    except BaseException as exc:
        rec.update(status='failed', error_class=type(exc).__name__)
        raise
    finally:
        rec['end_utc'] = datetime.now(timezone.utc).isoformat()
        rec['elapsed_seconds'] = time.perf_counter() - started
        if ledger is not None:
            Path(ledger).parent.mkdir(parents=True, exist_ok=True)
            with Path(ledger).open('a', encoding='utf-8') as fh:
                fh.write(json.dumps(rec, allow_nan=False) + '\n')


def valid_page(page):
    return type(page) is int and page > 0


def valid_source(event):
    name = event.get('source_file')
    return (isinstance(name, str) and name.lower().endswith('.pdf')
            and not any(c in name for c in ';|\r\n')
            and valid_page(event.get('source_page')))


def direct_support(context):
    """Conservative statement-local relations; false negatives remain review.

    Never read precomputed event size/owner. No whole-page token cooccurrence.
    Future sections remain future until an explicit operations/time-log boundary.
    Multiple supplier/size tuples or job headers require manual review.
    """
    if not isinstance(context, str) or not context.strip():
        return []
    if re.search(r'\b(?:RIG|WELL)\s*[:=]', context, re.I):
        return []  # possible adjacent job/header, not a bounded operation span
    supports = []
    context = re.split(r'\b(?:NEXT\s+24\s*HR\s+PLAN|PLAN(?:NED)?\s*:)', context, flags=re.I)[0]
    # A time-log row is a real operation boundary, not a full-page token bag.
    pieces = re.split(r'(?=\b[0-2]\d[0-5]\d\s*-\s*[0-2]\d[0-5]\d\b)', context)
    for piece in pieces:
        # Retain only pre-plan material; later plan tokens must not bless a run.
        piece = re.split(r'\bNext\s+24\s*hr\s+plan\b', piece, flags=re.I)[0]
        # Evaluate the complete time-log operation before splitting clauses. A
        # semicolon/newline/full stop cannot erase NOT YET RUN or a surface test.
        # Uncertain mixed operations stay review, even at the cost of recall.
        if BAD.search(piece):
            continue
        for sentence in re.split(r'[;\n!?]|(?<!\d)\.|\.(?!\d)', piece):
            text = sentence.strip()
            if not DV.search(text) or not OBSERVED.search(text) or BAD.search(text):
                continue
            sizes = [(size, m) for size, pat in SIZE_CANON.items()
                     for m in re.finditer(r'(?<![\d.])(?:' + pat + r')(?![\d/])', text, re.I)]
            owners = [(owner, m) for owner, pat in COMPANY_TOKENS.items()
                      for m in re.finditer(r'\b(?:' + pat + r')\b', text, re.I)]
            if len({s for s, _ in sizes}) != 1 or len({o for o, _ in owners}) != 1:
                continue
            dv = DV.search(text)
            size, sm = min(sizes, key=lambda x: abs(x[1].start() - dv.start()))
            owner, om = min(owners, key=lambda x: abs(x[1].start() - dv.start()))
            # Narrow local relation only. Responsibility codes alone are not names.
            lo, hi = min(sm.start(), om.start(), dv.start()), max(sm.end(), om.end(), dv.end())
            relation = text[lo:hi]
            if hi - lo > 110 or re.search(r'\b(?:RESPONSIBILITY|LAST CSG|HEADER|PREVIOUS|CASING ONLY)\b', text, re.I):
                continue
            # Require size + supplier near the DV phrase, not behind independent ops.
            if (re.search(r'\b(?:THEN|AFTER|WHILE|BUT|CMT|HEAD|PUMP|LOGGING|RESPONSIBLE|TUBING|OTHER)\b|R/U', relation, re.I)
                    or (re.search(r'\b(?:CSG|CASING)\b', relation, re.I)
                        and not re.search(r'\bWITH\b', relation, re.I))):
                continue
            tm = TIME.search(text)
            supports.append({'size': size, 'owner': owner, 'quote': piece.strip(),
                             'size_span': sm.group(), 'supplier_span': om.group(),
                             'event_time': tm.group() if tm else None,
                             'event_state': 'observed'})
    return supports


def support_spans(r, events):
    supports = []
    for e in events:
        if not valid_source(e):
            continue
        if any(e.get(k) != r.get(k) for k in ('date', 'rig', 'well')):
            continue
        for support in direct_support(e.get('context')):
            supports.append(dict(support, source_file=e['source_file'],
                                 source_page=e['source_page']))
    return supports


def audit_spans(r, evs):
    """Compatibility tuple: ok, reason, size, owner, pages, files."""
    size, owner = r.get('size'), r.get('owner')
    pages = sorted({e['source_page'] for e in evs if valid_source(e)})
    files = sorted({e['source_file'] for e in evs if valid_source(e)})
    if not evs or any(not valid_source(e) for e in evs):
        return False, 'missing/invalid physical-page lineage', size, owner, pages, files
    if r.get('verdict') not in ('CONFIRMED', 'ADOPTED'):
        return False, 'ineligible/unknown verdict', size, owner, pages, files
    spans = support_spans(r, evs)
    tuples = {(s['size'], s['owner']) for s in spans}
    if (size, owner) not in tuples:
        return False, 'no direct observed DV size/supplier span', size, owner, pages, files
    if len(tuples) != 1:
        return False, 'multiple DV tuples require separate run identity', size, owner, pages, files
    times = {s['event_time'] for s in spans if s['event_time']}
    if len(times) > 1:
        return False, 'multiple operation times require run disambiguation', size, owner, pages, files
    if r['verdict'] == 'ADOPTED':
        if r.get('code_owner') != 'UNKNOWN':
            return False, 'ADOPTED requires unknown code owner', size, owner, pages, files
    elif r.get('code_owner') != owner:
        return False, 'CONFIRMED code owner mismatch', size, owner, pages, files
    return True, '', size, owner, pages, files


def cache_valid(r, events=None):
    meta = r.get('cache', {})
    if any(meta.get(k) != v for k, v in (
            ('schema_version', ja.SCHEMA_VERSION), ('state_version', ja.STATE_VERSION),
            ('policy_version', ja.POLICY_VERSION), ('question_hash', ja.QUESTION_HASH),
            ('policy_hash', ja.POLICY_HASH), ('model', 'jev-1.13.0'))):
        return False
    if events is not None and meta != ja.cache_metadata(ja.make_state(events), 'jev-1.13.0'):
        return False
    body = {k: v for k, v in meta.items() if k != 'cache_key'}
    return (isinstance(meta.get('input_hash'), str) and len(meta['input_hash']) == 64
            and meta.get('cache_key') == hashlib.sha256(json.dumps(body, sort_keys=True).encode()).hexdigest())


def scores_valid(r):
    j = r.get('jev', {})
    return (j.get('model') == 'jev-1.13.0'
            and j.get('supplier_support') == ja.SUPPLIER_SUPPORT
            and ja.INV_DISPLAY.get(j.get('choice')) == r.get('owner')
            and ja.adopt_approved(j.get('confidence'), j.get('tool_run'), j.get('verify_absent')))


def make_row(r, events):
    sources = support_spans(r, events)
    pairs = sorted({(s['source_file'], s['source_page']) for s in sources})
    return {**{k: r.get(k) for k in ('date', 'rig', 'well', 'size', 'owner', 'verdict', 'code_owner', 'jev', 'cache')},
            'report_date': r['date'], 'date_rih': None,
            'normalized_operational_date': 'AWAITING AJEEZ CONFIRMATION',
            'run_identity': {'rig': r['rig'], 'well': r['well'], 'report_date': r['date'],
                             'status': 'candidate cluster; cycle/run requires verification'},
            'provenance': 'extracted', 'source_file': pairs[0][0], 'source_page': pairs[0][1],
            'source_pages': sorted({page for _, page in pairs}),
            'sources': sources, 'acceptance': 'UNACCEPTED CANDIDATE'}


def verify_pdf_source(path, page, quote, ledger, run_id):
    """Exact declared 1-based physical page. No page-window substitutions."""
    import fitz
    with source_phase(path, ledger, 'physical_page_verification', run_id,
                      'SHA256 plus one declared PDF page; not whole-file extraction') as rec:
        with fitz.open(path) as doc:
            rec.update(pages_total=len(doc), pages_checked=[page])
            if not valid_page(page) or page > len(doc):
                rec['status'] = 'SOURCE_INVALID'
                return False
            text = doc[page - 1].get_text()
            if not text.strip():
                rec['status'] = 'OCR_NEEDED'
                return False
            norm = lambda s: re.sub(r'\s+', ' ', s).strip()
            ok = bool(quote) and norm(quote) in norm(text)
            rec['status'] = 'ok' if ok else 'QUOTE_NOT_ON_PAGE'
            return ok


def consume(results, by_key, verifier=None):
    rows, ledger, candidates, boundary = [], [], [], []
    for n, r in enumerate(results):
        key = tuple(r.get(k) for k in ('date', 'rig', 'well'))
        evs = by_key.get(key, [])
        rec = {'input_index': n, 'input': r, 'sources': evs}
        date = r.get('date', '')
        if date == '2026-07-01':
            disposition, reason = 'JUNE_BOUNDARY_REVIEW', 'July1 report; June event date not established'
            boundary.append(rec)
        elif not re.fullmatch(r'2026-06-(?:0[1-9]|[12]\d|30)', date):
            disposition, reason = 'OUT_OF_SCOPE', 'June-only; later-month inference disabled'
        elif r.get('verdict') not in ('CONFIRMED', 'ADOPTED', 'REVIEW', 'CONFLICT', 'NOT_A_RUN'):
            disposition, reason = 'SOURCE_INVALID', 'unknown verdict'
        elif not evs or any(not valid_source(e) for e in evs):
            disposition, reason = 'SOURCE_INVALID', 'missing/invalid source file or physical page'
        elif r.get('verdict') == 'CONFLICT':
            disposition, reason = 'CONFLICT', 'model/code disagreement retained; no publication'
        elif (r.get('verdict') == 'NOT_A_RUN' and cache_valid(r, evs)
              and ja.probability(r.get('jev', {}).get('tool_run')) is not None
              and r['jev']['tool_run'] < ja.NOT_A_RUN_BELOW):
            disposition, reason = 'NOT_A_RUN', 'versioned observed-run question below frozen cutoff'
        else:
            ok, reason, *_ = audit_spans(r, evs)
            if ok:
                candidates.append(make_row(r, evs))
            if not cache_valid(r, evs):
                disposition, reason = 'REVIEW', 'legacy/unversioned cache: chosen-company verification INVALID; ' + reason
            elif not ok:
                disposition = 'SOURCE_INVALID' if not evs or any(not valid_source(e) for e in evs) else 'REVIEW'
            elif not scores_valid(r):
                disposition, reason = 'REVIEW', 'invalid/missing scores or thresholds'
            elif verifier is None:
                disposition, reason = 'REVIEW', 'physical-page verification required before publication'
            else:
                row = make_row(r, evs)
                if all(verifier(s) for s in row['sources']):
                    row['physical_page_verified'] = True
                    rows.append(row)
                    disposition, reason = 'ELIGIBLE_CANDIDATE', 'v3 judgment plus direct physical-page evidence; not acceptance'
                else:
                    disposition, reason = 'SOURCE_INVALID', 'quote absent on declared physical page or OCR required'
        ledger.append(dict(rec, disposition=disposition, reason=reason))
    assert len(ledger) == len(results)
    return rows, ledger, candidates, boundary


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--adj', type=Path, default=NOTES / 'jev-adj-all.json')
    ap.add_argument('--events', type=Path, default=NOTES / 'dv-june-new.json')
    # --workbook is the legacy reference for reference_reconciliation only
    # (every ref is INSUFFICIENT EVIDENCE by construction). It points at the
    # retired v1 workbook kept for lineage; the ruled reference is the
    # adjudicated batch served via /matrix provenance=adjudicated.
    ap.add_argument('--workbook', type=Path,
                    default=HERE / 'ingested/matrix/_retired-v1/June2026.json')
    ap.add_argument('--pdf-dir', type=Path, help='Optional exact PDF root; never searches arbitrary paths')
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--ledger', required=True, type=Path)
    ap.add_argument('--timings', required=True, type=Path)
    a = ap.parse_args()
    run_id = 'repair-' + str(uuid.uuid4())
    for p in (a.out, a.ledger, a.timings):
        if p.resolve().is_relative_to(ROOT):
            raise SystemExit('repair outputs must be outside project; use explicit scratch paths')
    def load(path):
        with source_phase(path, a.timings, 'cached_json_parse', run_id,
                          'Hash + JSON decode only; no new model or PDF extraction'):
            return json.loads(path.read_text(encoding='utf-8'))
    adj, raw, wb = load(a.adj), load(a.events), load(a.workbook)
    by = {}
    for e in raw['events']:
        by.setdefault(tuple(e.get(k) for k in ('date', 'rig', 'well')), []).append(e)
    with source_phase(a.events, a.timings, 'cached_context_guard', run_id,
                      'Frozen context relation audit only; NOT source PDF verification'):
        def verify(s):
            # source paths must be simple filenames under the explicitly supplied root.
            if Path(s['source_file']).name != s['source_file']:
                return False
            source = a.pdf_dir / s['source_file']
            ok = verify_pdf_source(source, s['source_page'], s['quote'], a.timings, run_id)
            if ok:
                s.update(source_sha256=sha256(source), physical_page_verified=True)
            return ok
        rows, dispositions, candidates, boundary = consume(
            adj['results'], by, verify if a.pdf_dir else None)
    coverage = [{'source_file': p.get('file'), 'status': ('OCR_NEEDED' if p.get('file') == 'LMR06262026.pdf'
                 else 'HISTORICAL_TIMING_INCOMPLETE'), 'historical': p}
                for p in raw.get('per_file', [])]
    payload = {'schema_version': ja.SCHEMA_VERSION, 'acceptance': 'HOLD / UNACCEPTED',
               'scope': 'June report dates; event-date normalization unconfirmed',
               'row_count': len(rows), 'rows': rows, 'candidate_rows': candidates,
               'june_boundary_candidates': boundary, 'new_model_calls': 0}
    refs = [{'sno': w.get('sno'), 'excel_row': None,
             'excel_row_note': 'not retained by original ingestion; not inferred from Sno',
             'reference': w, 'disposition': 'INSUFFICIENT EVIDENCE',
             'reason': 'legacy cache invalid; no independently verified accepted row'} for w in wb['rows']]
    ledger = {'run_id': run_id, 'input_count': len(adj['results']),
              'inputs': {str(p): sha256(p) for p in (a.adj, a.events, a.workbook)},
              'dispositions': dict(Counter(x['disposition'] for x in dispositions)),
              'entries': dispositions, 'reference_reconciliation': refs,
              'coverage': coverage, 'held_out_calibration': 'NOT PERFORMED',
              'cache_verification': 'legacy unbound verify_absent INVALID; preserved unchanged',
              'acceptance': 'NOT June clearance; no source PDF bulk rescan or model replay'}
    for path, obj in ((a.out, payload), (a.ledger, ledger)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(obj, indent=1, allow_nan=False) + '\n', encoding='utf-8')
    print(json.dumps({'input_count': ledger['input_count'], 'dispositions': ledger['dispositions'],
                      'matrix_rows': len(rows), 'context_only_candidates': len(candidates),
                      'reference_rows': len(refs), 'new_model_calls': 0}))


if __name__ == '__main__':
    main()
