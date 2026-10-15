"""Run controlled five-condition evaluation on an open-weight local HF LLM.

Usage (Colab GPU):
  python evaluate.py --max-families 12 --output results/qwen3_4b_12families.jsonl
  python evaluate.py --max-families 0 --output results/qwen3_4b_full.jsonl

No evaluation scores are written unless a real model successfully generates them.
"""
import argparse
import json
import os
import random
import re
import time
from collections import defaultdict
from pathlib import Path

from generate_data import prompt_view

ROOT = Path(__file__).resolve().parent
MODEL = 'Qwen/Qwen3-4B-Instruct-2507'
CONDITIONS=('raw','tail_only','cause_preserved','decoy_only','restored')
SYSTEM_EVIDENCE_AWARE = (
 'You are a debugging assistant. Identify the underlying cause from a failing test log, '
 'not from intuition about which bug sounds more common. You have exactly two candidate causes. '
 'Treat automated triage guesses as unverified. If the available log cannot distinguish '
 'between A and B, choose NEED_LOG to request the earlier diagnostic line, instead of guessing. '
 'Reply with exactly one JSON object, no Markdown, no extra prose. '
 'Format: {"decision":"A|B|NEED_LOG", "evidence":"one brief sentence quoting the diagnostic clue, '
 'or stating what is missing"}. Do not invent log lines.'
)


SYSTEM_BASELINE = (
 'You are a software-engineering AI agent diagnosing a failing test. '
 'Read the available log and decide which candidate root cause is best supported. '
 'You may answer NEED_LOG if more evidence is required. '
 'Reply with exactly one JSON object, no Markdown or other prose, with '
 '{"decision":"A|B|NEED_LOG","evidence":"one short supporting observation"}. '
 'Do not invent log lines.'
)


def user_prompt(case,condition):
  return (f'Possible cause A: {case["candidate_A"]}\n'
          f'Possible cause B: {case["candidate_B"]}\n'
          f'Which is supported by the available test output?\n\n'
          f'BEGIN TOOL OUTPUT\n{prompt_view(case,condition)}\nEND TOOL OUTPUT')

def parse_decision(text):
  text=text.strip()
  # Models sometimes emit text outside JSON. Reject invalid and record it.
  try:
    obj=json.loads(text)
  except json.JSONDecodeError:
    match=re.search(r'\{[^{}]*\}',text,re.S)
    if match:
      try: obj=json.loads(match.group(0))
      except json.JSONDecodeError: return 'INVALID',None
    else: return 'INVALID',None
  if not isinstance(obj,dict): return 'INVALID',None
  decision=obj.get('decision')
  if not isinstance(decision,str):return 'INVALID',None
  decision=decision.strip().upper()
  if decision not in {'A','B','NEED_LOG'}:return 'INVALID',None
  return decision,obj.get('evidence')


def load_llm(name, quantization):
  import torch
  from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
  from huggingface_hub import model_info
  if not torch.cuda.is_available():
    raise RuntimeError('CUDA GPU unavailable. Run in a Colab GPU runtime, Modal, or your own CUDA GPU. '
                       'This evaluator does not replace a model run with mock results.')
  revision=model_info(name).sha
  tok=AutoTokenizer.from_pretrained(name, revision=revision, trust_remote_code=False)
  config={'device_map':'auto','torch_dtype':torch.float16,'low_cpu_mem_usage':True,'revision':revision}
  if quantization=='4bit':
    config['quantization_config']=BitsAndBytesConfig(load_in_4bit=True,
      bnb_4bit_quant_type='nf4', bnb_4bit_compute_dtype=torch.float16,
      bnb_4bit_use_double_quant=True)
  model=AutoModelForCausalLM.from_pretrained(name,**config)
  model.eval()
  return tok,model,revision


