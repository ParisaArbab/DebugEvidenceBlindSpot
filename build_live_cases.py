"""Build deterministic, runnable counterfactual bug projects.

Each world has exactly one wrong setting in app.py. Both versions genuinely fail
pytest, but the standardized runner emits identical final error text. Diagnostic
lines come from running the code, not prewritten outcomes.
"""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parent
TARGET = ROOT / 'live_bugs'

# Each expression is run inside generated app.py. Settings are simple assignment
# statements so applying an agent-selected patch is exact and auditable.
FAMILIES = [
 dict(id='pagination',name='Paginated export returns incomplete records',
      A='The export loop is limited to one page', B='The cursor never advances to the next page',
      a_key='MAX_PAGES',a_bad='1',a_good='4',b_key='ADVANCE_CURSOR',b_bad='False',b_good='True',
      algorithm='''def run():
    result = []
    cursor = 0
    for _ in range(MAX_PAGES):
        result.append(cursor)
        if ADVANCE_CURSOR:
            cursor += 1
    return result
EXPECTED = [0, 1, 2, 3]'''),
 dict(id='json_cleanup',name='JSON event ingestion fails to parse payload',
      A='The UTF-8 byte-order mark was not removed',B='The trailing comma was not removed',
      a_key='STRIP_BOM',a_bad='False',a_good='True',b_key='STRIP_COMMA',b_bad='False',b_good='True',
      algorithm='''import json

def run():
    payload = '\\ufeff{"ok": true,}'
    if STRIP_BOM:
        payload = payload.lstrip('\\ufeff')
    if STRIP_COMMA:
        payload = payload.replace(',}', '}')
    try:
        return json.loads(payload)
    except ValueError:
        return None
EXPECTED = {'ok': True}'''),
 dict(id='auth_window',name='Valid API credentials incorrectly rejected',
      A='The configured token lifetime is too short', B='The verifier clock skew exceeds the allowed window',
      a_key='TOKEN_TTL',a_bad='30',a_good='600',b_key='CLOCK_SKEW',b_bad='3600',b_good='0',
      algorithm='''def run():
    issued_at = 10000
    request_time = 10120 + CLOCK_SKEW
    return request_time - issued_at <= TOKEN_TTL
EXPECTED = True'''),
 dict(id='memory_budget',name='Synthetic training step exceeds memory limit',
      A='The training batch size exceeds the available budget',B='Retained activations consume the budget',
      a_key='BATCH_SIZE',a_bad='256',a_good='16',b_key='RETAINED_ACTIVATIONS',b_bad='200',b_good='0',
      algorithm='''def run():
    memory_mb = BATCH_SIZE * 4 + RETAINED_ACTIVATIONS * 4
    return memory_mb <= 128
EXPECTED = True'''),
 dict(id='graph_edges',name='Heterogeneous graph message passing misses edges',
      A='Reverse relation edges are removed',B='Forward write relation edges are filtered out',
      a_key='KEEP_REVERSE',a_bad='False',a_good='True',b_key='KEEP_WRITES',b_bad='False',b_good='True',
      algorithm='''def run():
    edges = [('a','writes','p'),('p','rev_writes','a')]
    if not KEEP_REVERSE:
        edges = [e for e in edges if e[1] != 'rev_writes']
    if not KEEP_WRITES:
        edges = [e for e in edges if e[1] != 'writes']
    return len(edges)
EXPECTED = 2'''),
 dict(id='invoice_total',name='Invoice final amount violates the calculation contract',
      A='A cents conversion scale is incorrect',B='The discount is added instead of subtracted',
      a_key='CENTS_SCALE',a_bad='1',a_good='100',b_key='DISCOUNT_SIGN',b_bad='1',b_good='-1',
      algorithm='''def run():
    base_dollars = 120
    discount_dollars = 20
    return (base_dollars + DISCOUNT_SIGN * discount_dollars) * CENTS_SCALE
EXPECTED = 10000'''),
 dict(id='stream_chunk',name='Streaming reader drops records',
      A='The reader stops after a short first chunk',B='The last record is dropped during reassembly',
      a_key='READ_LIMIT',a_bad='2',a_good='4',b_key='DROP_LAST',b_bad='True',b_good='False',
      algorithm='''def run():
    records = [1,2,3,4]
    received = records[:READ_LIMIT]
    return received[:-1] if DROP_LAST else received
EXPECTED = [1,2,3,4]'''),
 dict(id='cache_consistency',name='Caching returns stale or cross-user results',
      A='Cache keys omit the user identifier',B='The cache lifetime is too long',
      a_key='INCLUDE_USER',a_bad='False',a_good='True',b_key='TTL',b_bad='999',b_good='30',
      algorithm='''def run():
    cache = {}
    def query(user, now, value):
        key = user if INCLUDE_USER else 'global'
        if key in cache and now - cache[key][0] < TTL:
            return cache[key][1]
        cache[key] = (now, value)
        return value
    query('alice', 0, 'red')
    other_user = query('bob', 10, 'blue')
    refreshed_user = query('alice', 90, 'green')
    return [other_user, refreshed_user]
EXPECTED = ['blue','green']'''),
]

RUNNER = '''"""Sanitized trace captured by executing this actual buggy app."""
import sys
import app

def main():
    print('[RUN] executing test contract for the live case')
    for field, value in app.diagnostics().items():
        print(f'[DIAGNOSTIC] {field}={value!r}')
    try:
        value = app.run()
        assert value == app.EXPECTED, 'contract validation failed'
        print('[PASS] contract validation succeeded')
    except Exception:
        print('[FAIL] AssertionError: contract validation failed')
        return 1
    return 0

if __name__ == '__main__':
    sys.exit(main())
'''
TEST = '''import app

def test_contract():
    assert app.run() == app.EXPECTED, 'contract validation failed'
'''

def source(f, world):
    ka,kb=f['a_key'],f['b_key']
    av=f['a_bad'] if world=='A' else f['a_good']
    bv=f['b_bad'] if world=='B' else f['b_good']
    return (f'"""Live counterfactual {f["id"]} world {world}."""\n'
            + f'{ka} = {av}\n{kb} = {bv}\n\n'
            + f'def diagnostics():\n    return {{"{ka}": {ka}, "{kb}": {kb}}}\n\n'
            + f['algorithm'] + '\n')

def generate():
    TARGET.mkdir(parents=True,exist_ok=True)
    manifest=[]
    for f in FAMILIES:
        for world in 'AB':
            folder=TARGET/f['id']/world
            folder.mkdir(parents=True,exist_ok=True)
            app=source(f,world)
            (folder/'app.py').write_text(app,encoding='utf-8')
            (folder/'test_app.py').write_text(TEST,encoding='utf-8')
            (folder/'trace_run.py').write_text(RUNNER,encoding='utf-8')
            manifest.append({
                'case_id':f['id']+'_'+world,
                'family_id':f['id'],'world':world,'test_name':f['name'],
                'candidate_A':f['A'],'candidate_B':f['B'],
                'patch_A':{'key':f['a_key'],'before':f['a_bad'],'after':f['a_good']},
                'patch_B':{'key':f['b_key'],'before':f['b_bad'],'after':f['b_good']},
                'source_sha256':hashlib.sha256(app.encode()).hexdigest(),
                'relative_path':str(folder.relative_to(ROOT)),
                'gold':world,
            })
    (TARGET/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
    return manifest

if __name__=='__main__':
    print('Generated',len(generate()),'real bug worlds across',len(FAMILIES),'families')
