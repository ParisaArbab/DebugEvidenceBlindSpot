# Reproducible results and provenance

## Real local measured executions, non-LLM only

- `live_diagnostic_rule.jsonl`: 80 instrumented-rule agent decisions, including patch checks, never model generations.
- `live_always_a.jsonl`: 80 always-A agent decisions, including patch checks, never model generations.
- Corresponding `_summary.json`: aggregated counts from those JSONL records.
- `live_controls.png`: local visualization of the two non-LLM control policies; regenerate with `python write_live_report.py` if absent.
- `live_*_part{0,1,2,3}.jsonl`: the validated independent run shards.
- `_run_*.log`, `_guess*.log`: local progress logs, not result records.

## Not yet available

- `live_qwen_all.jsonl`: produced only when Qwen actually runs on GPU with 80 decisions.
- `live_qwen_guardrail.jsonl`: optional alternate prompt instruction run.
- `live_qwen_metrics.json`: created only by `verify_model_results.py` after real model outputs exist.

**No model metrics exist in this directory. Do not report the rule-based control accuracy as Qwen performance.**
