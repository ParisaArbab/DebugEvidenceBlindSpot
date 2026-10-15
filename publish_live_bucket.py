"""Publish a public HF bucket ONLY once a complete actual 80-call Qwen run exists.

Requires explicit HF authentication in a user-controlled notebook/session.
Does not upload credentials or weights or change GitHub visibility.
"""
from pathlib import Path
import argparse
import shutil
from tempfile import TemporaryDirectory
from verify_model_results import verify

ROOT=Path(__file__).resolve().parent
EXTRA=['README.md','SUBMISSION.md','LIVE_EXPERIMENT_REPORT.md','MODEL_REFERENCE.json',
       'build_live_cases.py','live_eval.py','merge_live_results.py','write_live_report.py',
       'verify_model_results.py','publish_live_bucket.py','build_live_colab.py',
       'LIVE_Qwen3_4B_Colab.ipynb','generate_data.py','evaluate.py','analyze.py',
       'requirements.txt','data/paired_cases.jsonl','data/manifest.json',
       'results/live_diagnostic_rule_summary.json','results/live_always_a_summary.json',
       'results/live_diagnostic_rule.jsonl','results/live_always_a.jsonl',
       'results/live_qwen_all.jsonl','results/live_qwen_metrics.json','results/live_controls.png',
       'live_bugs/manifest.json']

def publish(bucket_name):
    from huggingface_hub import create_bucket,sync_bucket,bucket_info,whoami
    stats=verify(ROOT/'results/live_qwen_all.jsonl')
    if stats['status']!='MEASURED_FROM_QWEN_GENERATIONS':raise RuntimeError('No model study')
    user=whoami()['name']
    bucket_id=f'{user}/{bucket_name}'
    with TemporaryDirectory(prefix='ced_hf_bucket_') as tmp:
        dest=Path(tmp)
        for rel in EXTRA:
            src=ROOT/rel
            if src.is_file():
                p=dest/rel;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p)
        for src in (ROOT/'live_bugs').rglob('*.py'):
            relative=src.relative_to(ROOT)
            p=dest/relative;p.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,p)
        url=create_bucket(bucket_id,private=False,exist_ok=True)
        if bucket_info(url.bucket_id).private:
            raise RuntimeError('Refusing to claim public publication from a private bucket.')
        sync_bucket(source=str(dest),dest=f'hf://buckets/{url.bucket_id}')
    print('Verified public bucket:',url.url)
    return url.url

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--bucket-name',default='debug-evidence-blindspot-live')
    a=p.parse_args();publish(a.bucket_name)
