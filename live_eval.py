"""Execute live bugs, run an agent decision loop, apply selected patches, retest.

This is a *controlled patch-selection* benchmark, NOT free-form code generation.
Backend "diagnostic_rule" is a transparent programmatic upper-bound control,
NOT an LLM. "always_a" is a naive guess control. "qwen" runs an actual HF LLM
and requires a separate CUDA GPU with Transformers installed.
"""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
from collections import defaultdict

ROOT = Path(__file__).resolve().parent
LIVE = ROOT/'live_bugs'
CONDITIONS = ('raw','tail_only','causal_slice','decoy_summary','retrieval_enabled')
MODEL_ID='Qwen/Qwen3-4B-Instruct-2507'
EVIDENCE_AWARE_INSTRUCTION = (
    'You are diagnosing a real Python test failure. Given two possible root causes, '
    'choose A or B ONLY if the execution evidence distinguishes them. '
    'If the available logs cannot distinguish them, return NEED_LOG. '
    'Do not trust unverified triage guesses. Return exactly JSON like '
    '{"decision":"A", "evidence":"brief diagnostic reason"}. '
    'Valid decisions: A, B, NEED_LOG. Avoid extra text.'
)

BASELINE_INSTRUCTION = (
    'You are a software debugging agent. Diagnose the most likely root cause '
    'from the test log and two candidate explanations. You may request more log '
    'information if necessary. Return exactly JSON as '
    '{"decision":"A", "evidence":"brief observation"}. '
    'Valid decisions: A, B, NEED_LOG. Do not invent runtime evidence.'
)

