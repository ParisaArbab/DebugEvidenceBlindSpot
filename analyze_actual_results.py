"""Analyze and independently audit both real Qwen live-debugging runs.

This script loads real raw-response JSONL files; it never generates model scores.
Output: results/analysis_metrics.json and results/case_level_comparison.csv.
"""
from __future__ import annotations
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from verify_model_results import verify

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / 'results'
FILES = {
    'baseline': RESULTS / 'live_qwen_all.jsonl',
    'evidence_aware': RESULTS / 'live_qwen_evidence_aware.jsonl',
}
CONDITIONS = ['raw', 'tail_only', 'causal_slice', 'decoy_summary', 'retrieval_enabled']


def load_verified():
    runs = {}
    for mode, path in FILES.items():
        checked = verify(path)
        rows = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
        assert all(x.get('prompt_mode') == mode for x in rows), f'Wrong mode for {path}'
        assert len({(x['case_id'], x['condition']) for x in rows}) == 80
        # The two matched worlds must be indistinguishable when causal evidence is deleted.
        for family in {r['family_id'] for r in rows}:
            for cond in ('tail_only', 'decoy_summary', 'retrieval_enabled'):
                twin = [r for r in rows if r['family_id'] == family and r['condition'] == cond]
                assert len(twin) == 2 and len({r['observed_log_sha256'] for r in twin}) == 1, (mode, family, cond)
        for r in rows:
            assert r['correct_diagnosis'] == (r['final_decision'] == r['gold'])
            assert r['requested_evidence'] == (r['initial_decision'] == 'NEED_LOG')
            assert r['test_passed'] in (True, False)
            assert r['model_revision'] == checked['model_revision']
        runs[mode] = (checked, rows)
    assert runs['baseline'][0]['model_revision'] == runs['evidence_aware'][0]['model_revision']
    assert {(r['case_id'], r['condition']) for r in runs['baseline'][1]} == {(r['case_id'], r['condition']) for r in runs['evidence_aware'][1]}
    return runs


def summarize(runs):
    metrics = {
        'study': 'Live Causal Evidence Deletion (16 executable bug worlds / 8 paired families)',
        'model': runs['baseline'][0]['model'],
        'model_revision': runs['baseline'][0]['model_revision'],
        'experimental_unit_note': 'Two correlated worlds per family; results descriptive, not representative of production debugging',
        'runs': {},
        'paired': {},
    }
    for mode, (_, rows) in runs.items():
        metrics['runs'][mode] = {}
        for cond in CONDITIONS:
            subset = [r for r in rows if r['condition'] == cond]
            ct = Counter(r['initial_decision'] for r in subset)
            metric = {
                'n': len(subset),
                'verified_repairs': sum(bool(r['test_passed']) for r in subset),
                'correct_diagnoses': sum(bool(r['correct_diagnosis']) for r in subset),
                'initial_decisions': {k: ct.get(k, 0) for k in ('A', 'B', 'NEED_LOG', 'INVALID')},
                'initial_evidence_requests': ct['NEED_LOG'],
                'retrievals': sum(bool(r['retrieved']) for r in subset),
                'initial_unsupported_guesses': sum(r['initial_decision'] in ('A','B') for r in subset) if cond in ('tail_only','decoy_summary','retrieval_enabled') else None,
                'mean_log_characters': round(sum(r['observed_log_characters'] for r in subset)/len(subset), 2),
                'mean_prompt_tokens': round(sum(r['initial_response']['prompt_tokens'] for r in subset)/len(subset),2),
                'mean_generated_tokens': round(sum(r['initial_response']['generated_tokens'] for r in subset)/len(subset),2),
                'initial_max_token_hits': sum(r['initial_response']['generated_tokens'] == 120 for r in subset),
                'final_invalid_responses': sum(r['final_decision'] == 'INVALID' for r in subset),
            }
            if cond == 'retrieval_enabled':
                metric['recovered_repairs_after_retrieval'] = sum(r['retrieved'] and r['test_passed'] for r in subset)
                metric['retrieval_final_max_token_hits'] = sum(r['retrieved'] and r['final_response']['generated_tokens'] == 120 for r in subset)
            metrics['runs'][mode][cond] = metric
    for cond in CONDITIONS:
        a = {(r['case_id'], r['condition']):r for r in runs['baseline'][1] if r['condition']==cond}
        b = {(r['case_id'], r['condition']):r for r in runs['evidence_aware'][1] if r['condition']==cond}
        metrics['paired'][cond] = {
            'both_repaired':sum(a[k]['test_passed'] and b[k]['test_passed'] for k in a),
            'baseline_only_repaired':sum(a[k]['test_passed'] and not b[k]['test_passed'] for k in a),
            'evidence_aware_only_repaired':sum(not a[k]['test_passed'] and b[k]['test_passed'] for k in a),
            'neither_repaired':sum(not a[k]['test_passed'] and not b[k]['test_passed'] for k in a),
        }
    return metrics


def save_case_comparison(runs):
    first = {(r['case_id'],r['condition']):r for r in runs['baseline'][1]}
    second = {(r['case_id'],r['condition']):r for r in runs['evidence_aware'][1]}
    columns=['family_id','case_id','world','gold','condition','baseline_initial_decision','baseline_final_decision',
             'baseline_test_passed','baseline_retrieved','baseline_raw_response','baseline_final_raw_response',
             'evidence_aware_initial_decision','evidence_aware_final_decision','evidence_aware_test_passed',
             'evidence_aware_retrieved','evidence_aware_raw_response','evidence_aware_final_raw_response']
    file = RESULTS / 'case_level_comparison.csv'
    with file.open('w',newline='',encoding='utf-8') as out:
        writer=csv.DictWriter(out,fieldnames=columns)
        writer.writeheader()
        for key in sorted(first):
            a,b=first[key],second[key]
            writer.writerow(dict(family_id=a['family_id'],case_id=a['case_id'],world=a['world'],gold=a['gold'],condition=a['condition'],
            baseline_initial_decision=a['initial_decision'],baseline_final_decision=a['final_decision'],baseline_test_passed=a['test_passed'],
            baseline_retrieved=a['retrieved'],baseline_raw_response=a['initial_response']['raw_response'],baseline_final_raw_response=a['final_response']['raw_response'],
            evidence_aware_initial_decision=b['initial_decision'],evidence_aware_final_decision=b['final_decision'],evidence_aware_test_passed=b['test_passed'],
            evidence_aware_retrieved=b['retrieved'],evidence_aware_raw_response=b['initial_response']['raw_response'],evidence_aware_final_raw_response=b['final_response']['raw_response']))
    return file

if __name__=='__main__':
    RESULTS.mkdir(exist_ok=True)
    runs=load_verified()
    stats=summarize(runs)
    (RESULTS/'analysis_metrics.json').write_text(json.dumps(stats,indent=2)+'\n',encoding='utf-8')
    csv_path=save_case_comparison(runs)
    print('VERIFIED:',sum(len(rows) for _,rows in runs.values()),'model decisions; matched-world evidence deletion confirmed')
    for condition in CONDITIONS:
        print(f'{condition:<19}', 'baseline',stats['runs']['baseline'][condition]['verified_repairs'],'/16',
             'evidence-aware',stats['runs']['evidence_aware'][condition]['verified_repairs'],'/16')
    print('Saved',RESULTS/'analysis_metrics.json',csv_path)
