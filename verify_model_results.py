"""Fail closed on incomplete/unattributed live Qwen evaluation outputs."""
import argparse
import json
import re
from pathlib import Path
from live_eval import CONDITIONS,MODEL_ID,summarize
ROOT=Path(__file__).resolve().parent

def verify(path):
    path=Path(path)
    if not path.exists():raise ValueError(f'Missing model output {path}. Do not report model results.')
    rows=[json.loads(x) for x in path.read_text().splitlines() if x.strip()]
    cases=json.loads((ROOT/'live_bugs/manifest.json').read_text())
    if len(rows)!=80:raise ValueError(f'Expected 80 actual model decisions, got {len(rows)}')
    expected={(c['case_id'],con) for c in cases for con in CONDITIONS}
    if {(r['case_id'],r['condition']) for r in rows}!=expected:
        raise ValueError('Missing or duplicate world-condition pairs')
    if any(r.get('backend')!='qwen' or r.get('model')!=MODEL_ID for r in rows):
        raise ValueError('Found non-Qwen rows or wrong model ID')
    revisions={r.get('model_revision') for r in rows}
    if len(revisions)!=1 or not re.fullmatch(r'[0-9a-f]{40}',next(iter(revisions)) or ''):
        raise ValueError('Model revision missing, conflicting or not a full SHA')
    for r in rows:
        for phase in ('initial_response','final_response'):
            x=r.get(phase)
            if not x or not isinstance(x.get('raw_response'),str) or not x['raw_response'].strip():
                raise ValueError('Missing unedited model generation in '+r['case_id'])
            if not isinstance(x.get('prompt_tokens'),int) or x['prompt_tokens']<=0:
                raise ValueError('Missing measured input tokens')
        if r.get('final_decision') not in ('A','B','NEED_LOG','INVALID'):
            raise ValueError('Bad decision value')
    stats=summarize(rows)
    stats.update({'status':'MEASURED_FROM_QWEN_GENERATIONS','model':MODEL_ID,
                  'model_revision':next(iter(revisions)),
                  'caveat':'Executable toy repo patch-selection tasks; not SWE-bench or end-to-end autonomous freeform patch generation.'})
    return stats

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('path',nargs='?',default=str(ROOT/'results/live_qwen_all.jsonl'))
    p.add_argument('--save',default=str(ROOT/'results/live_qwen_metrics.json'))
    args=p.parse_args()
    score=verify(args.path)
    Path(args.save).write_text(json.dumps(score,indent=2)+'\n')
    print('VERIFIED QWEN OUTPUT',json.dumps(score,indent=2))