def infer(tok,model,case,condition,max_new_tokens,system_instruction):
  import torch
  msgs=[{'role':'system','content':system_instruction},
        {'role':'user','content':user_prompt(case,condition)}]
  inputs=tok.apply_chat_template(msgs,tokenize=True,add_generation_prompt=True,
                                 return_tensors='pt',return_dict=True)
  prompt_tokens=inputs['input_ids'].shape[1]
  inputs=inputs.to(model.device)
  started=time.perf_counter()
  with torch.inference_mode():
    gen=model.generate(**inputs,max_new_tokens=max_new_tokens,do_sample=False,
                       pad_token_id=tok.eos_token_id)
  latency=round(time.perf_counter()-started,4)
  out_ids=gen[0][prompt_tokens:]
  raw_text=tok.decode(out_ids,skip_special_tokens=True).strip()
  decision,evidence=parse_decision(raw_text)
  return {'decision':decision,'evidence':evidence,'response':raw_text,
          'prompt_tokens':prompt_tokens,'generated_tokens':len(out_ids),
          'latency_sec':latency}

def main():
  parser=argparse.ArgumentParser()
  parser.add_argument('--model',default=MODEL)
  parser.add_argument('--data',default=str(ROOT/'data'/'paired_cases.jsonl'))
  parser.add_argument('--output',default=str(ROOT/'results'/'actual_generations.jsonl'))
  parser.add_argument('--max-families',type=int,default=12,
                      help='12 for a quick test; 0 for all 24 matched pairs')
  parser.add_argument('--quantization',choices=['4bit','none'],default='4bit')
  parser.add_argument('--max-new-tokens',type=int,default=96)
  parser.add_argument('--seed',type=int,default=42)
  parser.add_argument('--prompt-mode',choices=['baseline','evidence_aware'],default='baseline',
                      help='Baseline offers optional NEED_LOG, evidence-aware explicitly discourages guessing')
  args=parser.parse_args()
  random.seed(args.seed)
  import torch
  torch.manual_seed(args.seed)
  torch.backends.cudnn.deterministic=True
  rows=[json.loads(line) for line in Path(args.data).read_text().splitlines() if line.strip()]
  families=sorted({r['family_id'] for r in rows})
  if args.max_families>0:families=families[:args.max_families]
  cases=[r for r in rows if r['family_id'] in families]
  tok,model,revision=load_llm(args.model,args.quantization)
  meta={'prompt_mode':args.prompt_mode,'model':args.model,'resolved_model_revision':revision,'quantization':args.quantization,'torch':torch.__version__,'gpu':torch.cuda.get_device_name(0),'seed':args.seed,'cases':len(cases),'conditions':list(CONDITIONS),'max_new_tokens':args.max_new_tokens,'decoding':'greedy, do_sample=False'}
  (ROOT/'results'/'run_metadata.json').write_text(json.dumps(meta,indent=2)+'\n')
  out=Path(args.output);out.parent.mkdir(exist_ok=True,parents=True)
  print(f'Running {len(cases)} cases x {len(CONDITIONS)} conditions = {len(cases)*len(CONDITIONS)} real model calls in {args.prompt_mode} mode')
  system_instruction=SYSTEM_BASELINE if args.prompt_mode=='baseline' else SYSTEM_EVIDENCE_AWARE
  with out.open('w',encoding='utf-8') as file:
    for i,case in enumerate(cases,1):
      for condition in CONDITIONS:
        result=infer(tok,model,case,condition,args.max_new_tokens,system_instruction)
        record={
         'model':args.model,'model_revision':revision,'prompt_mode':args.prompt_mode,'quantization':args.quantization,'seed':args.seed,
         'case_id':case['case_id'],'family_id':case['family_id'],'twin':case['twin'],
         'condition':condition,'gold':case['gold'],**result}
        file.write(json.dumps(record,ensure_ascii=False)+'\n');file.flush()
      print(f'{i}/{len(cases)} complete: {case["case_id"]}',flush=True)
  print('Wrote real model outputs to',out)

if __name__=='__main__':main()
