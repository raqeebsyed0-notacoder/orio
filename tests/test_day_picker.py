"""FIX6 regression: Report-day picker must not use a native <select> (t_31edfb22).

The native popup renders in OS chrome (white bg, pale-grey options) --
illegible in the dark shell and invisible to DOM screenshots. The themed
DayPicker (button trigger + popover listbox, theme-var DOM) replaces it
with identical behavior: Latest = '' server default, value validated vs
/meta, $day + storage write on pick, stale-day reset untouched.

Runs against a THROWAWAY database, never the installed demo DB:
  <venv python> -m pytest tests/test_day_picker.py -q
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


def fn_body(name):
    start = SRC.index('function ' + name)
    starts = [m.start() for m in re.finditer(r'^function ', SRC, re.M)]
    end = min([x for x in starts if x > start] or [len(SRC)])
    return SRC[start:end]


@pytest.fixture(scope='module')
def client():
    os.environ['HERMES_HOME'] = tempfile.mkdtemp(prefix='orio-test-daypick-home-')
    build_db.main()
    app = FastAPI()
    app.include_router(plugin_api.router, prefix='/api/plugins/euphoria-orio-operations')
    return TestClient(app)


def test_no_native_select_for_report_day():
    # Strip block/line comments: the FIX6 rationale comments name the
    # removed element, so only code counts here.
    code = re.sub(r'/\*.*?\*/', '', SRC, flags=re.S)
    code = re.sub(r'^[ \t]*\*.*$', '', code, flags=re.M)
    # No jsx('select') / <select remains anywhere in code.
    assert "jsx('select'" not in code
    assert 'jsxs(\'select\'' not in code
    assert '<select' not in code
    # No option elements remain for the day list either.
    assert "jsx('option'" not in code
    assert 'jsxs(\'option\'' not in code
    assert '<option' not in code


def test_daypicker_component_exists_with_listbox_semantics():
    body = fn_body('DayPicker')
    assert 'listbox' in body
    assert 'aria-haspopup' in body
    assert 'aria-expanded' in body
    assert 'aria-selected' in body
    assert "role: 'option'" in body or 'role:"option"' in body or "role: 'option'" in body


def test_daypicker_interaction_handlers():
    body = fn_body('DayPicker')
    # open/close: click toggle, click-outside, Escape
    assert 'setOpen' in body
    assert 'mousedown' in body
    assert 'Escape' in body
    # keyboard: arrows move highlight, Enter commits
    assert 'ArrowDown' in body and 'ArrowUp' in body
    assert 'scrollIntoView' in body  # selected row visible on open


def test_daypicker_behavior_preserved():
    page = fn_body('OrioPage')
    # Latest-first option list with dayParam default preserved.
    assert 'DayPicker' in page
    assert 'dayParam' in page
    # Selecting still drives $day + persisted storage, validated vs /meta.
    assert "$day.set(v); storageSet('day', v)" in page
    assert 'days.includes(day)' in page
    # Trigger keeps the accessible name + explanatory title.
    daypick = fn_body('DayPicker')
    assert "'Report day'" in daypick
    assert 'drives the Today heading and the Rigs & Wells index' in daypick


def test_daypicker_contrast_uses_theme_vars_only():
    style_start = SRC.index('function ensureStyles()')
    style_end = SRC.index('/* Styling', style_start + 10) if '/* Styling' in SRC[style_start:] else len(SRC)
    css = SRC[style_start:style_end + 20000]
    for cls in ['-daytrig', '-daypop', '-dayopt']:
        assert cls in SRC
    pop = css[css.index('-daypop'):]
    pop = pop[:pop.index('}')]
    assert 'var(--ui-bg-elevated)' in pop
    assert 'var(--foreground)' in pop
    # No hardcoded hex colors in the day-picker rules.
    day_rules = css[css.index('-daytrig'):css.index('-daycheck') + 200]
    assert not re.search(r'#[0-9a-fA-F]{3,6}', day_rules)


def test_meta_still_serves_report_dates(client):
    met = client.get('/api/plugins/euphoria-orio-operations/meta').json()
    assert len(met['report_dates']) == 92
    assert met['report_dates'][0] == '2026-10-12'
