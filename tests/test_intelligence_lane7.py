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

    # ---------------------------------------------------------- static guards
    src = (PKG / 'dashboard' / 'intelligence.py').read_text(encoding='utf-8')
    for mod in ('socket', 'urllib', 'httpx', 'requests', 'smtplib',
                'email.mime'):
        check('no-net-' + mod, 'import %s' % mod not in src)

    print('FAILURES: %s' % (fails if fails else 'none'))
    sys.exit(1 if fails else 0)


if __name__ == '__main__':
    main()
