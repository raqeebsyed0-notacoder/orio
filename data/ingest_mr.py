"""Ingest one Morning Report PDF into dated rig/well index records.

Runtime ingestion (Phase 1): this replaces the old build-time-only path so the
plugin can carry many report days instead of one.

Block header shape (verified against June + Oct reports):
    Rig
    <rig>
    Well
    <well>

Record shape matches the existing mr_index.json contract and adds the two
fields multi-day storage needs: ``report_date`` and ``source_file``.

Usage:
    python3 ingest_mr.py <report.pdf> [--json OUT] [--quiet]

Library:
    from ingest_mr import ingest_pdf
    records = ingest_pdf(Path('LMR06012026.pdf'))
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import fitz  # PyMuPDF

BLOCK_RE = re.compile(
    r'\nRig\s*\n\s*([A-Z0-9\-]+)\s*\n[\s\n]*?Well\s*\n\s*([A-Z0-9\-?]+)\s*\n',
    re.I)
# Standby / maintenance rigs have no Well section; the header reads
#   "<RIG> @ <status> Limited Morning Report for <date>"
# and the index records their well as a literal '?'.
STANDBY_RE = re.compile(
    r'\n([A-Z0-9][A-Z0-9\-]{1,14}) @[^\n]{0,60}?Limited Morning Report for',
    re.I)
DATE_RE = re.compile(r'Limited Morning Report for (\d{2}/\d{2}/\d{4})', re.I)
FILENAME_DATE_RE = re.compile(r'LMR(\d{2})(\d{2})(\d{4})', re.I)

ORIO_RE = re.compile(r'\b(ORIO|INNOVEX)\b', re.I)
RIH_RE = re.compile(r'\bRIH\b', re.I)
LANDED_RE = re.compile(r'\b(LANDED|LAND(?:ING)?)\b', re.I)
# size tokens that carry market meaning in this workflow
SIZE_RE = re.compile(
    r'(18\.625|18-5/8|18 5/8|13\.375|13-3/8|13 3/8|9\.625|9-5/8|9 5/8)', re.I)


def report_date(pages: list[str], path: Path) -> str | None:
    """Prefer the date printed in the report; fall back to the filename."""
    for t in pages[:3]:
        m = DATE_RE.search(t)
        if m:
            mm, dd, yy = m.group(1).split('/')
            return '%s-%s-%s' % (yy, mm, dd)
    m = FILENAME_DATE_RE.search(path.name)
    if m:
        mm, dd, yy = m.group(1), m.group(2), m.group(3)
        return '%s-%s-%s' % (yy, mm, dd)
    return None


def _section(text: str, label: str) -> str:
    """Pull the text following a 'Last 24 hr operations' style label."""
    m = re.search(re.escape(label) + r'\s*\n(.{0,900}?)(?:\n[A-Z][^\n]{0,60}\n|$)',
                  text, re.I | re.S)
    return re.sub(r'\s+', ' ', m.group(1)).strip() if m else ''


def ingest_pdf(path: Path) -> dict:
    """Return {'report_date', 'source_file', 'pdf_pages', 'records': [...]}."""
    doc = fitz.open(path)
    pages = [doc[i].get_text() for i in range(doc.page_count)]
    date = report_date(pages, path)

    spans = []
    for pno, t in enumerate(pages):
        for m in BLOCK_RE.finditer(t):
            spans.append((m.group(1).strip().upper(),
                          m.group(2).strip().upper(), pno, m.end()))
    # Standby / maintenance rigs carry no Well section; their header reads
    # "<RIG> @ <status> Limited Morning Report for <date>" and the index
    # records the well as a literal '?'. Keep those only for rigs that have
    # no real well anywhere in this report (every active rig repeats the
    # same header line, so an unfiltered match would duplicate all of them).
    real_well_rigs = {s[0] for s in spans}
    for pno, t in enumerate(pages):
        for m in STANDBY_RE.finditer(t):
            rig = m.group(1).strip().upper()
            if rig not in real_well_rigs:
                spans.append((rig, '?', pno, m.end()))
    # de-duplicate (rig, well) keeping the earliest page, in page order
    seen = set()
    ordered = []
    for s in sorted(spans, key=lambda x: (x[2], x[3])):
        key = (s[0], s[1])
        if key not in seen:
            seen.add(key)
            ordered.append(s)
    spans = ordered

    records = []
    for i, (rig, well, pno, start) in enumerate(spans):
        end_page = spans[i + 1][2] if i + 1 < len(spans) else len(pages) - 1
        chunk = pages[pno][start:]
        for p in range(pno + 1, min(end_page + 1, len(pages))):
            chunk += '\n' + pages[p]
        chunk = chunk[:40000]
        last24 = _section(chunk, 'Last 24 hr operations')
        next24 = _section(chunk, 'Next 24 hr plan')
        records.append({
            'rig': rig,
            'well': well,
            'report_date': date,
            'source_file': path.name,
            'first_page': pno + 1,
            'pages': max(1, end_page - pno + 1),
            'last24': last24,
            'next24': next24,
            'chars': len(chunk),
            'has_orio': bool(ORIO_RE.search(chunk)),
            'has_rih': bool(RIH_RE.search(chunk)),
            'has_landed': bool(LANDED_RE.search(chunk)),
            'has_size': bool(SIZE_RE.search(chunk)),
        })
    doc.close()
    return {'report_date': date, 'source_file': path.name,
            'pdf_pages': len(pages), 'records': records}


def main() -> None:
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if not args:
        print('usage: python3 ingest_mr.py <report.pdf> [--json OUT]')
        raise SystemExit(2)
    path = Path(args[0])
    out = ingest_pdf(path)
    print('file        :', out['source_file'])
    print('report_date :', out['report_date'])
    print('pdf_pages   :', out['pdf_pages'])
    print('blocks      :', len(out['records']))
    if '--json' in sys.argv:
        dest = Path(sys.argv[sys.argv.index('--json') + 1])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(json.dumps(out, indent=1))
        print('wrote       :', dest)


if __name__ == '__main__':
    main()
