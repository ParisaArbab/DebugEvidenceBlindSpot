"""Create and populate a PUBLIC Hugging Face Bucket with local CED artifacts.

Requires an HF account with a write token; `hf auth login` first.
Deliberately does not upload model weights, tokens, caches, or any files outside allowlist.
"""
from pathlib import Path
import argparse
import json
from huggingface_hub import create_bucket, sync_bucket, bucket_info, whoami

ROOT=Path(__file__).resolve().parent
ALLOWED=['README.md','SUBMISSION.md','MODEL_REFERENCE.json','requirements.txt','generate_data.py','evaluate.py','analyze.py',
         'smoke_test.py','publish_bucket.py','CED_Qwen3_4B_Colab.ipynb',
         'data/paired_cases.jsonl','data/manifest.json',
         'results/actual_generations.jsonl','results/metrics.json','results/run_metadata.json',
         'results/measured_rates.png','results/evidence_aware_generations.jsonl']

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--bucket-name',default='causal-evidence-deletion-debugging')
    p.add_argument('--allow-unmeasured',action='store_true',help='Publish preparatory artifacts without measured results')
    args=p.parse_args()
    if not args.allow_unmeasured:
        required=[ROOT/'results/actual_generations.jsonl',ROOT/'results/metrics.json']
        missing=[str(f) for f in required if not f.exists() or not f.stat().st_size]
        if missing:raise SystemExit('No completed model evaluation yet. Run evaluate.py and analyze.py first, or pass --allow-unmeasured to publish study design only. Missing: '+str(missing))
        metrics=json.loads((ROOT/'results/metrics.json').read_text())
        if metrics.get('status')!='MEASURED_FROM_MODEL_GENERATIONS' or metrics.get('n_generations')!=240 or metrics.get('n_families')!=24:
            raise SystemExit('Invalid results status; refusing to publish fabricated scores.')
    user=whoami()['name']
    url=create_bucket(f'{user}/{args.bucket_name}',private=False,exist_ok=True)
    info=bucket_info(url.bucket_id)
    if info.private:
        raise SystemExit('Bucket with this name is private. Create a different new PUBLIC bucket; existing bucket unchanged.')
    # Sync a controlled staging directory, never copy notebook authentication data.
    from tempfile import TemporaryDirectory
    import shutil
    with TemporaryDirectory() as temp:
        dest=Path(temp)
        for rel in ALLOWED:
            src=ROOT/rel
            if src.is_file():
                out=dest/rel;out.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(src,out)
        sync_bucket(str(dest),f'hf://buckets/{url.bucket_id}')
    print('Public bucket published:',url.url)

if __name__=='__main__': main()
