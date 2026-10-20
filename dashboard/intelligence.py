"""LANE 7 — Intelligence enhancements 1-4 (read-only range views over VERIFIED June data).

Every view reads the frozen Lane-4 / Lane-2 registers and the confirmed
company-alias map. This module:

- opens no sockets, sends nothing, writes nothing (pure functions);
- never invents forecasts, revenue, lost-sales, substitutions, or findings;
- labels each outcome honestly: implemented-on-real-evidence |
  fixture-only | lacking-source;
- keeps planned vs completed/postponed/cancelled/unconfirmed distinct —
  outcome states with no source support are reported as unsupported,
  never as data;
- words supplier first-sightings as "first observed in covered reports"
  with the coverage window stated on every row;
- links a tool problem to a supplier ONLY when the source text connects it;
- never ranks supplier reliability;
- preserves reviewer-correction originals beside proposals (history is
  never overwritten) and reports effort metrics as observed.

Source registers (frozen, read-only — never edited here):
  06_Working-Notes/dv-june-adjudicated.json              (691 day-events, Jun-Aug)
  06_Working-Notes/reviews/june-closeout-2026-10-19/
      lane4-reconciliation-round2.json                   (131 rows: 88/11/32/3/7)
      lane4-accepted-corrected.json / lane4-provisional-corrected.json
      lane4-timing-ledger.json
  06_Working-Notes/reviews/june-ocr-coverage-2026-10-19/coverage-ledger.json
  data/company_aliases.json                              (confirmed display map)
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# ---------------------------------------------------------------- roots

_PLUGIN_DIR = Path(__file__).resolve().parent          # .../orio-operations-plugin/dashboard
_PLUGIN_ROOT = _PLUGIN_DIR.parent                       # .../orio-operations-plugin
_PROJECT_ROOT = _PLUGIN_ROOT.parent                     # .../Innovex (ajeez)
_NOTES = _PROJECT_ROOT / '06_Working-Notes'
_CLOSEOUT = _NOTES / 'reviews' / 'june-closeout-2026-10-19'
_COVERAGE_LEDGER = (_NOTES / 'reviews' / 'june-ocr-coverage-2026-10-19'
                    / 'coverage-ledger.json')
_ADJUDICATED = _NOTES / 'dv-june-adjudicated.json'
_RECONCILIATION = _CLOSEOUT / 'lane4-reconciliation-round2.json'
_TIMING_LEDGER = _CLOSEOUT / 'lane4-timing-ledger.json'
_ALIASES = _PLUGIN_ROOT / 'data' / 'company_aliases.json'
_QUESTIONS = _PLUGIN_ROOT / 'data' / 'intelligence_questions.json'

JUNE_START = '2026-06-01'
JUNE_END = '2026-06-30'
COVERAGE_LABEL = ('June LMR set 2026-06-01..2026-06-30 '
                  '(adjudicated day-events + Lane-4 reconciliation vs '
                  'the 131-row clean reference)')


def _load(path: Path):
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def file_sha_map(reconciliation: dict) -> dict[str, str]:
    """Source file name -> sha256, from reconciliation support entries."""
    out: dict[str, str] = {}
    for section in ('matched', 'conflicting', 'missing_evidence',
                    'proposed_correction'):
        for row in reconciliation.get(section, []):
            sup = row.get('support') or {}
            if sup.get('file') and sup.get('sha256'):
                out.setdefault(sup['file'], sup['sha256'])
    return out


def june_events(adjudicated: dict) -> list[dict]:
    """June CONFIRMED/REVIEW day-events (the VERIFIED working set)."""
    return [e for e in adjudicated.get('events', [])
            if (e.get('date') or '')[:10] >= JUNE_START
            and (e.get('date') or '')[:10] <= JUNE_END
            and e.get('verdict') in ('CONFIRMED', 'REVIEW')]


# ------------------------------------------------------------- feature 1

# Explicit forward-plan markers only — past-tense operational prose and
# recap/summary contexts never qualify.
_PLAN_RES = [
    re.compile(r'next\s+\d*\s*(hr|hour|day)[s]?\s*(operations?|plan)?', re.I),
    re.compile(r'\bupcoming\b', re.I),
    re.compile(r'\bwill\s+(run|rih|m/u|p/u|r/u|pooh)\b', re.I),
    re.compile(r'\bto\s+be\s+(run|performed|rih)\b', re.I),
    re.compile(r'\bplan\s*[:\-]\s*\S', re.I),
    re.compile(r'\bas\s+per\s+program\b', re.I),
]

# Outcome vocabulary. Only PLANNED_EXPLICIT and UNCONFIRMED have source
# support; the rest are listed so callers can see what is NOT supported.
OUTCOME_VOCABULARY = {
    'PLANNED_EXPLICIT': 'explicit forward-plan wording in the source report',
    'UNCONFIRMED': 'no outcome wording found in covered reports',
    'COMPLETED': 'NOT SUPPORTED BY SOURCE — no completion wording tracked',
    'POSTPONED': 'NOT SUPPORTED BY SOURCE — no postponement wording tracked',
    'CANCELLED': 'NOT SUPPORTED BY SOURCE — no cancellation wording tracked',
}

_RETROSPECTIVE_NOTE = ('RETROSPECTIVE QA (later evidence, never back-projected '
                       'into the as-of-date state per AGENTS.md §C).')


def _plan_quote(context: str) -> str | None:
    for rx in _PLAN_RES:
        m = rx.search(context or '')
        if m:
            s = max(0, m.start() - 160)
            return re.sub(r'\s+', ' ',
                          context[s:m.end() + 200]).strip()[:500]
    return None


def upcoming_plans(adjudicated: dict, reconciliation: dict,
                   as_of: str = JUNE_END,
                   with_retrospective: bool = True) -> dict:
    """Explicit upcoming-job plans visible as of a date (historical view).

    ``as_of`` filters to plans dated <= as_of. Every item carries outcome
    UNCONFIRMED unless a same-rig+well later report inside covered June
    reports mentions the job again — attached as labelled retrospective,
    never merged into the as-of-date state.
    """
    shas = file_sha_map(reconciliation)
    events = [e for e in june_events(adjudicated)
              if (e.get('date') or '') <= as_of]
    covered = june_events(adjudicated)
    items = []
    for e in events:
        quote = _plan_quote(e.get('context') or '')
        if not quote:
            continue
        item = {
            'date': e.get('date'), 'rig': e.get('rig'),
            'well': e.get('well'), 'size': e.get('size'),
            'owner': e.get('owner'),
            'company_display': e.get('company_display'),
            'plan_quote': quote,
            'outcome': 'UNCONFIRMED',
            'outcome_note': OUTCOME_VOCABULARY['UNCONFIRMED'],
            'evidence': {
                'register': 'dv-june-adjudicated.json',
                'source_file': e.get('source_file'),
                'sha256': shas.get(e.get('source_file') or ''),
                'source_page': e.get('source_page'),
                'verdict': e.get('verdict'),
            },
            'retrospective': None,
        }
        if with_retrospective:
            for f in covered:
                if (f.get('rig') == e.get('rig')
                        and f.get('well') == e.get('well')
                        and (f.get('date') or '') > (e.get('date') or '')):
                    item['retrospective'] = {
                        'note': _RETROSPECTIVE_NOTE,
                        'date': f.get('date'),
                        'owner': f.get('owner'),
                        'company_display': f.get('company_display'),
                        'context_excerpt': re.sub(
                            r'\s+', ' ',
                            (f.get('context') or '')[:400]).strip(),
                        'evidence': {
                            'register': 'dv-june-adjudicated.json',
                            'source_file': f.get('source_file'),
                            'sha256': shas.get(f.get('source_file') or ''),
                            'source_page': f.get('source_page'),
                            'verdict': f.get('verdict'),
                        },
                    }
                    break
        items.append(item)
    items.sort(key=lambda i: (i['date'] or '', i['rig'] or ''))
    return {
        'feature': 'upcoming-jobs-from-explicit-plans',
        'evidence_status': 'implemented-on-real-evidence',
        'as_of': as_of,
        'coverage': COVERAGE_LABEL,
        'outcome_vocabulary': OUTCOME_VOCABULARY,
        'unsupported_outcomes': ['COMPLETED', 'POSTPONED', 'CANCELLED'],
        'items': items,
        'negative_cases': [
            'recap/summary contexts (e.g. July-1 SINO-46L recap-level hit) '
            'never qualify as plans',
            'past-tense operational prose without a forward marker never '
            'qualifies',
            'non-June reports are outside the covered range',
        ],
    }


# ------------------------------------------------------------- feature 2

def first_seen_suppliers(adjudicated: dict) -> dict:
    """First supplier appearances + repeat use within covered June reports."""
    norm: dict[str, dict] = {}
    for e in june_events(adjudicated):
        owner = e.get('owner')
        if not owner or owner == 'UNKNOWN':
            continue
        slot = norm.setdefault(owner, {
            'supplier_code': owner,
            'first_observed_date': None,
            'first_observed': None,
            'observations': 0,
            'rigs': set(),
            'wells': set(),
        })
        slot['observations'] += 1
        slot['rigs'].add(e.get('rig'))
        slot['wells'].add(e.get('well'))
        if (slot['first_observed_date'] is None
                or (e.get('date') or '') < slot['first_observed_date']):
            slot['first_observed_date'] = e.get('date')
            slot['first_observed'] = {
                'date': e.get('date'), 'rig': e.get('rig'),
                'well': e.get('well'),
                'company_display': e.get('company_display'),
                'source_file': e.get('source_file'),
                'source_page': e.get('source_page'),
                'verdict': e.get('verdict'),
                'context_excerpt': re.sub(
                    r'\s+', ' ', (e.get('context') or '')[:300]).strip(),
            }
    try:
        aliases = _load(_ALIASES)
        amap = aliases.get('mapping', {})
        display = {k: v.get('display', k) for k, v in amap.items()}
        # Report-alias spellings resolve to their canonical display
        # (e.g. SLB -> SCHLUMBERGER (KSV)); the observed code is kept.
        for k, v in amap.items():
            for a in v.get('report_aliases', []) or []:
                display.setdefault(a, v.get('display', k))
    except OSError:
        display = {}
    rows = []
    for code in sorted(norm):
        slot = norm[code]
        rows.append({
            'supplier_code': code,
            'supplier_display': display.get(code, code),
            'wording': ('first observed in covered reports: '
                        + str(slot['first_observed_date'])),
            'first_observed': slot['first_observed'],
            'repeat_use': {
                'observations': slot['observations'],
                'distinct_rigs': len(slot['rigs']),
                'distinct_wells': len(slot['wells']),
            },
            'coverage': COVERAGE_LABEL,
        })
    return {
        'feature': 'first-supplier-appearances-plus-repeat-use',
        'evidence_status': 'implemented-on-real-evidence',
        'coverage': COVERAGE_LABEL,
        'filters': 'June CONFIRMED/REVIEW day-events; UNKNOWN owner excluded',
        'suppliers': rows,
        'negative_cases': [
            'UNKNOWN owner (255 full-corpus events) excluded, never assigned',
            'OCR-noise spellings (WED/HALIB) flagged at source, never '
            'normalized silently',
            'July/August sightings excluded from June first-observed claims',
        ],
    }


# ------------------------------------------------------------- feature 3

# Explicit DV-tool problem wording. Rig-equipment failures (power unit,
# pumps) and casing-test failures without a tool link never qualify.
_TOOL_PROBLEM_RES = [
    re.compile(r'shut\s+off\s+plug\s+stuck', re.I),
    re.compile(r'unable\s+to\s+close\s+\S*\s*dv\s+tool', re.I),
    re.compile(r'(deformation|damage)\s+(on|to)\s+\S*\s*dv\s+(packer|tool|element)', re.I),
    re.compile(r'fail\w*\s+of\s+the\s+dv\s+tool\s+plugs?', re.I),
    re.compile(r'found\s+deformation\s+and\s+damage\s+on\s+dv', re.I),
    re.compile(r'damaged\s+\S+\s+below\s+dv\b', re.I),
]

_SUPPLIER_LINK_RES = [
    re.compile(r'\bTF\s+FOT\s+DV\s+(FET|HAL|WFD|TAM|SLB|KSV)\b'),
    re.compile(r'\bL/D\s+(HAL|WFD|FET|TAM|SLB)\b[^.]{0,60}\bDV\s+TOOL\b'),
    re.compile(r'\bM/U\s+(WFD|HAL|FET|TAM|SLB)\b[^.]{0,60}\bDV\b'),
    re.compile(r'\bDV\s+(FET|HAL|WFD|TAM|SLB)\b'),
]


def _problem_quote(context: str) -> str | None:
    for rx in _TOOL_PROBLEM_RES:
        m = rx.search(context or '')
        if m:
            s = max(0, m.start() - 200)
            return re.sub(r'\s+', ' ',
                          context[s:m.end() + 200]).strip()[:700]
    return None


def _supplier_link(context: str) -> str | None:
    for rx in _SUPPLIER_LINK_RES:
        m = rx.search(context or '')
        if m:
            for g in m.groups():
                if g:
                    return g
    return None


def tool_problems(adjudicated: dict, reconciliation: dict) -> dict:
    """Explicitly reported DV-tool problems + resolution state.

    A supplier is linked ONLY when the source text connects it. Resolution
    is reported only with explicit wording; otherwise the item states
    resolution_not_reported_in_covered_reports. No reliability ranking —
    the view carries none and the schema has no field for one.
    """
    shas = file_sha_map(reconciliation)
    # Any June verdict: a NOT_A_RUN row can still carry explicit problem
    # wording (shown with its verdict, never upgraded).
    events = [e for e in adjudicated.get('events', [])
              if (e.get('date') or '')[:10] >= JUNE_START
              and (e.get('date') or '')[:10] <= JUNE_END
              and (e.get('context') or '').strip()]
    items = []
    for e in events:
        quote = _problem_quote(e.get('context') or '')
        if not quote:
            continue
        linked = _supplier_link(e.get('context') or '')
        resolution = None
        for f in events:
            if (f.get('rig') == e.get('rig')
                    and f.get('well') == e.get('well')
                    and (f.get('date') or '') > (e.get('date') or '')):
                ctx = f.get('context') or ''
                if re.search(r'resolv|rectif|repaired|replaced|re-?run|'
                             r'successfully|normali[sz]ed', ctx, re.I):
                    resolution = {
                        'date': f.get('date'),
                        'excerpt': re.sub(r'\s+', ' ', ctx[:300]).strip(),
                        'source_file': f.get('source_file'),
                        'source_page': f.get('source_page'),
                    }
                    break
        items.append({
            'date': e.get('date'), 'rig': e.get('rig'),
            'well': e.get('well'),
            'problem_quote': quote,
            'supplier_linked': linked,
            'supplier_link_note': ('linked from source wording'
                                   if linked else
                                   'no supplier named in the problem '
                                   'wording — left unlinked'),
            'size': e.get('size'),
            'evidence': {
                'register': 'dv-june-adjudicated.json',
                'source_file': e.get('source_file'),
                'sha256': shas.get(e.get('source_file') or ''),
                'source_page': e.get('source_page'),
                'verdict': e.get('verdict'),
            },
            'resolution': (resolution if resolution else {
                'status': 'resolution_not_reported_in_covered_reports'}),
        })
    items.sort(key=lambda i: (i['date'] or '', i['rig'] or ''))
    return {
        'feature': 'explicit-tool-problems-plus-resolution',
        'evidence_status': 'implemented-on-real-evidence',
        'coverage': COVERAGE_LABEL,
        'reliability_ranking': 'NONE — forbidden; this view carries no '
                               'ranking field',
        'items': items,
        'negative_cases': [
            'ADC-16 2026-06-10 power-unit malfunction excluded (rig '
            'equipment, not DV tool)',
            'July NBR-16S DV-plug failure excluded (outside June coverage)',
            'problems never auto-linked to the row owner — only to a '
            'supplier the wording names',
        ],
    }


# ------------------------------------------------------------- feature 4

def reviewer_corrections(reconciliation: dict, aliases: dict,
                         timing: dict) -> dict:
    """Reviewer correction flow: proposals with originals, alias-rule reuse,
    effort-falling metrics. Proposals are human-review-only, never applied.
    """
    corrections = []
    for row in reconciliation.get('proposed_correction', []):
        sup = row.get('support') or {}
        corrections.append({
            'sno': row.get('sno'), 'excel_row': row.get('excel_row'),
            'rig': row.get('rig'), 'well': row.get('well'),
            'date_rih': row.get('date_rih'),
            'original_workbook': {
                'size': row.get('size'), 'company': row.get('company')},
            'observed_evidence': {
                'observed_size': sup.get('observed_size'),
                'observed_company': sup.get('observed_company'),
                'jev_choice': sup.get('jev_choice'),
                'verdict': sup.get('verdict'),
                'date_relation': sup.get('date_relation'),
                'delta_days': sup.get('delta_days'),
                'source_file': sup.get('file'),
                'sha256': sup.get('sha256'),
                'source_page': sup.get('page'),
                'report_date': sup.get('report_date'),
            },
            'mismatch_fields': row.get('mismatch_fields'),
            'status': row.get('proposed_status',
                              'proposed-human-review (never auto-applied)'),
            'history_preserved': True,
        })
    conflicting = []
    for row in reconciliation.get('conflicting', []):
        sup = row.get('support') or {}
        conflicting.append({
            'sno': row.get('sno'), 'rig': row.get('rig'),
            'well': row.get('well'), 'date_rih': row.get('date_rih'),
            'mismatch_fields': row.get('mismatch_fields'),
            'workbook': {'size': row.get('size'),
                         'company': row.get('company')},
            'observed': {'size': sup.get('observed_size'),
                         'company': sup.get('observed_company'),
                         'jev_choice': sup.get('jev_choice'),
                         'verdict': sup.get('verdict'),
                         'source_file': sup.get('file'),
                         'source_page': sup.get('page')},
            'status': 'conflicting — human review only, never auto-applied',
            'history_preserved': True,
        })
    mapping = (aliases.get('mapping') or {})
    alias_rules = [{
        'code': code,
        'display': spec.get('display'),
        'report_aliases': spec.get('report_aliases', []),
        'evidence': spec.get('evidence'),
        'status': spec.get('status'),
    } for code, spec in sorted(mapping.items())]
    counts = reconciliation.get('counts', {})
    totals = (timing.get('totals') or {}) if isinstance(timing, dict) else {}
    verdict = (timing.get('verdict') or {}) if isinstance(timing, dict) else {}
    effort = {
        'source': 'lane4-timing-ledger.json (observed, Lane-4 measured)',
        'june_26_increment_s': totals.get('june26_increment_wall_s'),
        'june_26_verdict': verdict.get('june26_increment'),
        'full_corpus_s': totals.get('full_corpus_wall_s'),
        'full_corpus_verdict': verdict.get('full_corpus'),
        'coverage_note': verdict.get('coverage'),
        'accuracy_note': verdict.get('accuracy'),
        'jev_cost_note': 'Lane-4 live Jev: 10/10 clusters, $0.0021; '
                         'this lane adds $0.00 (no live model calls)',
    }
    return {
        'feature': 'reviewer-correction-flow',
        'evidence_status': 'implemented-on-real-evidence',
        'coverage': COVERAGE_LABEL,
        'proposed_corrections': corrections,
        'conflicting_rows': conflicting,
        'counts': counts,
        'alias_rules': alias_rules,
        'alias_reuse_tests': 'see tests/test_intelligence_lane7.py '
                             '(positive: DAVIS LYNCH->FET, HLB->HAL, '
                             'WFD->WEATHERFORD; negative: TAM never '
                             'expanded, bare short forms never display)',
        'effort_metrics': effort,
        'negative_cases': [
            'the recording’s "two human errors" stay unidentified — '
            'proposals are candidates, never identifications',
            'V76/V108 additional runs excluded (unverified block-header '
            'rig IDs)',
            'provisional_near matches excluded from correction candidacy '
            '(weak by construction)',
        ],
    }


# ------------------------------------------------------------- questions

def load_questions() -> dict:
    """Real ORIO questions with evidence links (banked, versioned)."""
    try:
        return _load(_QUESTIONS)
    except OSError:
        return {'questions': [], 'note': 'question bank not installed'}


def build_bundle(as_of: str = JUNE_END) -> dict:
    """All four range views + questions in one evidence bundle."""
    adjudicated = _load(_ADJUDICATED)
    reconciliation = _load(_RECONCILIATION)
    try:
        aliases = _load(_ALIASES)
    except OSError:
        aliases = {'mapping': {}}
    try:
        timing = _load(_TIMING_LEDGER)
    except OSError:
        timing = {}
    return {
        'lane': 'LANE-7',
        'scope': 'VERIFIED June data only; June accuracy first',
        'upcoming': upcoming_plans(adjudicated, reconciliation,
                                   as_of=as_of),
        'suppliers': first_seen_suppliers(adjudicated),
        'problems': tool_problems(adjudicated, reconciliation),
        'corrections': reviewer_corrections(reconciliation, aliases,
                                            timing),
        'questions': load_questions(),
    }
