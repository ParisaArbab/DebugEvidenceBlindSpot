# DebugEvidenceBlindSpot

**Research question:** Can an AI debugging agent recognize when the causal evidence behind a failure has been removed or replaced by an unreliable tool summary?

This is a systematic model inspection project inspired by research on context optimization for AI coding agents.

## Status: Qwen3-4B evaluation completed and verified

The executable benchmark ran on an AIScalar A100 GPU on **October 15, 2026** with `Qwen/Qwen3-4B-Instruct-2507` (4 billion parameters), resolved revision `cdbee75f17c01a7cc42f958dc650907174af0554`. We recorded **160 real model decisions** (80 standard prompting, 80 evidence-aware prompting). The dataset contains **eight families of executable Python bugs**, with two causes per family, tested under five log conditions.

| Log condition | Standard prompt: verified repairs | Evidence-aware prompt: verified repairs |
|---|---:|---:|
| Full log | 11/16 | 8/16 |
| Critical evidence removed | 2/16 | 0/16 |
| Short log preserving causal evidence | 13/16 | 10/16 |
| Evidence missing with misleading A summary | 8/16 | 1/16 |
| Missing evidence with retrieval | 11/16 | 10/16 |

**For missing evidence, repair count is not a reliability metric by itself.** Asking for the missing log is appropriate. The standard model requested missing evidence in 12/16 cases without a decoy, but 0/16 cases with an unverified summary suggesting A. The evidence-aware model requested evidence in 16/16 and 14/16 cases, respectively. In the misleading-summary case, the standard model chose A in every one of the 16 worlds, so eight repairs were accidental matches to the decoy.

**Important caveats:** This is a small controlled **patch-selection** benchmark, not autonomous end-to-end repair or SWE-bench. Some malformed model generations resulted from the 120-token output cap. See [`LIVE_EXPERIMENT_REPORT.md`](LIVE_EXPERIMENT_REPORT.md) for observed responses, exact methods, limits, and proposed training/architecture changes.

## Reproduce the analysis (no GPU needed)

```bash
python smoke_test.py
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_live_harness.py
python analyze_actual_results.py
```

The final command checks both real JSONL files, verifies that counterfactual paired worlds have identical missing-evidence observations, and writes:

- `results/analysis_metrics.json`, detailed per-condition metrics, token counts, invalid-output counts, and paired comparison
- `results/case_level_comparison.csv`, 80 paired comparisons of raw responses and verified patch outcomes

## Run your own GPU evaluation

Recommended on AIScalar or an equivalent NVIDIA GPU:

```bash
# Prefer scratch storage for downloaded model weights if your home quota is small
export HF_HOME=/scratch/$USER/hf_cache
export TMPDIR=/scratch/$USER/tmp
export CUDA_VISIBLE_DEVICES=0
python -m pip install -r requirements.txt

python live_eval.py --backend qwen --repeat 3 --output results/live_qwen_all.jsonl
python live_eval.py --backend qwen --prompt-mode evidence_aware --repeat 3 --output results/live_qwen_evidence_aware.jsonl

python verify_model_results.py results/live_qwen_all.jsonl --save results/live_qwen_metrics.json
python verify_model_results.py results/live_qwen_evidence_aware.jsonl --save results/live_qwen_evidence_aware_metrics.json
python analyze_actual_results.py
```

A complete live model run produces 80 decisions per prompting mode. Runs are deterministic greedy-decoding experiments, but outcomes are not asserted to generalize to other models.

## Data and files

| Folder/file | Purpose |
|---|---|
| `live_bugs/` | Eight two-world executable Python bug families and their `manifest.json` |
| `live_eval.py` | Execute real failures, collect logs, ask Qwen, select one of two known patches, retest |
| `results/live_qwen_all.jsonl` | 80 recorded baseline outputs and verification |
| `results/live_qwen_evidence_aware.jsonl` | 80 recorded evidence-aware outputs and verification |
| `results/analysis_metrics.json` | Detailed independently derived metrics |
| `results/case_level_comparison.csv` | All 80 paired prompt-setting comparisons |
| `analyze_actual_results.py` | Recalculate and audit results |
| `PUBLICATION_STEPS.md` | Transfer to AIScalar, verification, public Bucket publishing |
| `results/verified_repairs_comparison.png`, `results/missing_evidence_requests.png` | Comparison figures |
| `LIVE_EXPERIMENT_REPORT.md` | Full method, model examples, findings, limits |
| `SUBMISSION.md` | First-person answers to questions 1, 2 and 3 |
| `data/paired_cases.jsonl` | Supplementary 24-family synthetic non-executable CED dataset; **no GPU results are claimed for this supplementary dataset** |

**Model weights:** Use the [original model repository](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), pinned to revision `cdbee75f17c01a7cc42f958dc650907174af0554`. We do not duplicate the model weights in this evaluation archive.

## Public Hugging Face Bucket

This project includes `publish_live_bucket.py`. It checks that **both** Qwen runs are complete and verified, uploads dataset/code/measurements/README to a **public** Hugging Face Bucket, then prints the verified URL. The Bucket requires a write-capable Hugging Face account login to publish.

```bash
python -m pip install --upgrade 'huggingface_hub>=1.5.0'
hf auth login  # authenticate privately; do not put your token in code or chat
python publish_live_bucket.py --bucket-name debug-evidence-blindspot-live
```

The expected Bucket namespace comes from the authenticated Hugging Face account.
