"""Offline repair regressions. Synthetic fixtures are NOT June acceptance."""
import copy
import csv
import io
import json
import os
from pathlib import Path
import shutil
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch
import urllib.error

PKG = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(PKG / 'data'), str(PKG / 'dashboard'), str(PKG.parent / '05_Architecture')]
import jev_consume as jc
import jev_adjudicate as ja
import jev_ask as ask
import build_db

OUT = Path(os.environ['ORIO_REPAIR_OUT']).resolve()
OUT.mkdir(parents=True, exist_ok=True)
os.environ['HERMES_HOME'] = str(OUT / 'isolated-home')
TMP = OUT / 'fixtures'
TMP.mkdir(exist_ok=True)


def event(context='M/U 13-3/8" WEATHERFORD DV TOOL & RIH SAME.', **kw):
    return dict(date='2026-06-01', rig='SYNTHETIC', well='SYNTHETIC-WELL',
                source_file='synthetic.pdf', source_page=1, size='13.375',
                owner='WFD', context=context, **kw)


def result(e=None, adopted=False):
    e = e or event()
    r = {k: e[k] for k in ('date', 'rig', 'well', 'size', 'source_file')}
    r.update(owner='WFD', code_owner='UNKNOWN' if adopted else 'WFD',
             verdict='ADOPTED' if adopted else 'CONFIRMED',
             jev={'choice': ja.DISPLAY['WFD'], 'confidence': .95, 'tool_run': .9,
                  'verify_absent': 0.0, 'supplier_support': ja.SUPPLIER_SUPPORT,
                  'model': 'jev-1.13.0'})
    r['cache'] = ja.cache_metadata(ja.make_state([e]), 'jev-1.13.0')
    return r


