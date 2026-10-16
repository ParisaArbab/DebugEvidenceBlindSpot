# Live Causal Evidence Deletion: completed Qwen3-4B experiment

**Study completed:** October 15, 2026  
**Model:** [`Qwen/Qwen3-4B-Instruct-2507`](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), 4B parameters  
**Resolved model revision:** `cdbee75f17c01a7cc42f958dc650907174af0554`  
**Execution:** AIScalar, NVIDIA A100 80GB, 4-bit NF4 model loading, greedy decoding  
**Verification:** Both JSONL files passed `verify_model_results.py`; `analyze_actual_results.py` also checked all matched-world observation hashes and cross-run case IDs.

## Research question

When an AI coding agent receives a compressed or misleading tool output, can it tell whether the evidence needed to diagnose a bug is missing? Can it still reason correctly after the relevant evidence is restored?

This comes from research on context optimization for AI debugging agents. A shorter log can save time and tokens, but removing one important line can make two different bugs look the same. A model may still give a confident answer, or trust an earlier summarizer's unverified guess.

## Experimental design

- **Eight small executable Python bug families**, each constructed as a counterfactual pair with different correct root causes: **16 bugs** total.
- **Five observation conditions** for each bug: `raw` full noisy log, `tail_only` deleted causal evidence, `causal_slice` short log preserving diagnostic evidence, `decoy_summary` deleted evidence plus an identical unverified suggestion that A is likely, and `retrieval_enabled` deleted evidence with optional targeted retrieval.
- **Two prompting regimes** with the same 4B model and same examples: baseline debugging instruction and evidence-aware instruction that explicitly says to ask for missing evidence and distrust unverified summaries.
- **160 recorded decisions** (16 bugs × 5 conditions × 2 prompting regimes); model responses and token counts are saved in the original JSONL files. The retrieval condition may include a second model generation after `NEED_LOG`.
- **Actual code execution:** Each buggy program first failed three repeated runs and pytest; the agent chose A, B, or `NEED_LOG`. The harness applied the corresponding prewritten one-line patch in a temporary copy and checked three repeated runs and pytest. This is a **controlled patch-selection** study, not free-form patch generation or SWE-bench.
- Under `tail_only`, `decoy_summary`, and the initial `retrieval_enabled` observation, the two worlds in each family have exactly identical observation hashes, checked independently. A correct-looking decision from these views alone cannot reliably distinguish the worlds.

## Main results, independently recalculated from raw JSONL files

**Successful verified patches** (not the best metric for evidence-deleted conditions, where abstention is desirable):

| Condition | Baseline | Evidence-aware |
|---|---:|---:|
| Raw tool output | 11/16 (68.75%) | 8/16 (50%) |
| Deleted evidence (`tail_only`) | 2/16 (12.5%) | 0/16 (0%) |
| Causal diagnostic slice | 13/16 (81.25%) | 10/16 (62.5%) |
| Missing evidence plus misleading summary | 8/16 (50%) | 1/16 (6.25%) |
| Retrieval permitted | 11/16 (68.75%) | 10/16 (62.5%) |

**Evidence requests and unsafe guesses**:

| Condition | Baseline requested evidence | Evidence-aware requested evidence |
|---|---:|---:|
| Deleted evidence | 12/16 | 16/16 |
| Misleading summary | 0/16 | 14/16 |
| Retrieval permitted, before retrieval | 12/16 | 16/16 |

For the misleading-summary condition, the baseline chose **A in all 16 paired worlds**. Thus it repaired all eight A worlds and none of the eight B worlds. This is a direct sign of strong attraction to the unverified "A" suggestion. It does **not** show 50% legitimate debugging accuracy. The evidence-aware prompt asked for evidence in 14 worlds; the remaining two guesses were both B, and only one happened to be correct.

For tail-only evidence, the baseline made four unsupported B guesses and abstained 12 times, while the evidence-aware prompt abstained 16 times. Therefore **0 repairs for evidence-aware tail-only is a good refusal outcome, not a failed diagnosis**.

In the retrieval condition, the baseline requested evidence 12 times and repaired 9 of those 12 after it was supplied; two other repairs came from unsupported guesses without retrieval. The evidence-aware prompt requested evidence 16 times and repaired 10 after seeing the retrieved diagnostics. The model therefore **still sometimes misinterprets adequate evidence**.

The baseline causal slice produced **13/16 verified fixes vs 11/16 for full logs**, while average visible log length fell from 2,842.8 to 106.8 characters (about **96.2% shorter**). Initial model input fell from an average of 1,077.5 to 170.5 tokens (**84.2% fewer prompt tokens**, including fixed instructions). The evidence-aware causal slice also exceeded evidence-aware raw logs (10/16 vs 8/16). These two-case differences are descriptive, not evidence of statistical superiority with only eight independent bug families.

## Direct inspection of model behavior

### Example 1: The model copies a misleading summary

**Case:** `pagination_B`. The actual cause is **B: cursor never advances**. The short observation contains no causal diagnostic line, only the common failure and an unverified statement that cause A is likely.