def run_command(args, cwd, timeout=12):
    import os
    env=os.environ.copy()
    env['PYTEST_DISABLE_PLUGIN_AUTOLOAD']='1'
    p = subprocess.run(args,cwd=cwd,text=True,capture_output=True,timeout=timeout,env=env)
    return {'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr}

def run_trace(folder):
    r=run_command([sys.executable,'-B','trace_run.py'],folder)
    assert r['returncode'] in (0,1), (folder,r)
    return r

def run_pytest(folder):
    return run_command([sys.executable,'-m','pytest','-q','-p','no:cacheprovider','test_app.py'],folder)

def trace_views(trace_text):
    lines=trace_text.strip().splitlines()
    assert len(lines)>=4, lines
    diagnostic=[l for l in lines if l.startswith('[DIAGNOSTIC]')]
    failure=next(l for l in lines if l.startswith('[FAIL]'))
    # Tool-output compression discards the first diagnostic observations.
    tail='[RUN] prior tool output summarized; earlier diagnostic lines omitted\n'+failure
    # The same unverified triage guess is given to both counterfactual worlds.
    decoy='[UNVERIFIED TRIAGE SUMMARY] A is the probable root cause (not validated).\n'+tail
    # Noise is noncausal, deterministic, and identical across worlds.
    noise='\n'.join(f'[INFO] heartbeat tick={i:03d}, worker=healthy' for i in range(1,65))
    raw='\n'.join(lines[:-1])+'\n'+noise+'\n'+failure
    sliced='\n'.join(diagnostic)+'\n'+failure
    return {'raw':raw,'tail_only':tail,'causal_slice':sliced,
            'decoy_summary':decoy,'retrieval_enabled':tail},'\n'.join(diagnostic)

def prompt(case, log):
    return (f'Test: {case["test_name"]}\n'
            f'Possible root cause A: {case["candidate_A"]}\n'
            f'Possible root cause B: {case["candidate_B"]}\n'
            'Choose the root cause supported by the runtime log or request earlier evidence.\n'
            f'--- TOOL OUTPUT ---\n{log}\n--- END ---')

class DiagnosticRule:
    """Reads instrumented live diagnostics against known nominal settings."""
    name='diagnostic_rule'
    def decide(self,case,log):
        observed={}
        for match in re.finditer(r'^\[DIAGNOSTIC\] ([A-Z_]+)=(.+)$',log,re.M):
            try: observed[match.group(1)]=ast.literal_eval(match.group(2))
            except (SyntaxError,ValueError): pass
        a,b=case['patch_A'],case['patch_B']
        if a['key'] not in observed or b['key'] not in observed:
            return {'decision':'NEED_LOG','evidence':'No cause-distinguishing runtime diagnostics','prompt_tokens':None,'generated_tokens':None,'latency_sec':0}
        expect=lambda text: ast.literal_eval(text)
        if observed[a['key']]==expect(a['before']) and observed[b['key']]==expect(b['after']):
            answer='A'
        elif observed[a['key']]==expect(a['after']) and observed[b['key']]==expect(b['before']):
            answer='B'
        else:answer='NEED_LOG'
        return {'decision':answer,'evidence':'Instrumented settings compared with known-good settings',
                'prompt_tokens':None,'generated_tokens':None,'latency_sec':0}

class AlwaysA:
    name='always_a'
    def decide(self,case,log):
        return {'decision':'A','evidence':'Always-A control, ignores all evidence',
                'prompt_tokens':None,'generated_tokens':None,'latency_sec':0}

class Qwen:
    name='qwen'
    def __init__(self,model_id=MODEL_ID,prompt_mode='baseline'):
        self.prompt_mode=prompt_mode
        import torch
        if not torch.cuda.is_available():
            raise RuntimeError('No CUDA GPU. Qwen scores cannot be obtained in this environment. Use LIVE_Qwen3_4B_Colab.ipynb.')
        from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
        from huggingface_hub import model_info
        self.revision=model_info(model_id).sha
        self.tokenizer=AutoTokenizer.from_pretrained(model_id,revision=self.revision)
        conf=BitsAndBytesConfig(load_in_4bit=True,bnb_4bit_quant_type='nf4',
                                 bnb_4bit_compute_dtype=torch.float16,bnb_4bit_use_double_quant=True)
        self.model=AutoModelForCausalLM.from_pretrained(model_id,revision=self.revision,
                       quantization_config=conf,device_map='auto',torch_dtype=torch.float16)
        self.model.eval()
    def decide(self,case,log):
        import torch
        from evaluate import parse_decision
        p=prompt(case,log)
        instruction=BASELINE_INSTRUCTION if self.prompt_mode=='baseline' else EVIDENCE_AWARE_INSTRUCTION
        messages=[{'role':'system','content':instruction},{'role':'user','content':p}]
        toks=self.tokenizer.apply_chat_template(messages,tokenize=True,add_generation_prompt=True,
                                               return_tensors='pt',return_dict=True).to(self.model.device)
        n=toks['input_ids'].shape[1]
        t=time.perf_counter()
        with torch.inference_mode():
            gen=self.model.generate(**toks,max_new_tokens=120,do_sample=False,
                                    pad_token_id=self.tokenizer.eos_token_id)
        elapsed=time.perf_counter()-t
        outputs=gen[0][n:]
        response=self.tokenizer.decode(outputs,skip_special_tokens=True)
        decision,evidence=parse_decision(response)
        return {'decision':decision,'evidence':evidence,'raw_response':response,
                'prompt_tokens':n,'generated_tokens':len(outputs),'latency_sec':round(elapsed,4)}

def apply_patch(folder,case,decision):
    patch=case['patch_'+decision]
    original=(folder/'app.py').read_text()
    pattern=rf'^{re.escape(patch["key"])}\s*=\s*{re.escape(patch["before"])}$'
    replaced,n=re.subn(pattern,f'{patch["key"]} = {patch["after"]}',original,flags=re.M)
    if n!=1:
        # Wrong patch may already be good in counterfactual opposite world.
        # Leave source alone, giving explicit no-change evidence.
        return False, hashlib.sha256(original.encode()).hexdigest()
    (folder/'app.py').write_text(replaced)
    return True, hashlib.sha256(replaced.encode()).hexdigest()

def evaluate_repair(case,choice,repeat=3):
    src=ROOT/case['relative_path']
    with tempfile.TemporaryDirectory(prefix='ced_live_patch_') as tmp:
        dst=Path(tmp)
        for fname in ('app.py','test_app.py','trace_run.py'):
            shutil.copyfile(src/fname,dst/fname)
        changed,new_sha=apply_patch(dst,case,choice)
        runs=[run_trace(dst) for _ in range(repeat)]
        pytest_result=run_pytest(dst)
        ok=changed and all(r['returncode']==0 for r in runs) and pytest_result['returncode']==0
        return {'patch_changed':changed,'patch_sha256':new_sha,'test_passed':ok,
                'post_repeat_exit_codes':[r['returncode'] for r in runs],
                'post_pytest_returncode':pytest_result['returncode']}

def verify_originals(cases,repeat=3):
    validated={}
    for case in cases:
        folder=ROOT/case['relative_path']
        original=(folder/'app.py').read_bytes()
        sha=hashlib.sha256(original).hexdigest()
        assert sha==case['source_sha256'],f'Case file changed: {case["case_id"]}'
        traces=[run_trace(folder) for _ in range(repeat)]
        assert all(r['returncode']==1 for r in traces),case['case_id']
        assert len({r['stdout'] for r in traces})==1,'Nondeterministic trace'
        py=run_pytest(folder)
        assert py['returncode']!=0,(case['case_id'],py)
        validated[case['case_id']]={'trace':traces[0]['stdout'],
           'pre_repeat_exit_codes':[r['returncode'] for r in traces],
           'pre_pytest_returncode':py['returncode']}
    # Identical observations in both worlds when diagnostic evidence is deleted.
    for family in {c['family_id'] for c in cases}:
        pair=sorted((c for c in cases if c['family_id']==family),key=lambda c:c['world'])
        if len(pair)<2:continue
        a,_=trace_views(validated[pair[0]['case_id']]['trace'])
        b,_=trace_views(validated[pair[1]['case_id']]['trace'])
        assert a['tail_only']==b['tail_only'],family
        assert a['decoy_summary']==b['decoy_summary'],family
        assert a['raw']!=b['raw'],family
        assert a['causal_slice']!=b['causal_slice'],family
    return validated

def evaluate(backend='diagnostic_rule',max_families=0,repeat=3,output=None,verify=True,family_offset=0,prompt_mode='baseline'):
    cases=json.loads((LIVE/'manifest.json').read_text())
    families=sorted({x['family_id'] for x in cases})
    families=families[family_offset:]
    if max_families: families=families[:max_families]
    cases=[c for c in cases if c['family_id'] in families]
    print(f'Validating {len(cases)} actual buggy projects x {repeat} reproductions...',flush=True)
    agent=Qwen(prompt_mode=prompt_mode) if backend=='qwen' else {'diagnostic_rule':DiagnosticRule,'always_a':AlwaysA}[backend]()
    original=verify_originals(cases,repeat) if verify else {
        c['case_id']:{'trace':run_trace(ROOT/c['relative_path'])['stdout']} for c in cases}
    patch_cache={}
    results=[]
    for idx,case in enumerate(cases,1):
        views,diagnostic=trace_views(original[case['case_id']]['trace'])
        for condition in CONDITIONS:
            log=views[condition]
            before=agent.decide(case,log)
            final=before
            retrieved=False
            if condition=='retrieval_enabled' and before['decision']=='NEED_LOG':
                retrieved=True
                final=agent.decide(case,log+'\n[RETRIEVED EARLIER EVIDENCE]\n'+diagnostic)
            choice=final['decision']
            if choice in ('A','B') and (case['case_id'],choice) not in patch_cache:
                patch_cache[(case['case_id'],choice)]=evaluate_repair(case,choice,repeat)
            patch=patch_cache[(case['case_id'],choice)] if choice in ('A','B') else {
                'patch_changed':False,'patch_sha256':None,'test_passed':False,
                'post_repeat_exit_codes':[],'post_pytest_returncode':None}
            results.append({
                'backend':backend,'prompt_mode':prompt_mode if backend=='qwen' else 'not_applicable',
                'model':MODEL_ID if backend=='qwen' else None,
                'model_revision':getattr(agent,'revision',None),
                'case_id':case['case_id'],'family_id':case['family_id'],'world':case['world'],
                'condition':condition,'gold':case['gold'],
                'initial_decision':before['decision'],'final_decision':choice,
                'retrieved':retrieved,'correct_diagnosis':choice==case['gold'],
                'requested_evidence':before['decision']=='NEED_LOG',
                'observed_log_sha256':hashlib.sha256(log.encode()).hexdigest(),
                'observed_log_characters':len(log),
                'initial_response':before,'final_response':final,
                'pre_repeat_exit_codes':original[case['case_id']].get('pre_repeat_exit_codes',[]),
                'pre_pytest_returncode':original[case['case_id']].get('pre_pytest_returncode'),
                **patch,
            })
        print(f'  {idx}/{len(cases)} {case["case_id"]} complete',flush=True)
    if output is None:output=ROOT/'results'/f'live_{backend}.jsonl'
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in results))
    summary=summarize(results)
    summary['experimental_backend']=backend
    summary['not_a_model_result']=backend!='qwen'
    summary['replications_per_pre_and_post_validation']=repeat
    summary['model']=MODEL_ID if backend=='qwen' else None
    summary['prompt_mode']=prompt_mode if backend=='qwen' else 'not_applicable'
    summary['model_revision']=getattr(agent,'revision',None)
    summary['observation_generation']='Live subprocess traces; deterministic noise and synthetic triage summaries'
    (output.parent/(output.stem+'_summary.json')).write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)
    return results

