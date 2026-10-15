"""No-GPU integrity checks; these are NOT model-evaluation results."""
import json
from collections import Counter,defaultdict
from pathlib import Path
from generate_data import build,prompt_view
from evaluate import parse_decision,CONDITIONS
from analyze import collect

cases=build()
assert len(cases)==48
assert len({c['family_id'] for c in cases})==24
assert Counter(c['gold'] for c in cases)=={'A':24,'B':24}
by_family=defaultdict(dict)
for case in cases:
  by_family[case['family_id']][case['twin']]=case
  assert case['causal_line'] not in prompt_view(case,'tail_only')
  assert case['causal_line'] not in prompt_view(case,'decoy_only')
  for cond in ('raw','cause_preserved','restored'):
    assert case['causal_line'] in prompt_view(case,cond)
  assert 'A static heuristic guessed candidate A' in prompt_view(case,'decoy_only')
for family,t in by_family.items():
  assert set(t)=={'A','B'}
  a,b=t['A'],t['B']
  assert a['candidate_A']==b['candidate_A'] and a['candidate_B']==b['candidate_B']
  for blind in ('tail_only','decoy_only'):
    assert prompt_view(a,blind)==prompt_view(b,blind),family
  assert a['causal_line']!=b['causal_line']
assert parse_decision('{"decision":"B","evidence":"yes"}')[0]=='B'
assert parse_decision('garbage')[0]=='INVALID'
assert parse_decision('{"decision":"NEED_LOG","evidence":"missing"}')[0]=='NEED_LOG'
print(f'PASS: 48 synthetic cases, 24 paired counterfactuals; underdetermined views identical within each pair.')
print('PASS: Real-model score files have not been synthesized.')
