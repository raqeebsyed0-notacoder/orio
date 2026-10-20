"""LANE 7 standalone check (no pytest in the hermes venv). Exit non-zero on failure.

One CHECKED real example per feature (evidence links verified against the
frozen registers) + negative cases. Fixture-only validation is labelled
as such where the source gives no support.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
PKG = HERE.parent
sys.path.insert(0, str(PKG / 'dashboard'))

import intelligence as intel

def main():
    fails = []


    def check(name, cond, extra=''):
        print(('PASS' if cond else 'FAIL'), name, extra)
        if not cond:
            fails.append(name)


    bundle = intel.build_bundle()
    up = bundle['upcoming']
    sup = bundle['suppliers']
    prob = bundle['problems']
    corr = bundle['corrections']
    qs = bundle['questions']

    # ---------------------------------------------------------- feature 1
    check('f1-status', up['evidence_status'] == 'implemented-on-real-evidence')
    k = [i for i in up['items']
         if i['rig'] == 'KINGDOM-2' and i['date'] == '2026-06-04']
    check('f1-checked-plan', len(k) == 1
          and 'Next 24 hr plan' in k[0]['plan_quote']
          and 'WFD DV TOOL' in k[0]['plan_quote'], 'n=%d' % len(k))
    check('f1-plan-evidence', k[0]['evidence']['source_file'] == 'LMR06042026.pdf'
          and k[0]['evidence']['source_page'] == 324
          and k[0]['evidence']['sha256'] ==
          'ffc49468d8b829c4057eeb2d6c1a0e3cc59817208d3baf94e6a53e33080f12a1'
          and k[0]['evidence']['verdict'] == 'CONFIRMED')
    check('f1-outcome-unconfirmed', k[0]['outcome'] == 'UNCONFIRMED',
          k[0]['outcome'])
    check('f1-retrospective-labelled',
          (k[0]['retrospective'] or {}).get('date') == '2026-06-05'
          and 'FET' in (k[0]['retrospective'] or {}).get('owner', '')
          and 'RETROSPECTIVE QA' in (k[0]['retrospective'] or {}).get('note', ''))
    early = intel.build_bundle(as_of='2026-06-03')['upcoming']
    check('f1-historical-view',
          not [i for i in early['items']
               if i['rig'] == 'KINGDOM-2' and i['date'] == '2026-06-04']
          and early['as_of'] == '2026-06-03')
    check('f1-unsupported-outcomes',
          set(up['unsupported_outcomes']) == {'COMPLETED', 'POSTPONED',
                                              'CANCELLED'})
    check('f1-negative-recap', 'recap' in ' '.join(up['negative_cases']))

    # ---------------------------------------------------------- feature 2
    check('f2-status', sup['evidence_status'] == 'implemented-on-real-evidence')
    by_code = {s['supplier_code']: s for s in sup['suppliers']}
    slb = by_code.get('SLB')
    check('f2-checked-slb', slb is not None
          and slb['first_observed']['date'] == '2026-06-03'
          and slb['first_observed']['rig'] == 'HP-706'
          and slb['first_observed']['source_file'] == 'LMR06032026.pdf'
          and slb['first_observed']['source_page'] == 302
          and slb['first_observed']['verdict'] == 'REVIEW'
          and slb['supplier_display'] == 'SCHLUMBERGER (KSV)'
          and 'SLB PUMP UNIT' in slb['first_observed']['context_excerpt'])
    check('f2-wording', slb['wording'] ==
          'first observed in covered reports: 2026-06-03')
    check('f2-repeat-use', slb['repeat_use']['observations'] == 8
          and slb['repeat_use']['distinct_rigs'] == 7)
    check('f2-wfd-first', by_code.get('WFD', {}).get('first_observed', {})
          .get('date') == '2026-06-01')
    check('f2-no-unknown', 'UNKNOWN' not in by_code)
    check('f2-coverage-on-rows',
          all(s['coverage'] == intel.COVERAGE_LABEL for s in sup['suppliers']))

    # ---------------------------------------------------------- feature 3
    check('f3-status', prob['evidence_status'] == 'implemented-on-real-evidence')
    sp = [i for i in prob['items']
          if i['rig'] == 'SP-26' and i['date'] == '2026-06-18']
    check('f3-checked-stuck-plug', len(sp) == 1
          and 'STUCK ACROSS DV' in sp[0]['problem_quote']
          and 'UNABLE TO CLOSE DV TOOL' in sp[0]['problem_quote'], 'n=%d' % len(sp))
    check('f3-supplier-linked', sp[0]['supplier_linked'] == 'FET')
    check('f3-problem-evidence', sp[0]['evidence']['source_file'] ==
          'LMR06182026.pdf' and sp[0]['evidence']['verdict'] == 'CONFIRMED'
          and sp[0]['evidence']['sha256'] ==
          'fd66b1f9d4c1bbf369d2c40865e5dd2c89362fcce73702194ecbb539a3c0f8e2')
    check('f3-resolution-honest',
          sp[0]['resolution'].get('status') ==
          'resolution_not_reported_in_covered_reports')
    ad = [i for i in prob['items']
          if i['rig'] == 'AD-83' and i['date'] == '2026-06-15']
    check('f3-hal-damage-shown', len(ad) == 1
          and 'DEFORMATION AND DAMAGE ON DV' in ad[0]['problem_quote']
          and ad[0]['supplier_linked'] == 'HAL'
          and ad[0]['evidence']['verdict'] == 'NOT_A_RUN')
    check('f3-no-july', not [i for i in prob['items']
                             if (i['date'] or '') > '2026-06-30'])
    check('f3-no-power-unit', not [i for i in prob['items']
                                   if i['rig'] == 'ADC-16'])
    check('f3-no-ranking', prob['reliability_ranking'].startswith('NONE'))

    # ---------------------------------------------------------- feature 4
    check('f4-status', corr['evidence_status'] == 'implemented-on-real-evidence')
    check('f4-three-proposed', len(corr['proposed_corrections']) == 3)
    s29 = [c for c in corr['proposed_corrections'] if c['sno'] == 29]
    check('f4-checked-sno29', len(s29) == 1
          and s29[0]['original_workbook']['company'] == 'TAM'
          and s29[0]['observed_evidence']['jev_choice'] ==
          'FORUM ENERGY TECHNOLOGIES (FET)'
          and s29[0]['observed_evidence']['source_file'] == 'LMR06082026.pdf'
          and s29[0]['observed_evidence']['source_page'] == 273
          and s29[0]['observed_evidence']['sha256'] ==
          'c0accb8fddda782ac5026f8c06d116837aaa3c8a4a175e03be939b300766ec9c'
          and 'never auto-applied' in s29[0]['status'])
    check('f4-size-rows', {c['sno'] for c in corr['proposed_corrections']}
          == {29, 56, 65})
    check('f4-eleven-conflicting', len(corr['conflicting_rows']) == 11)
    check('f4-history-preserved',
          all(c['history_preserved'] for c in corr['proposed_corrections'])
          and all(c['history_preserved'] for c in corr['conflicting_rows']))
    rules = {r['code']: r for r in corr['alias_rules']}
    check('f4-alias-pos', 'DAVIS' in (rules.get('FET', {}).get('evidence') or '')
          .upper()
          and 'HLB' in (rules.get('HAL', {}).get('report_aliases') or [])
          and rules.get('WFD', {}).get('display') == 'WEATHERFORD (WFD)')
    check('f4-alias-neg', rules.get('TAM', {}).get('status') ==
          'needs-ajeez-confirmation'
          and 'Do not expand' in (rules.get('TAM', {}).get('evidence') or ''))
    check('f4-effort-real', corr['effort_metrics']['june_26_increment_s'] == 656.3
          and corr['effort_metrics']['full_corpus_s'] == 3305.0
          and 'WITHIN' in (corr['effort_metrics']['june_26_verdict'] or '')
          and 'MISS' in (corr['effort_metrics']['full_corpus_verdict'] or ''))
    check('f4-zero-cost', '$0.00' in corr['effort_metrics']['jev_cost_note'])

    # ---------------------------------------------------------- questions
    qlist = qs.get('questions', [])
    check('q-eight', len(qlist) == 8, 'n=%d' % len(qlist))
    check('q-ids', [q['id'] for q in qlist] ==
          ['Q-UP-01', 'Q-UP-02', 'Q-SU-01', 'Q-SU-02',
           'Q-TP-01', 'Q-TP-02', 'Q-RC-01', 'Q-RC-02'])
    check('q-links', all(q.get('range_view', '').startswith('GET /intelligence/')
                         for q in qlist))

    # ---------------------------------------------------------- v2 re-point
    v2 = intel.build_bundle_v2()
    vsup = v2['suppliers']
    check('v2-no-stale', 'stale' not in vsup and 'stale' not in v2['corrections'])
    vcodes = {s['supplier_code']: s for s in vsup['suppliers']}
    check('v2-ruled-counts',
          {c: vcodes[c]['repeat_use']['observations'] for c in vcodes}
          == {'WFD': 47, 'HAL': 39, 'FET': 26, 'TAM': 10},
          str({c: vcodes[c]['repeat_use']['observations'] for c in vcodes}))
    check('v2-first-dates',
          vcodes['WFD']['first_observed']['date'] == '2026-06-01'
          and vcodes['HAL']['first_observed']['date'] == '2026-06-01'
          and vcodes['FET']['first_observed']['date'] == '2026-06-01'
          and vcodes['TAM']['first_observed']['date'] == '2026-06-03')
    check('v2-repeat-use',
          vcodes['WFD']['repeat_use']['distinct_rigs'] == 41
          and vcodes['WFD']['repeat_use']['distinct_wells'] == 42
          and vcodes['HAL']['repeat_use']['distinct_rigs'] == 34
          and vcodes['TAM']['repeat_use']['observations'] == 10)
    check('v2-displays',
          vcodes['WFD']['supplier_display'] == 'WEATHERFORD (WFD)'
          and vcodes['HAL']['supplier_display'] == 'HALLIBURTON (HAL)'
          and vcodes['FET']['supplier_display'] == 'FORUM ENERGY TECHNOLOGIES (FET)'
          and vcodes['TAM']['supplier_display'] == 'TAM (TAM)'
          and 'UNPROVEN' not in vcodes
          and vsup['unproven_company_rows'] == 1)
    check('v2-supplier-evidence',
          vcodes['HAL']['first_observed']['source_file'] == 'LMR06012026.pdf'
          and 'PHASE6-SHEET1-VERIFIED' in
          (vcodes['HAL']['first_observed']['authority'] or ''))
    check('v2-status-counts',
          vsup['status_counts'] == {'COUNTED': 123, 'PENDING_FILE': 6,
                                    'PENDING_RULING': 3, 'EXCLUDED': 3})
    vcorr = v2['corrections']
    check('v2-ruling', vcorr['ruling']['authority'] == 'Ajeez'
          and vcorr['ruling']['date'] == '2026-10-20')
    check('v2-applied',
          len(vcorr['applied_corrections']) == 2
          and {a['row'] for a in vcorr['applied_corrections']} == {65, 79}
          and all(a['status'] == 'APPLIED' and a['history_preserved']
                  for a in vcorr['applied_corrections']))
    a65 = [a for a in vcorr['applied_corrections'] if a['row'] == 65][0]
    a79 = [a for a in vcorr['applied_corrections'] if a['row'] == 79][0]
    check('v2-applied-originals',
          a65['original_sheet1'] == '9-5/8'
          and a65['adjudicated_value'] == '13-3/8'
          and a65['page']['file'] == 'LMR06162026.pdf'
          and a79['original_sheet1'] == 'FET'
          and a79['adjudicated_value'] == 'HAL'
          and 'HALLIBURTON DV TOOL' in (a65['page_quote'] or ''))
    check('v2-groups', len(vcorr['kept_at_tam']) == 3
          and len(vcorr['restored_unique_jobs']) == 4
          and len(vcorr['provisional_rows']) == 3
          and len(vcorr['codified_rules']) == 2
          and all(p['status'] == 'PROVISIONAL_PENDING_AJEEZ'
                  for p in vcorr['provisional_rows']))
    vrules = {r['code']: r for r in vcorr['alias_rules']}
    check('v2-alias-reuse',
          vrules.get('WFD', {}).get('display') == 'WEATHERFORD (WFD)'
          and vrules.get('TAM', {}).get('display') == 'TAM (TAM)'
          and vrules.get('TAM', {}).get('status') == 'needs-ajeez-confirmation')
    check('v2-effort-honest',
          vcorr['effort_metrics']['june_26_increment_s'] == 656.3
          and 'no machine-observed' in vcorr['effort_metrics']['v2_note'])

    # ---------------------------------------------------------- static guards
    src = (PKG / 'dashboard' / 'intelligence.py').read_text(encoding='utf-8')
    for mod in ('socket', 'urllib', 'httpx', 'requests', 'smtplib',
                'email.mime'):
        check('no-net-' + mod, 'import %s' % mod not in src)

    # ---------------------------------------------------------- vendor fidelity
    import hashlib as _hl
    _proj = PKG.parent  # Innovex (ajeez): frozen project-tree inputs
    _pairs = [
        ('dv-june-adjudicated.json',
         _proj / '06_Working-Notes' / 'dv-june-adjudicated.json'),
        ('lane4-reconciliation-round2.json',
         _proj / '06_Working-Notes' / 'reviews' / 'june-closeout-2026-10-19'
         / 'lane4-reconciliation-round2.json'),
        ('lane4-timing-ledger.json',
         _proj / '06_Working-Notes' / 'reviews' / 'june-closeout-2026-10-19'
         / 'lane4-timing-ledger.json'),
        ('coverage-ledger.json',
         _proj / '06_Working-Notes' / 'reviews'
         / 'june-ocr-coverage-2026-10-19' / 'coverage-ledger.json'),
        ('adjudication-table.json',
         _proj / '06_Working-Notes' / 'reviews' / 'pipeline-v2-2026-10-19'
         / 'phase7-ajeez-rulings' / 'adjudication-table.json'),
    ]
    for name, tree_path in _pairs:
        vendored = PKG / 'data' / 'registers' / name
        check('vendor-present-' + name, vendored.exists())
        if vendored.exists() and tree_path.exists():
            vh = _hl.md5(vendored.read_bytes()).hexdigest()
            th = _hl.md5(tree_path.read_bytes()).hexdigest()
            check('vendor-identical-' + name, vh == th, vh[:12])

    print('FAILURES: %s' % (fails if fails else 'none'))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