- Baseline response: `{"decision":"A","evidence":"The export loop is limited to one page, as indicated by the assertion error during contract validation, suggesting incomplete data retrieval due to pagination constraints."}`
- Evidence-aware response: chose **B**, also unsupported, arguing that the cursor must be stuck despite missing evidence.
- Verified outcome: both decisions came from insufficient observation; the baseline patch was wrong and the evidence-aware patch happened to pass. A model should have requested the missing diagnostic trace.

### Example 2: Evidence present, but the diagnosis contradicts it

**Case:** `graph_edges_B`. The true cause is **B: forward write edges are removed**. The raw log showed `KEEP_REVERSE=True` and `KEEP_WRITES=False`.

- Baseline: chose **B** and repaired the case.
- Evidence-aware: chose **A** and claimed the failure was more likely due to missing reverse edges **after explicitly stating that reverse edges were preserved**.
- This is a *reasoning-on-available-evidence* failure, not missing-evidence failure. The error illustrates why evidence sufficiency and causal interpretation should be evaluated separately.

### Example 3: Diagnosing a familiar explanation instead of the actual setting

**Case:** `invoice_total_A`. The true cause is **A: wrong cents conversion**. The raw log showed `CENTS_SCALE=1`, although the known-good value is 100, and `DISCOUNT_SIGN=-1`, already the correct sign.

- Both prompts chose **B**, claiming the discount had the wrong sign, despite reporting that the discount was being subtracted.
- Both selected patches failed. This is a concrete example of a common-sense story overriding the observed configuration.

### Example 4: Some apparent failures are output truncation

`live_eval.py` allowed a maximum of **120 generated tokens** per model response. An incomplete JSON response is marked `INVALID` and cannot trigger a patch. There were **3 final invalid responses under the baseline** and **6 under the evidence-aware prompt**. Every recorded invalid final response reached the 120-token cap (in its final generation). These are formatting/truncation failures, not necessarily wrong causal diagnoses. For example, the baseline response to `json_cleanup_B` ended mid-sentence and was rejected by the parser.

This matters for the interpretation of the lower evidence-aware repair count: stronger instructions sometimes produced longer explanations and more clipped outputs. A follow-up should use structured decoding or a larger token budget and report invalid-format rates separately.

## Proposed path forward

1. **Curate paired, executable data.** Collect actual CI failures, debugging tool traces, and verified minimal fixes. Create matched pairs with the same high-level error but different root causes. For each pair, annotate the decisive evidence, missing evidence, source location, verified patch, and minimal retrieval query.
2. **Train evidence-aware behavior.** Use supervised fine-tuning or QLoRA on full, causal-slice, missing-evidence, and deceptive-summary variants. Reward valid abstention when evidence cannot distinguish causes, and reward correct diagnosis only after adequate evidence is present. Add preference examples penalizing confident answers based solely on unreliable summaries.
3. **Change the agent workflow.** Separate an *evidence sufficiency gate* from the actual debugging model. Preserve diagnostic provenance and offsets during compression, use program slicing to identify relevant code and observations, retrieve targeted missing logs on demand, and require post-patch execution validation.
4. **Evaluate both capabilities.** Report unsupported guess rate under identical observations, evidence request rate, successful repairs when evidence exists, reliability after retrieval, token and latency costs, and invalid output rate. Include held-out repositories and ablations for label order, decoy wording, and compressor type.

## Limits and validity threats

- Only **eight designed bug families**; A/B worlds are paired, not independent. Numbers should not be generalized to production coding agents.
- The challenge measures **choosing one of two predefined fixes**. It does not evaluate writing original patches, navigating large repositories, or recovering from arbitrary tool failures.
- The decoy always recommended **A**. Its strong effect is real in this setup, but future experiments must counterbalance recommendation labels and vary wording to distinguish anchoring to the summary from broader label bias.
- Model output truncation at 120 tokens creates a format-related confound. Decoding is deterministic within a prompt, but one run per configuration is not enough to estimate robustness under diverse prompts or programs.
- Evidence deletion is controlled. The current benchmark uses intentionally injected settings and artificial repeated heartbeat lines, not mined production traces.
- Retrieval-enabled results depend on a single fixed retrieval action, not an agent autonomously searching arbitrary code or logs.

## Reproduction and source files

- `results/live_qwen_all.jsonl`: all 80 baseline decisions, raw model responses, model revision, token counts and patch validation.
- `results/live_qwen_evidence_aware.jsonl`: same 80 cases with evidence-aware instructions.
- `results/live_qwen_metrics.json`, `results/live_qwen_evidence_aware_metrics.json`: original verification outputs.
- `results/analysis_metrics.json`, `results/case_level_comparison.csv`: independently regenerated metrics and paired response table.
- `analyze_actual_results.py`: regeneration and matched-world checks.
- `live_bugs/`, `live_eval.py`, `build_live_cases.py`, `verify_model_results.py`: executable dataset and model evaluation implementation.
- Model weights are not republished; reproducibility uses the exact upstream model revision recorded above.
