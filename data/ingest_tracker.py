"""Ingest the ORIO tracker workbook into dated tracker rows.

One sheet per report day (sheet names like 'Oct 12', 'Oct 11', 'June 24').
Header row 1; data from row 2. Columns (verified against the Oct-12 workbook):

    1 Sno. | 2 DRSS # orio | 3 MDD | 4 Rig | 5 Well | 6 Qty | 7 Cal done
    8 Ship date | 9 RIH date | 10 RIH time | 11 L Date | 12 L Time | 13 Op hrs
    14 MDD signed | 15 Rig Activity | 16 Current well ...

Dates arrive as datetime, times as datetime OR time; some cells hold Excel
formulas (=((K3+L3)-(I3...)) — those are never evaluated here, only recorded
as present. Missing stays missing.

Usage:
    python3 ingest_tracker.py <workbook.xlsx> [--json OUT]
"""
from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path

import openpyxl

MONTHS = {'jan': 1, 'feb': 2, 'mar': 3, 'apr': 4, 'may': 5, 'jun': 6,
          'jul': 7, 'aug': 8, 'sep': 9, 'oct': 10, 'nov': 11, 'dec': 12}
SHEET_DATE_RE = re.compile(r'([A-Za-z]{3,9})\s*(\d{1,2})', re.I)


def _val(v) -> str | None:
    """Cell -> plain string. Formulas are recorded as their text, never run."""
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, dt.time):
        return v.strftime('%H:%M')
    if isinstance(v, dt.date):
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    return s or None


def sheet_date(name: str, fallback_year: int) -> str | None:
    """'Oct 12' -> '2026-10-12'. Returns None for non-day sheets."""
    m = SHEET_DATE_RE.fullmatch(name.strip())
    if not m:
        return None
    mon = MONTHS.get(m.group(1)[:3].lower())
    if not mon:
        return None
    return '%04d-%02d-%02d' % (fallback_year, mon, int(m.group(2)))


def ingest_workbook(path: Path, year: int = 2026) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True, data_only=False)
    out_sheets, skipped = [], []
    for name in wb.sheetnames:
        sdate = sheet_date(name, year)
        if sdate is None:
            skipped.append(name)
            continue
        ws = wb[name]
        rows = []
        for r in ws.iter_rows(min_row=2, values_only=True):
            if all(c is None for c in r[:13]):
                continue
            rig = _val(r[3])
            well = _val(r[4])
            if not rig and not well:
                continue
            rows.append({
                'report_date': sdate,
                'sheet': name,
                'sno': _val(r[0]),
                'drss': _val(r[1]),
                'mdd': _val(r[2]),
                'rig': (rig or '').upper(),
                'well': (well or '').upper(),
                'qty': _val(r[5]),
                'cal_done': _val(r[6]),
                'ship_date': _val(r[7]),
                'rih_date': _val(r[8]),
                'rih_time': _val(r[9]),
                'l_date': _val(r[10]),
                'l_time': _val(r[11]),
                'op_hrs': _val(r[12]),
                'mdd_signed': _val(r[13]) if len(r) > 13 else None,
                'rig_activity': _val(r[14]) if len(r) > 14 else None,
                'current_well': _val(r[15]) if len(r) > 15 else None,
            })
        out_sheets.append({'report_date': sdate, 'sheet': name,
                           'rows': rows})
    wb.close()
    return {'source_file': path.name, 'sheets': out_sheets,
            'skipped_sheets': skipped}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print('usage: python3 ingest_tracker.py <workbook.xlsx> [--json OUT]')
        raise SystemExit(2)
    out = ingest_workbook(Path(args[0]))
    total = sum(len(s['rows']) for s in out['sheets'])
    print('file        :', out['source_file'])
    print('day sheets  :', len(out['sheets']))
    print('tracker rows:', total)
    print('skipped     :', out['skipped_sheets'])
    for s in out['sheets'][-3:]:
        print('   %-10s %s -> %d rows' % (s['sheet'], s['report_date'],
                                          len(s['rows'])))
    if '--json' in sys.argv:
        dest = Path(sys.argv[sys.argv.index('--json') + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=1))
        print('wrote       :', dest)


if __name__ == '__main__':
    main()