class Repair(unittest.TestCase):
    def test_probability_boundaries(self):
        self.assertTrue(ja.adopt_approved(.85, .6, .7))
        self.assertTrue(ja.adopt_approved(.9, .8, 0.0))
        for value in (None, True, False, -1, 1.01, float('nan'), float('inf'), '0.9'):
            for pos in range(3):
                args = [.9, .8, .1]
                args[pos] = value
                with self.subTest(value=str(value), position=pos):
                    self.assertFalse(ja.adopt_approved(*args))
        for args in ((.84,.8,.1),(.9,.59,.1),(.9,.8,.71)):
            self.assertFalse(ja.adopt_approved(*args))

    def test_explicit_independent_questions(self):
        self.assertNotIn('verify_absent', ja.QUESTIONS)
        for owner, aliases in ja.SUPPLIER_ALIASES.items():
            for alias in aliases:
                self.assertIn(alias, ja.QUESTIONS['absent_' + owner]['instructions'])
        ans = {'company': {'choice': ja.DISPLAY['WFD'], 'confidence': .95},
               'tool_run': {'noul': .9}, 'absent_WFD': {'noul': 0.0}}
        self.assertEqual(ja.route_answers(ans, 'UNKNOWN')[:2], ('ADOPTED', 'WFD'))
        del ans['absent_WFD']
        self.assertEqual(ja.route_answers(ans, 'UNKNOWN')[0], 'REVIEW')
        ans['absent_WFD'] = {'noul': -1}
        self.assertEqual(ja.route_answers(ans, 'UNKNOWN')[0], 'REVIEW')

    def test_nonrun_is_independent_of_supplier(self):
        ans = {'company': {'choice': 'NO-MATCH', 'confidence': .99},
               'tool_run': {'noul': .1}}
        self.assertEqual(ja.route_answers(ans, 'UNKNOWN')[:2], ('NOT_A_RUN', 'UNKNOWN'))
        self.assertEqual(ja.route_answers({'tool_run': {'noul': 0.0}}, 'WFD')[0], 'NOT_A_RUN')
        for value in (None, True, False, -1, 1.1, float('nan'), float('inf'), '0.1'):
            with self.subTest(invalid_run=str(value)):
                bad = dict(ans, tool_run={'noul': value})
                self.assertEqual(ja.route_answers(bad, 'UNKNOWN')[0], 'REVIEW')
        for value in ({}, None, [], {'tool_run': None}, {'tool_run': {}},
                      {'tool_run': {'noul': .4}}, {'tool_run': {'noul': .59}}):
            self.assertEqual(ja.route_answers(value, 'UNKNOWN')[0], 'REVIEW')
        good = {'company': {'choice': ja.DISPLAY['WFD'], 'confidence': .95},
                'tool_run': {'noul': .9}, 'absent_WFD': {'noul': 0.0}}
        for code, expected in (('UNKNOWN', 'ADOPTED'), ('WFD', 'CONFIRMED'), ('HAL', 'CONFLICT')):
            self.assertEqual(ja.route_answers(good, code)[0], expected)
        bad = dict(good, tool_run={'noul': None})
        self.assertEqual(ja.route_answers(bad, 'WFD')[0], 'REVIEW')

    def test_alias_bound_schema_invalidates_v2(self):
        for owner, aliases in ja.SUPPLIER_ALIASES.items():
            question = ja.QUESTIONS['absent_' + owner]
            for alias in aliases:
                self.assertIn(alias, question['instructions'])
                self.assertIn(alias, question['criteria']['false'])
        self.assertEqual(set(ja.SUPPLIER_ALIASES), {'WFD', 'HAL', 'FET', 'TAM'})
        self.assertEqual((ja.ADOPT_CHOICE_CONF, ja.ADOPT_TOOL_RUN,
                          ja.VERIFY_ABSENT_MAX, ja.NOT_A_RUN_BELOW), (.85, .6, .7, .4))
        r = result()
        old = copy.deepcopy(r)
        old['cache']['schema_version'] = 'dv-supplier-v2'
        self.assertFalse(jc.cache_valid(old, [event()]))
        old = copy.deepcopy(r)
        old['jev']['supplier_support'] = 'explicit-candidate-v2'
        self.assertFalse(jc.scores_valid(old))
        self.assertEqual(jc.consume([old], {('2026-06-01', 'SYNTHETIC', 'SYNTHETIC-WELL'): [event()]},
                                    lambda s: True)[0], [])

    def test_v4_alias_first_framing_and_legacy_invalidation(self):
        # v4 framing: the literal alias list leads each independent absence
        # question; the v3 display-string subject trap is removed. Thresholds
        # stay frozen; legacy v2/v3 scores are stale, never inverted. This is
        # an offline framing/version check only: NO live v4 semantic claim.
        self.assertEqual((ja.SCHEMA_VERSION, ja.STATE_VERSION,
                          ja.POLICY_VERSION, ja.SUPPLIER_SUPPORT),
                         ('dv-supplier-v4', 'full-spans-v4',
                          'june-source-guard-v4', 'explicit-alias-candidate-v4'))
        self.assertEqual((ja.ADOPT_CHOICE_CONF, ja.ADOPT_TOOL_RUN,
                          ja.VERIFY_ABSENT_MAX, ja.NOT_A_RUN_BELOW), (.85, .6, .7, .4))
        self.assertNotEqual(ja.QUESTION_HASH,
                            '477269e3f033b740c5dfa4b8dbccb4495cbf692d716ddcaeb1c479e487e4c246')
        for owner, aliases in ja.SUPPLIER_ALIASES.items():
            names = ', '.join(aliases)
            question = ja.QUESTIONS['absent_' + owner]
            self.assertTrue(question['instructions'].startswith(
                'Look for any of these supplier names in the operation text: ' + names + '.'),
                'alias list must lead, not the display string')
            for alias in aliases:
                self.assertIn(alias, question['instructions'])
                self.assertIn(alias, question['criteria']['true'])
                self.assertIn(alias, question['criteria']['false'])
        self.assertIn('not-yet-run', ja.QUESTIONS['tool_run']['criteria']['false'])
        e = event()
        for legacy_schema in ('dv-supplier-v2', 'dv-supplier-v3'):
            old = copy.deepcopy(result(e))
            old['cache']['schema_version'] = legacy_schema
            self.assertFalse(jc.cache_valid(old, [e]))
        for legacy_support in ('explicit-candidate-v2', 'explicit-candidate-v3'):
            old = copy.deepcopy(result(e))
            old['jev']['supplier_support'] = legacy_support
            self.assertFalse(jc.scores_valid(old))
        current = result(e)
        self.assertTrue(jc.cache_valid(current, [e]))
        self.assertTrue(jc.scores_valid(current))
        # Manually authored v4 answers (NOT live Jev): positive adoption works,
        # a missing absence answer stays REVIEW, valid nonrun stays independent.
        ans = {'company': {'choice': ja.DISPLAY['WFD'], 'confidence': .95},
               'tool_run': {'noul': .9}, 'absent_WFD': {'noul': 0.0}}
        self.assertEqual(ja.route_answers(ans, 'UNKNOWN')[:2], ('ADOPTED', 'WFD'))
        del ans['absent_WFD']
        self.assertEqual(ja.route_answers(ans, 'UNKNOWN')[0], 'REVIEW')
        self.assertEqual(ja.route_answers(
            {'company': {'choice': 'NO-MATCH', 'confidence': .99},
             'tool_run': {'noul': .1}}, 'UNKNOWN')[0], 'NOT_A_RUN')

    def test_parent_surface_negation_through_pdf_consumer_builder(self):
        import fitz
        negatives = [
            'M/U 13-3/8" WEATHERFORD DV TOOL ON SURFACE FOR FUNCTION TEST.',
            'M/U 13-3/8" WEATHERFORD DV TOOL; NOT YET RUN INTO THE HOLE.',
            'RIH 13-3/8" WEATHERFORD DV TOOL; NOT YET RUN INTO THE HOLE.',
            'RIH 13-3/8" WEATHERFORD DV TOOL. NOT YET RUN INTO THE HOLE.',
            'RIH 13-3/8" WEATHERFORD DV TOOL! NOT YET RUN INTO THE HOLE.',
            'RIH 13-3/8" WEATHERFORD DV TOOL; RIH NOT COMMENCED.',
        ]
        # Bare M/U and INSTALL stay candidates: the June corpus phrases genuine
        # time-log DV steps that way (35 June CONFIRMED clusters recovered
        # 2026-10-16 when verbs were restored); review-160 faulted only
        # surface-qualified or negated makeup, never bare makeup verbs.
        # Candidacy is not acceptance: rows still need Jev thresholds plus
        # physical-page verification, and qualified output stays zero here.
        positives = ['P/U AND M/U 13-3/8" WEATHERFORD DV TOOL & RIH SAME.',
                     'RIH 13-3/8" WEATHERFORD DV TOOL; CONTINUED RIH.',
                     'M/U 13-3/8" WEATHERFORD DV TOOL.',
                     'INSTALL 13-3/8" WEATHERFORD DV TOOL.']
        receipt = []
        for i, context in enumerate(negatives + positives):
            expected = i >= len(negatives)
            with self.subTest(context=context):
                pdf = TMP / ('parent-run-%d.pdf' % i)
                with fitz.open() as doc:
                    doc.new_page().insert_textbox((40, 40, 560, 200), context)
                    doc.save(pdf)
                e = dict(event(context), source_file=pdf.name)
                r = result(e)
                # Verify the COMPLETE negative quotation too, proving rejection
                # is semantic, not an absent-page/quote shortcut.
                self.assertTrue(jc.verify_pdf_source(pdf, 1, context, OUT/'parent-case-timings.jsonl', 'repair161'))
                support = jc.direct_support(context)
                self.assertEqual(bool(support), expected)
                def verifier(s):
                    ok = jc.verify_pdf_source(pdf, s['source_page'], s['quote'],
                                              OUT/'parent-case-timings.jsonl', 'repair161')
                    if ok:
                        s.update(physical_page_verified=True, source_sha256=jc.sha256(pdf))
                    return ok
                rows, ledger, _, _ = jc.consume([r], {(e['date'], e['rig'], e['well']): [e]}, verifier)
                self.assertEqual(len(rows), int(expected))
                self.assertEqual(ledger[0]['sources'][0]['context'], context)
                self.assertEqual(ledger[0]['disposition'], 'ELIGIBLE_CANDIDATE' if expected else 'REVIEW')
                # Direct builder bypass attempt with real file/hash/page receipts.
                source = dict(source_file=pdf.name, source_page=1, quote=context,
                              size_span='13-3/8', supplier_span='WEATHERFORD',
                              physical_page_verified=True, source_sha256=jc.sha256(pdf))
                row = dict(r, provenance='extracted', source_page=1, source_pages=[1],
                           sources=[source], physical_page_verified=True)
                if expected:
                    build_db.validate_matrix([{'rows': [row]}])
                    self.assertEqual(rows[0]['sources'][0]['quote'], context)
                else:
                    with self.assertRaisesRegex(ValueError, 'does not support'):
                        build_db.validate_matrix([{'rows': [row]}])
                receipt.append(dict(context=context, source_file=str(pdf), source_sha256=jc.sha256(pdf),
                                    quote_verified=True, expected_run=expected, direct_support=support,
                                    rows=len(rows), disposition=ledger[0]['disposition'], builder_accepts=expected))
        (OUT/'parent-cases-after.json').write_text(json.dumps(receipt, indent=2))

    def test_parent_planned_and_pages(self):
        good = event()
        self.assertTrue(jc.audit_spans(result(good), [good])[0])
        for text in ('Next 24 hr plan: RUN 13-3/8" WFD DV TOOL.',
                     'PLAN TO RUN 13-3/8" WFD DV TOOL.',
                     'DRILL OUT 13-3/8" WFD DV TOOL.',
                     '13-3/8" WFD DV TOOL ON BOARD. RIH CASING.',
                     'Last Csg Size 13-3/8". WFD responsibility. RIH DV TOOL.',
                     'RIH 13-3/8" DV TOOL. WFD CEMENT PUMP.',
                     'RIH 113-3/8" WFD DV TOOL.',
                     'RIH 13-3/8" WFD DV TOOL. WELL: OTHER',
                     'RIH 13-3/8" DV TOOL. THEN WFD LOGGING.',
                     'PLAN: complete well. RIH 13-3/8" WFD DV TOOL.',
                     'RIH 13-3/8" CSG AND M/U WFD DV TOOL.',
                     'R/U WFD CMT HEAD AND RIH 13-3/8" DV TOOL.'):
            with self.subTest(context=text):
                e = event(text)
                self.assertFalse(jc.audit_spans(result(e), [e])[0])
        for page in (None, 0, -1, True, '1', 1.0):
            e = dict(good, source_page=page)
            self.assertFalse(jc.audit_spans(result(e), [e])[0])
        self.assertFalse(jc.audit_spans(result(), [])[0])

    def test_adoption_and_modal_tuple(self):
        e = event('M/U 13.375" WEATHERFORD DV TOOL AND RIH.')
        self.assertTrue(jc.audit_spans(result(e, True), [e])[0])
        self.assertFalse(jc.audit_spans(dict(result(e), size='9.625'), [e])[0])
        second = dict(e, context='M/U 9-5/8" HLB DV TOOL AND RIH.')
        self.assertFalse(jc.audit_spans(result(e), [e, second])[0])
        self.assertFalse(jc.audit_spans(dict(result(e), verdict='BOGUS'), [e])[0])
        self.assertFalse(jc.audit_spans(result(e), [dict(e, well='OTHER')])[0])

    def test_sources_and_two_runs(self):
        e = event('1200 - 1300 M/U 13-3/8" WFD DV TOOL AND RIH.')
        e2 = dict(e, source_file='other.pdf', source_page=99)
        r = result(e)
        row = jc.make_row(r, [e, e2])
        self.assertEqual({(s['source_file'], s['source_page']) for s in row['sources']},
                         {('synthetic.pdf', 1), ('other.pdf', 99)})
        e2['context'] = '1400 - 1500 M/U 13-3/8" WFD DV TOOL AND RIH.'
        self.assertFalse(jc.audit_spans(r, [e, e2])[0])

    def test_versioned_cache_and_all_dispositions(self):
        e = event()
        r = result(e)
        self.assertTrue(jc.cache_valid(r, [e]))
        self.assertFalse(jc.cache_valid(r, [dict(e, context='changed')]))
        results = [r, dict(r, date='2026-07-01'), dict(r, date='2026-08-01'),
                   dict(r, verdict='BOGUS'), dict(r, cache={})]
        by = {(e['date'], e['rig'], e['well']): [e]}
        rows, ledger, candidates, boundary = jc.consume(results, by, lambda s: True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(len(ledger), 5)
        self.assertEqual([x['disposition'] for x in ledger],
                         ['ELIGIBLE_CANDIDATE', 'JUNE_BOUNDARY_REVIEW', 'OUT_OF_SCOPE', 'SOURCE_INVALID', 'REVIEW'])
        self.assertEqual(len(boundary), 1)
        self.assertTrue(all(x['date'].startswith('2026-06-') for x in rows))
        self.assertEqual(jc.consume([r], by, lambda s: False)[0], [])
        not_run=copy.deepcopy(r); not_run['verdict']='NOT_A_RUN'; not_run['jev']['tool_run']=.1
        self.assertEqual(jc.consume([not_run],by)[1][0]['disposition'],'NOT_A_RUN')
        conflict=dict(r,verdict='CONFLICT')
        self.assertEqual(jc.consume([conflict],by)[1][0]['disposition'],'CONFLICT')

    def test_request_failure_is_logged(self):
        path=TMP/'request-input.txt'; path.write_text('synthetic')
        ledger=OUT/'request-failure-timing.jsonl'
        with self.assertRaises(SystemExit):
            with ask.request_phase(ledger,path,'synthetic-hash','jev-1.13.0',ja.QUESTION_HASH):
                raise SystemExit('explicit expected failure')
        rec=json.loads(ledger.read_text().splitlines()[-1])
        self.assertEqual(rec['status'],'failed')
        self.assertEqual(rec['source_sha256'],jc.sha256(path))
        self.assertGreaterEqual(rec['elapsed_seconds'],0)

    def test_retry_headers_and_budget_both_paths(self):
        from datetime import datetime, timezone
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.assertEqual(ask.retry_after_seconds({'Retry-After':'120'},1),120)
        self.assertEqual(ask.retry_after_seconds({'retry-after-ms':'1500'},1),1.5)
        self.assertEqual(ask.retry_after_seconds({'Retry-After':'Thu, 01 Jan 2026 00:02:00 GMT'},1,now),120)
        self.assertEqual(ask.retry_after_seconds({'retry-after':'nan'},2),4)
        for fn in (lambda: ask.call('synthetic', ja.QUESTIONS, 'jev-1.13.0', 'not-a-secret', retry_budget=30),
                   lambda: ja.one_call('synthetic','not-a-secret','jev-1.13.0',retry_budget=30)):
            error = urllib.error.HTTPError(ask.ENDPOINT,429,'rate',{'retry-after':'120'},None)
            with patch.object(ask.urllib.request,'urlopen',side_effect=error) as op, patch.object(ask.time,'sleep') as sleep:
                with self.assertRaises(SystemExit): fn()
                self.assertEqual(op.call_count,1)
                sleep.assert_not_called()
        for error in (urllib.error.URLError('offline'), TimeoutError()):
            with patch.object(ask.urllib.request,'urlopen',side_effect=error) as op, patch.object(ask.time,'sleep'):
                with self.assertRaises(SystemExit): ja.one_call('s','k','jev-1.13.0')
                self.assertEqual(op.call_count,3)

    def test_pdf_timing_actual_page_failure_ocr(self):
        import fitz
        ledger = OUT/'test-phases.jsonl'
        source = TMP/'synthetic.pdf'
        with fitz.open() as d:
            p = d.new_page(); p.insert_text((72,72),'M/U 13-3/8" WEATHERFORD DV TOOL & RIH SAME.')
            d.new_page()  # image/blank fixture, not a claim about source June26
            d.save(source)
        quote = event()['context']
        self.assertTrue(jc.verify_pdf_source(source,1,quote,ledger,'repair-tests'))
        self.assertFalse(jc.verify_pdf_source(source,2,quote,ledger,'repair-tests'))
        self.assertFalse(jc.verify_pdf_source(source,100,quote,ledger,'repair-tests'))
        with self.assertRaises(FileNotFoundError):
            jc.verify_pdf_source(TMP/'missing.pdf',1,quote,ledger,'repair-tests')
        records = [json.loads(x) for x in ledger.read_text().splitlines()]
        self.assertTrue({'ok','OCR_NEEDED','SOURCE_INVALID','failed'} <= {r['status'] for r in records})
        self.assertTrue(all(all(k in r for k in ('source_sha256','attempt_id','run_id','phase','start_utc','end_utc','elapsed_seconds','status')) for r in records))

    def test_consumer_cli_to_verified_row(self):
        import fitz
        import subprocess
        source=TMP/'cli-synthetic.pdf'
        e=dict(event(),source_file=source.name)
        r=result(e,adopted=True)
        r['fixture_kind']='SYNTHETIC MANUALLY AUTHORED JUDGMENT; NOT LIVE JEV'
        with fitz.open() as doc:
            page=doc.new_page(); page.insert_text((72,72),e['context']); doc.save(source)
        adj=TMP/'cli-adj.json'; adj.write_text(json.dumps({'results':[r]}))
        events=TMP/'cli-events.json'; events.write_text(json.dumps({'events':[e]}))
        output=OUT/'synthetic-cli-output.json'
        command=[sys.executable,str(PKG/'data/jev_consume.py'),'--adj',str(adj),'--events',str(events),
                 '--out',str(output),'--ledger',str(OUT/'synthetic-cli-ledger.json'),
                 '--timings',str(OUT/'synthetic-cli-timings.jsonl'),'--pdf-dir',str(TMP)]
        done=subprocess.run(command,capture_output=True,text=True)
        self.assertEqual(done.returncode,0,done.stdout+done.stderr)
        payload=json.loads(output.read_text())
        self.assertEqual(payload['row_count'],1)
        row=payload['rows'][0]
        self.assertTrue(row['physical_page_verified'])
        self.assertEqual(row['sources'][0]['source_sha256'],jc.sha256(source))
        build_db.validate_matrix([{'rows':[row]}])
        (OUT/'synthetic-cli-command.json').write_text(json.dumps({'source_kind':'SYNTHETIC FIXTURE ONLY','command':command,'stdout':done.stdout},indent=1))

    def test_builder_prevalidation_and_api_csv(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        import plugin_api
        directory = TMP/'matrix'; directory.mkdir(exist_ok=True)
        shutil.copyfile(PKG/'data/ingested/matrix/June2026.json',directory/'June2026.json')
        builder_event = dict(event(), source_file='builder-synthetic.pdf')
        row = jc.make_row(result(builder_event), [builder_event])
        import fitz
        synthetic = TMP/'builder-synthetic.pdf'
        with fitz.open() as doc:
            page=doc.new_page(); page.insert_text((72,72),event()['context'])
            doc.save(synthetic)
        for s in row['sources']:
            self.assertTrue(jc.verify_pdf_source(synthetic,s['source_page'],s['quote'],OUT/'builder-source-timing.jsonl','builder-test'))
            s.update(physical_page_verified=True,source_sha256=jc.sha256(synthetic))
        row['physical_page_verified'] = True
        matrix = directory/'June2026-extracted.json'
        matrix.write_text(json.dumps({'rows':[row]}))
        db = OUT/'isolated-home/state/orio-ops/orio_demo.db'
        args = ['--home',str(OUT/'isolated-home'),'--matrix-dir',str(directory),'--quiet']
        build_db.main(args)
        before = jc.sha256(db)
        matrix.write_text(json.dumps({'rows':[dict(row,source_pages=[True])]}))
        with self.assertRaises(ValueError): build_db.main(args)
        self.assertEqual(jc.sha256(db),before)
        matrix.write_text(json.dumps({'rows':[row]}))
        app=FastAPI(); app.include_router(plugin_api.router,prefix='/api/plugins/euphoria-orio-operations')
        client=TestClient(app); base='/api/plugins/euphoria-orio-operations'
        response=client.get(base+'/matrix?limit=5000').json()
        self.assertEqual(response['total'],132)
        ex=next(r for r in response['rows'] if r['extraction']=='extracted')
        self.assertEqual(json.loads(ex['evidence_json'])['sources'],row['sources'])
        self.assertEqual(ex['report_date'],'2026-06-01')
        self.assertIsNone(ex['date_rih'])
        body=list(csv.DictReader(io.StringIO(client.get(base+'/matrix/export.csv').text)))
        self.assertEqual(len(body),132)
        exported=next(r for r in body if r['Provenance']=='extracted')
        self.assertEqual(exported['Date RIH'],'')
        self.assertEqual(exported['Report Date'],'2026-06-01')
        self.assertEqual(json.loads(next(r for r in body if r['Provenance']=='extracted')['Evidence JSON'])['sources'],row['sources'])
        wb=[r for r in response['rows'] if r['extraction']=='workbook']
        reference=json.loads((directory/'June2026.json').read_text())['rows']
        keys=('date','rig','well','size','company')
        self.assertEqual(sorted(tuple(r[k] for k in keys) for r in wb), sorted(tuple(r[k] for k in keys) for r in reference))
        for value in ('=1+1','+1','-2','@SUM(A1)','\t=2','\r=2'):
            self.assertTrue(plugin_api._csv_cell(value).startswith("'"))
        for bad in (dict(row, sources=[]), dict(row, source_file='a.pdf;b.pdf'),
                    {'source_file':'not-a-workbook.pdf','source_page':None},
                    dict(row, source_pages=[0]), dict(row,date='2026-07-01')):
            with self.assertRaises(ValueError): build_db.validate_matrix([{'rows':[bad]}])
        (OUT/'api-positive-response.json').write_text(json.dumps(response,indent=1))
        (OUT/'api-positive-export.csv').write_text(client.get(base+'/matrix/export.csv').text)
        with sqlite3.connect(db) as con:
            con.execute('ALTER TABLE matrix_rows DROP COLUMN evidence_json')
        self.assertEqual(client.get(base+'/matrix/export.csv').status_code,200)


if __name__=='__main__':
    unittest.main(verbosity=2)
