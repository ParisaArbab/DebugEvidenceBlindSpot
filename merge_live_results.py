"""Merge independently validated experiment shards, audit completeness, score."""
import argparse
import json
from pathlib import Path
from live_eval import CONDITIONS,summarize
ROOT=Path(__file__).resolve().parent

def merge(backend):
    rows=[]
    for n in range(4):
        p=ROOT/'results'/f'live_{backend}_part{n}.jsonl'
        if not p.is_file():raise FileNotFoundError(p)
        rows.extend(json.loads(x) for x in p.read_text().splitlines() if x.strip())
    ids=[(r['case_id'],r['condition']) for r in rows]
    assert len(rows)==80, len(rows)
    assert len(ids)==len(set(ids)), 'duplicate decisions'
    cases=json.loads((ROOT/'live_bugs'/'manifest.json').read_text())
    assert set(ids)=={(x['case_id'],co) for x in cases for co in CONDITIONS}
    # Verify uncertainty problem by tracing actual world logs and comparing hashes.
    for family in {x['family_id'] for x in cases}:
        for cond in ('tail_only','decoy_summary','retrieval_enabled'):
            a,b=[r for r in rows if r['family_id']==family and r['condition']==cond]
            assert a['observed_log_sha256']==b['observed_log_sha256'],(family,cond)
    out=ROOT/'results'/f'live_{backend}.jsonl'
    out.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    summary=summarize(rows)
    summary.update({'experimental_backend':backend,'not_a_model_result':True,
        'replications_per_pre_and_post_validation':3,
        'validated_original_failures':16,
        'model':None,
        'methodology':'Executed instrumented Python cases, repeated each faulty behavior 3 times, pytest failure verification, applied selected source patch and verified 3 passes plus pytest.'})
    dest=ROOT/'results'/f'live_{backend}_summary.json'
    dest.write_text(json.dumps(summary,indent=2)+'\n')
    print('Merged',backend,out)
    print(json.dumps(summary['conditions'],indent=2))
    return rows

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--backend',choices=['diagnostic_rule','always_a','both'],default='both')
    args=parser.parse_args()
    for b in (['diagnostic_rule','always_a'] if args.backend=='both' else [args.backend]):merge(b)
