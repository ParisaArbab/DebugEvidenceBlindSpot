"""Publish an allowlisted, verified evaluation bundle to a PUBLIC HF Bucket.

Run after `hf auth login` on a write-authorized account. Never put tokens in
this script, the dataset, a notebook, or a Git commit. No model weights are
copied; the pinned upstream model reference is included instead.
"""
from __future__ import annotations
import argparse
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from analyze_actual_results import load_verified, summarize, save_case_comparison

ROOT = Path(__file__).resolve().parent
TOP_LEVEL = [
    'README.md', 'SUBMISSION.md', 'LIVE_EXPERIMENT_REPORT.md', 'MODEL_REFERENCE.json', 'PUBLICATION_STEPS.md',
    'build_live_cases.py', 'live_eval.py', 'merge_live_results.py',
    'write_live_report.py', 'verify_model_results.py', 'analyze_actual_results.py',
    'publish_live_bucket.py', 'build_live_colab.py', 'LIVE_Qwen3_4B_Colab.ipynb',
    'CED_Qwen3_4B_Colab.ipynb', 'generate_data.py', 'evaluate.py', 'analyze.py',
    'requirements.txt', 'smoke_test.py', 'build_colab.py', 'plot_actual_results.py'
]
RESULTS = [
    'live_diagnostic_rule_summary.json','live_always_a_summary.json',
    'live_diagnostic_rule.jsonl','live_always_a.jsonl',
    'live_qwen_all.jsonl','live_qwen_metrics.json',
    'live_qwen_evidence_aware.jsonl','live_qwen_evidence_aware_metrics.json',
    'analysis_metrics.json','case_level_comparison.csv','live_controls.png',
    'verified_repairs_comparison.png', 'missing_evidence_requests.png',
]


def create_bundle(destination: Path):
    runs = load_verified()  # strict: rejects missing/non-Qwen/incomplete outputs
    expected_metrics = summarize(runs)
    stats_file = ROOT/'results/analysis_metrics.json'
    import json
    stats_file.write_text(json.dumps(expected_metrics, indent=2) + '\n', encoding='utf-8')
    save_case_comparison(runs)
    for name in TOP_LEVEL:
        src = ROOT / name
        if src.is_file():
            dst = destination / name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for name in RESULTS:
        src = ROOT/'results'/name
        if src.is_file():
            dst = destination/'results'/name
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
    for dirname in ('data', 'live_bugs', 'tests'):
        for src in (ROOT/dirname).rglob('*'):
            if src.is_file() and src.suffix in ('.json', '.jsonl', '.py'):
                dst=destination/src.relative_to(ROOT)
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
    return runs


def publish(bucket_name, preview_only=False):
    # HF bucket APIs require huggingface_hub>=1.5.0.
    from huggingface_hub import bucket_info, create_bucket, sync_bucket, whoami
    with TemporaryDirectory(prefix='ced_hf_export_') as tmp:
        bundle=Path(tmp)
        runs = create_bundle(bundle)
        total=sum(len(rows) for _,rows in runs.values())
        print(f'Local evidence audit passed: {total} recorded Qwen decisions')
        print('Files staged:',len(list(bundle.rglob('*'))),'(including directories)')
        if preview_only:
            print('Preview only, nothing published.')
            for p in sorted(bundle.rglob('*')):
                if p.is_file():print(p.relative_to(bundle))
            return None
        user=whoami()['name']
        bucket_id=f'{user}/{bucket_name}' if '/' not in bucket_name else bucket_name
        # Users explicitly requested a public evaluation; fail if existing bucket is private.
        url=create_bucket(bucket_id,private=False,exist_ok=True)
        if bucket_info(url.bucket_id).private:
            raise RuntimeError('Bucket is private, refusing to proceed as public publication.')
        sync_bucket(str(bundle),f'hf://buckets/{url.bucket_id}')
        info=bucket_info(url.bucket_id)
        if info.private:
            raise RuntimeError('Publication ended with a private bucket!')
        if info.total_files < 1:
            raise RuntimeError('Bucket contains no files; publication not verified.')
        public_url=f'https://huggingface.co/buckets/{url.bucket_id}'
        print('VERIFIED PUBLIC BUCKET:',public_url)
        print('Remote files:',info.total_files)
        return public_url


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--bucket-name',default='debug-evidence-blindspot-live')
    parser.add_argument('--preview-only',action='store_true',help='Validate and stage all artifacts without publishing')
    args=parser.parse_args()
    publish(args.bucket_name,preview_only=args.preview_only)
