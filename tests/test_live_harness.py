"""Regression and leakage tests for the executable paired counterfactuals."""
import hashlib
import json
from pathlib import Path
import shutil
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from live_eval import LIVE,ROOT as ENGINE_ROOT,AlwaysA,DiagnosticRule,CONDITIONS,apply_patch,run_trace,run_pytest,trace_views

CASES=json.loads((LIVE/'manifest.json').read_text())

def test_8_families_16_distinct_worlds():
    assert len(CASES)==16
    assert len(set(c['case_id'] for c in CASES))==16
    assert len(set(c['family_id'] for c in CASES))==8
    assert all(c['world']==c['gold'] for c in CASES)

def test_all_originals_are_correspondingly_buggy_and_pairwise_indistinguishable_without_evidence():
    byfamily={}
    for c in CASES:
        folder=ROOT/c['relative_path']
        assert hashlib.sha256((folder/'app.py').read_bytes()).hexdigest()==c['source_sha256']
        actual=run_trace(folder)
        assert actual['returncode']==1
        views,_=trace_views(actual['stdout'])
        assert len(views)==5
        byfamily.setdefault(c['family_id'],{})[c['world']]=views
    for family,pair in byfamily.items():
        assert set(pair)=={'A','B'}
        for cond in ('tail_only','decoy_summary','retrieval_enabled'):
            assert pair['A'][cond]==pair['B'][cond],(family,cond)
        for cond in ('raw','causal_slice'):
            assert pair['A'][cond]!=pair['B'][cond],(family,cond)

def test_policy_does_not_use_gold_world_or_hidden_diagnostics():
    oracle=DiagnosticRule()
    for case in CASES:
        actual=run_trace(ROOT/case['relative_path'])
        views,diag=trace_views(actual['stdout'])
        assert oracle.decide(case,views['tail_only'])['decision']=='NEED_LOG'
        assert oracle.decide(case,views['decoy_summary'])['decision']=='NEED_LOG'
        # Mangle gold metadata to ensure this policy actually reads diagnostics.
        altered={**case,'gold':'unrelated'}
        assert oracle.decide(altered,views['causal_slice'])['decision']==case['world']
        assert oracle.decide(case,views['retrieval_enabled']+'\n'+diag)['decision']==case['world']

def test_correct_repair_and_wrong_repair_on_each_bug_family():
    for case in CASES:
        with tempfile.TemporaryDirectory() as tmp:
            dst=Path(tmp)
            for file in ('app.py','test_app.py','trace_run.py'):
                shutil.copy(ROOT/case['relative_path']/file,dst/file)
            wrong='B' if case['world']=='A' else 'A'
            changed, _=apply_patch(dst,case,wrong)
            assert not changed,'Wrong patch unexpectedly edits the correct setting'
            assert run_trace(dst)['returncode']==1
        with tempfile.TemporaryDirectory() as tmp:
            dst=Path(tmp)
            for file in ('app.py','test_app.py','trace_run.py'):
                shutil.copy(ROOT/case['relative_path']/file,dst/file)
            changed,_=apply_patch(dst,case,case['world'])
            assert changed
            assert run_trace(dst)['returncode']==0

def test_result_files_complete_and_real_controls():
    for backend in ('diagnostic_rule','always_a'):
        path=ROOT/'results'/f'live_{backend}.jsonl'
        assert path.is_file()
        records=[json.loads(x) for x in path.read_text().splitlines()]
        assert len(records)==16*len(CONDITIONS)
        assert len({(x['case_id'],x['condition']) for x in records})==80
        assert all(x['backend']==backend and x['model'] is None for x in records)
        assert all(x['pre_repeat_exit_codes']==[1,1,1] for x in records)
        assert all(x['pre_pytest_returncode']!=0 for x in records)
        for r in records:
            if r['test_passed']:
                assert r['correct_diagnosis']
                assert r['patch_changed']
                assert r['post_repeat_exit_codes']==[0,0,0]
                assert r['post_pytest_returncode']==0
