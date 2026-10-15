# Experimental report: Live Causal Debugging Under Context Compression

**Experiment date:** 2026-10-15  
**Evaluation status:** Completed local execution tests for two non-LLM control policies; **frontier model inference NOT run**.  
**Source:** `live_bugs/manifest.json`, `results/live_*.jsonl`, `live_eval.py`.  
**Model planned:** [Qwen/Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), 4B parameters, but no model scores currently exist.

## Question
Can a coding agent recognize when tool-output compression has removed the diagnostic information it needs to select the correct code fix, and can targeted retrieval repair that loss?

## What was actually executed
- 8 hand-designed executable Python bug families, 2 worlds per family, **16 failing test projects**; each world contains exactly one configurable defect and a targeted one-line repair.
- 5 evidence conditions per world: `raw`, `tail_only`, `causal_slice`, `decoy_summary`, `retrieval_enabled`.
- **80 end-to-end agent actions per non-LLM control (160 decision tasks in total)**. Agents choose from two candidate fixes or request the missing diagnostics. The harness copies the project into an isolated temporary folder, applies the selected fix, executes the program three times and runs pytest. It does not let the evaluator edit the reference files or tests.
- Before repair, all 16 original projects failed three consecutive reproduction runs and failed pytest. When a correct patch was chosen, three subsequent runs and pytest passed. An incorrect patch was not silently counted as a repair.
- The code genuinely executes the bug and produces its diagnostic values. The final failure message is standardized on purpose so two possible root causes look identical if the earlier diagnostic lines are omitted.
- Test files and execution evidence are available, and the complete dataset can be rebuilt deterministically using `build_live_cases.py`.

## Results: measured local controls, not a model study

| Condition | Diagnostic-rule repair | Guess-A repair | First-step evidence requests |
|---|---:|---:|---:|
| Full log | 16/16 | 8/16 | 0/16 |
| Evidence deleted | 0/16 | 8/16 | 16/16 |
| Causal slice | 16/16 | 8/16 | 0/16 |
| Unverified triage guess | 0/16 | 8/16 | 16/16 |
| Retrieve on request | 16/16 | 8/16 | 16/16 |

The diagnostic rule checks executed variable values against the two known-good settings. It is a **rule-based upper-bound sanity check that uses handcrafted family metadata**. It is **not Qwen, not an LLM, and not an evaluation of frontier-model accuracy**.

The always-guess-A control guesses A in all cases. Each matched family contains one A and one B world, hence 8/16 repairs is no better than chance. Importantly, **all 16 of its guesses on `tail_only` and `decoy_summary` are unsupported**, even though 8 of them happen to repair the defect.

On the evidence-deleted condition, the diagnostic rule requests evidence on 16/16 cases, and does not attempt an unsupported patch. Under the `retrieval_enabled` condition it requests earlier diagnostics 16/16 times, then selects the correct patch and repairs all 16 variants. This is evidence that the **benchmark's retrieval intervention operates as designed**, not proof that Qwen would know to use it.

## Evidence efficiency, measured in characters, not LLM tokens

- Full logs: mean **2842.8 characters**.
- Tail-only logs: mean **118.0 characters**, **95.8% shorter**.
- Causally sliced logs: mean **106.8 characters**, **96.2% shorter**.

Therefore compressing more aggressively is not the same as preserving useful evidence. The real GPU run will record the model's token counts, not approximate them with character counts.

## Validity and limitations

1. **This does not establish a frontier-model blind spot yet.** No downloaded model weights, GPU, or authenticated inference endpoint was available in the preparation environment. Run `LIVE_Qwen3_4B_Colab.ipynb` on a GPU, and include complete raw generations before making any Qwen-specific performance claim.
2. These are small, deliberately built executable examples. They demonstrate a testable information-loss mechanism, not measured failure rates in production repositories or SWE-bench.
3. A controlled patch-choice interface is used; the agent does not synthesize unconstrained unified diffs. This isolates evidence use and debugging decision quality from code-generation difficulty.
4. The rule-based upper bound is given nominal configuration values, so it is not an independent general debugging algorithm. A strong LLM could do better or worse on the actual prompts.
5. The raw condition adds deterministic neutral heartbeat lines. The decoy is a synthetic unverified summary. Neither should be described as mined from a real-world agent's interaction history.
6. Patch repair is evaluated using a one-line targeted change and a single test contract in each project. A full research extension needs multi-test regressions, open-ended patches, larger source trees, held-out bugs, varied compression policies, and possibly adversarial perturbed naming.

## Next experiment, executable with the included notebook

Run the same 16 worlds and 5 conditions with quantized **Qwen3-4B-Instruct-2507**. Record the raw JSON output and resolved model commit revision, prompt/completion token counts, runtime, first choice, retrieval decision, and verified patch-test outcome. Verify paired-world blindness after diagnostic deletion and measure counterfactual reversal with evidence. Use the model's existing ability to request diagnostics rather than tell it the ground-truth world.

Only after these Qwen generations exist may the README be updated with true measured model rates and the public Hugging Face Bucket be published as a completed frontier-model evaluation.
