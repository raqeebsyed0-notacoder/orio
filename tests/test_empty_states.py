"""F1/F2 regression: empty-state dead-ends + React key warnings (t_57a9f5a3).

Source-level: the five LoadGate-empty traps (Today, Rigs, Market Intel x2,
Exceptions) plus the Actions sibling must keep their filter chrome mounted
and render FilterEmpty inside the content area only, with a Clear action
that resets ALL view-local filter state (incl. persisted keys). No
`key`-in-props may remain in the touched views (React 19 dev-build
key-spread warnings); static child arrays go through jsxs().

API-level: pins the seed facts that make F1d/F1e real (extracted x COUNTED
is a legitimate zero-total combo; 0 resolved exceptions on seed) and the
non-empty bases the trap scenarios filter down from.

Runs against a THROWAWAY database, never the installed demo DB:
  <venv python> -m pytest tests/test_empty_states.py -q
"""
import os
import re
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

SRC = (PKG / 'desktop' / 'plugin.js').read_text(encoding='utf-8')

TOUCHED = ['FilterEmpty', 'Donut', 'SnapshotRail', 'TodayView', 'ActionsView',
           'RigsView', 'ExceptionCard', 'ExceptionsView', 'MarketIntelView',
           'THead', 'LoadGate']
TRAP_VIEWS = ['TodayView', 'ActionsView', 'RigsView', 'ExceptionsView',
              'MarketIntelView']


def fn_body(name):
    start = SRC.index('function ' + name)
    starts = [m.start() for m in re.finditer(r'^function ', SRC, re.M)]
    end = min([x for x in starts if x > start] or [len(SRC)])
    return SRC[start:end]


@pytest.fixture(scope='module')
def client():
    # Same discipline as test_api.py: claim a private home at fixture time
    # so whole-dir runs never share a DB between suites.
    os.environ['HERMES_HOME'] = tempfile.mkdtemp(prefix='orio-test-empty-home-')
    build_db.main()
    app = FastAPI()
    app.include_router(plugin_api.router, prefix='/api/plugins/euphoria-orio-operations')
    return TestClient(app)


def test_filter_empty_component_exists():
    assert 'function FilterEmpty' in SRC
    body = fn_body('FilterEmpty')
    assert 'Clear filters' in body  # default clear label
    assert 'onClear' in body  # null-safe: no button when nothing to clear


def test_trap_views_render_empty_inline_with_clear():
    for view in TRAP_VIEWS:
        body = fn_body(view)
        assert 'FilterEmpty' in body, view
        assert 'empty: q.data' not in body, view + ' still drops chrome via LoadGate empty'
        assert 'clearAll' in body, view + ' has no clear-all recovery'
        assert 'onClear' in body, view + ' never wires the clear action'


def test_empty_copy_names_controls_on_screen():
    assert 'search field or the priority filter above' in fn_body('TodayView')
    assert 'snapshot rail' in fn_body('ActionsView')
    assert 'search field or the stage rail' in fn_body('RigsView')
    assert 'snapshot rail' in fn_body('ExceptionsView')
    assert 'filters above' in fn_body('MarketIntelView')


def test_rigs_clear_wipes_persisted_query():
    body = fn_body('RigsView')
    assert "storageSet('rigq', '')" in body  # the session-sticky brick (F1a) cannot recur
    assert "storageGet('rigq', '')" in body  # initializer still reads the persisted key


def test_mi_clear_resets_all_nine_filters():
    body = fn_body('MarketIntelView')
    for frag in ["setStart('')", "setEnd('')", "setFSize('')", "setFCo('')",
                 "setFProv('')", "setFStatus('COUNTED')", "setFLoc('')",
                 "setFBasis('report')", "setFText('')", 'setPage(0)', 'setSelRow(null)']:
        assert frag in body, frag


def test_f2_no_spread_keys_in_touched_views():
    for view in TOUCHED:
        keys = re.findall(r'(?<![\w-])key\s*:', fn_body(view))
        assert keys == [], view + ' still passes key inside jsx() props'


def test_f2_static_arrays_use_jsxs():
    # The two flagged "unique key" sites (MarketIntelView render method).
    assert "}, 'lc')" in SRC  # sum-leader strong in a mixed static array
    assert "String(extrN) }, 'e')" in SRC  # provenance-strip strongs


def test_f1d_legitimate_combo_is_empty_at_api(client):
    r = client.get('/api/plugins/euphoria-orio-operations/matrix?provenance=extracted&status=COUNTED')
    assert r.json()['total'] == 0  # flagship view must survive this, not dead-end
    base = client.get('/api/plugins/euphoria-orio-operations/matrix?provenance=adjudicated&status=COUNTED')
    assert base.json()['total'] == 123  # same view, default selection is non-empty


def test_f1e_seed_has_zero_resolved(client):
    xs = client.get('/api/plugins/euphoria-orio-operations/exceptions').json()['exceptions']
    assert sum(1 for x in xs if x['state'] == 'open') == 6
    assert sum(1 for x in xs if x['state'] == 'resolved') == 0  # Resolved rail self-traps on seed


def test_trap_preconditions_nonempty(client):
    assert len(client.get('/api/plugins/euphoria-orio-operations/today').json()['items']) == 6
    assert client.get('/api/plugins/euphoria-orio-operations/rigs?limit=1').json()['total'] == 280
