"""Aggregate genuine evaluator output; refuses to invent or synthesize model scores."""
from collections import Counter,defaultdict
from pathlib import Path
import argparse,json,math,random,statistics

CONDITIONS=('raw','tail_only','cause_preserved','decoy_only','restored')

def avg(x):return round(sum(x)/len(x),4) if x else None

def collect(rows):
  grouped=defaultdict(list)
  for r in rows:grouped[r['condition']].append(r)
  scores={}
  for name in CONDITIONS:
    items=grouped[name]
    if not items:continue
    decis=[x['decision'] for x in items]
    inferred=[x['decision'] == x['gold'] for x in items]
    req=[x['decision']=='NEED_LOG' for x in items]
    scores[name]={
       'n':len(items),
       'ground_truth_accuracy':avg(inferred) if name in ('raw','cause_preserved','restored') else None,
       'correct_request_rate':avg(req) if name in ('tail_only','decoy_only') else None,
       'guessed_when_underdetermined_rate':avg([d in ('A','B') for d in decis]) if name in ('tail_only','decoy_only') else None,
       'invalid_response_rate':avg([d=='INVALID' for d in decis]),
       'mean_prompt_tokens':round(statistics.mean(x['prompt_tokens'] for x in items),1),
       'mean_completion_tokens':round(statistics.mean(x['generated_tokens'] for x in items),1),
       'mean_latency_sec':round(statistics.mean(x['latency_sec'] for x in items),2),
       'decision_counts':dict(Counter(decis)),
    }
  indexed={(r['case_id'],r['condition']):r for r in rows}
  recovered=[];request=[]
  for row in grouped['tail_only']:
    tail_dec=row['decision']
    restore=indexed.get((row['case_id'],'restored'))
    if tail_dec=='NEED_LOG':
      request.append(row)
      if restore:recovered.append(restore['decision']==restore['gold'])
  scores['policy_simulation']={
    'description':'Counterfactual one-retrieval policy: reveal stored diagnostic line ONLY IF first tail-only answer was NEED_LOG',
    'requested_log_cases':len(request),
    'request_rate':avg([r['decision']=='NEED_LOG' for r in grouped['tail_only']]),
    'recovered_accuracy_given_request':avg(recovered),
    'end_to_end_success_rate':round(sum(recovered)/len(grouped['tail_only']),4) if grouped['tail_only'] else None,
  }
  # Matched-pair failure: an answer must flip when a single diagnostic line flips.
  families=defaultdict(dict)
  for row in rows:
    families[(row['family_id'],row['condition'])][row['twin']]=row
  result={}
  for name in ('raw','cause_preserved','restored'):
    pairs=[d for (fid,c),d in families.items() if c==name and {'A','B'}<=d.keys()]
    result[name]={'complete_pairs':len(pairs),
                  'correct_causal_reversal_rate':avg([d['A']['decision']=='A' and d['B']['decision']=='B' for d in pairs])}
  scores['matched_pair_reversal']=result
  return scores


def main():
  p=argparse.ArgumentParser()
  p.add_argument('results',help='Path to actual model output produced by evaluate.py')
  p.add_argument('--save',default=None)
  args=p.parse_args()
  path=Path(args.results)
  if not path.is_file():raise SystemExit('No model generations found; run evaluate.py on a GPU first.')
  rows=[json.loads(l) for l in path.read_text().splitlines() if l.strip()]
  if not rows:raise SystemExit('Result file is empty, no measured results to report.')
  assert len({r.get('prompt_mode','baseline') for r in rows})==1, 'Do not mix prompt modes in one metric file'
  assert len({r.get('model_revision') for r in rows})==1, 'Do not mix model revisions'
  for r in rows:
    assert r.get('model') and r.get('decision') in ('A','B','NEED_LOG','INVALID')
  data={'status':'MEASURED_FROM_MODEL_GENERATIONS','model':rows[0]['model'],
        'model_revision':rows[0].get('model_revision'),'prompt_mode':rows[0].get('prompt_mode','baseline'),
        'n_generations':len(rows),'n_families':len({r['family_id'] for r in rows}),
        'metrics':collect(rows)}
  result=json.dumps(data,indent=2,ensure_ascii=False)
  print(result)
  if args.save:
    path=Path(args.save);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(result+'\n')
    print('Saved',path)

if __name__=='__main__':main()
