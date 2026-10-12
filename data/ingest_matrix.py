"""Ingest a competitor-matrix workbook (Ajeez's hand-built monthly sheet).

Sheet1 columns (verified against the June workbook):
    1 Sno. | 2 Date RIH | 3 Rig | 4 Well | 5 Size | 6 Company | 7 Special Remarks

Produces matrix rows with page lineage left EMPTY here: this ingester only
reads Ajeez's own workbook. Page lineage is attached by the MR extraction
path (see june_matrix.py) so a row can always be traced to the report page
it came from.

Usage:
    python3 ingest_matrix.py <matrix.xlsx> [--json OUT]
"""
from __future__ import annotations

import datetime as dt
import json
import sys
from collections import Counter
from pathlib import Path

import openpyxl


def _date(v) -> str | None:
    if v is None:
        return None
    if isinstance(v, dt.datetime):
        return v.strftime('%Y-%m-%d')
    if isinstance(v, dt.date):
        return v.strftime('%Y-%m-%d')
    s = str(v).strip()
    return s[:10] if s else None


def _txt(v) -> str | None:
    if v is None:
        return None
    s = str(v).strip()
    return s or None


def ingest_matrix(path: Path) -> dict:
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb.active
    rows = []
    for r in ws.iter_rows(min_row=2, values_only=True):
        if r[0] is None or r[1] is None:
            continue
        size = r[4]
        try:
            size = ('%g' % float(size)) if size is not None else None
        except (TypeError, ValueError):
            size = _txt(size)
        rows.append({
            'sno': _txt(r[0]),
            'date': _date(r[1]),
            'rig': (_txt(r[2]) or '').upper(),
            'well': (_txt(r[3]) or '').upper(),
            'size': size,
            'company': (_txt(r[5]) or '').upper(),
            'remarks': _txt(r[6]) if len(r) > 6 else None,
            'source_file': path.name,
            'source_page': None,   # attached by the MR extraction path
        })
    wb.close()
    return {
        'source_file': path.name,
        'row_count': len(rows),
        'sizes': dict(Counter(r['size'] for r in rows)),
        'companies': dict(Counter(r['company'] for r in rows)),
        'months': dict(Counter((r['date'] or '')[:7] for r in rows)),
        'rows': rows,
    }


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print('usage: python3 ingest_matrix.py <matrix.xlsx> [--json OUT]')
        raise SystemExit(2)
    out = ingest_matrix(Path(args[0]))
    print('file      :', out['source_file'])
    print('rows      :', out['row_count'])
    print('sizes     :', out['sizes'])
    print('companies :', out['companies'])
    print('months    :', out['months'])
    if '--json' in sys.argv:
        dest = Path(sys.argv[sys.argv.index('--json') + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=1))
        print('wrote     :', dest)


if __name__ == '__main__':
    main()