def summarize(rows):
    stats={}
    for cond in CONDITIONS:
        sub=[r for r in rows if r['condition']==cond]
        count=len(sub)
        stats[cond]={
            'n':count,
            'correct_diagnosis':sum(r['correct_diagnosis'] for r in sub),
            'successful_verified_repairs':sum(r['test_passed'] for r in sub),
            'requested_evidence_first':sum(r['requested_evidence'] for r in sub),
            'retrievals':sum(r['retrieved'] for r in sub),
            'unsupported_guesses_initial':sum(r['initial_decision'] in ('A','B') for r in sub) if cond in ('tail_only','decoy_summary','retrieval_enabled') else None,
            'mean_initial_log_characters':round(sum(r['observed_log_characters'] for r in sub)/count,1) if count else None,
        }
    return {'total_decision_tasks':len(rows),'unique_bug_cases':len({r['case_id'] for r in rows}),
            'unique_bug_families':len({r['family_id'] for r in rows}),'conditions':stats}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--backend',choices=['diagnostic_rule','always_a','qwen'],default='diagnostic_rule')
    parser.add_argument('--max-families',type=int,default=0)
    parser.add_argument('--repeat',type=int,default=3)
    parser.add_argument('--family-offset',type=int,default=0)
    parser.add_argument('--prompt-mode',choices=['baseline','evidence_aware'],default='baseline')
    parser.add_argument('--output')
    args=parser.parse_args()
    evaluate(args.backend,args.max_families,args.repeat,args.output,
             family_offset=args.family_offset,prompt_mode=args.prompt_mode)
