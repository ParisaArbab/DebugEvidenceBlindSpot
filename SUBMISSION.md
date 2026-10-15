> **Status correction (2026-10-15):** A new runnable benchmark has been implemented and locally tested. The measured numbers in `LIVE_EXPERIMENT_REPORT.md` concern *non-LLM controls only*. Qwen3-4B open-weight evaluation has **not yet been executed** because the current container lacks a GPU and outbound access. No honest submission should present the control numbers as model results, and no public HF bucket has been published yet. The file `LIVE_Qwen3_4B_Colab.ipynb` provides the needed full model run, including verification and publication after authentication.

# Technical Challenge: Blind Spots of Frontier Models

## 1. An underexplored capability gap from my experience

In my recent research, I have been developing context optimization methods for coding agents. An agent debugging a program sees only the source files, logs, and test outputs made available by its tools. To save inference time and tokens, many systems summarize or compress these outputs. The compression can look successful because the final error is still visible, while a tiny earlier line that distinguishes two possible root causes is missing.

I want to study **causal evidence blindness**: the risk that a frontier model makes a confident debugging claim even when its *current observation* does not logically identify the cause. This is different from simply failing a programming question. The model may be capable of solving the bug with complete evidence, yet fail to recognize when critical evidence has been discarded.

In a previous SymPy pilot, raw and compressed output produced the same top-five source-file ranking, and neither included the true source file in the top five. That result did not prove a negative effect from compression. Instead, it made me realize that typical final-answer or ranking metrics do not identify whether a debugging agent actually had the evidence necessary to act. My new experiment isolates that question.

## 2. Controlled evaluation of an open-weight frontier model

I selected [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), a 4B-parameter open-weight instruction model designed for strong coding and tool-use performance, while still fitting on a consumer CUDA GPU in 4-bit form. I constructed a **Causal Evidence Deletion (CED)** benchmark with 24 synthetic debugging families. Each has two counterfactual worlds with the exact same final error but a different root cause, for example, a CUDA out-of-memory error caused by an excessive batch size versus retained activation tensors.

There are 48 total debugging cases and 5 observation conditions: complete log, missing diagnostic line, compressed log that retains the line, missing line plus an unreliable triage guess, and a restored log. That is 240 generations for one full benchmark pass. The key control is that when the decisive line is deleted, the A and B worlds have **identical visible text**. Choosing one cause confidently is unjustified. A good agent should ask to retrieve evidence.

The code measures diagnosis accuracy when evidence exists, appropriate evidence requests when evidence is missing, attraction to misleading summaries, correct reversal of predictions when a single causal line changes, and token costs. It also supports comparing a standard debugging prompt with explicit evidence-seeking instructions. The complete dataset, GPU evaluation script, analysis code, and runnable Colab notebook are included in the project artifact.

**Honest experimental status:** I generated and verified the synthetic cases locally, including all 24 matched-pair indistinguishability checks. I have not yet executed Qwen3-4B GPU inference or collected its predictions in this environment, so I do not report any model failure rate or improvement. The Colab notebook generates and saves real scores once run.

## 3. Proposed solution

I propose training **evidence-aware debugging agents**. I would collect executable debugging traces from CI failures and real repository repairs, generate matched failures with differing root causes, and randomly omit critical log or traceback lines. Using QLoRA and preference tuning, the agent would learn to distinguish (a) supported diagnoses from (b) guesses made from incomplete observations. Asking for targeted evidence would be rewarded when the current view is insufficient.

At the system level, I would modify context compression to preserve provenance: original log offsets, source locations, and graph-based links to affected variables and assertions. If the agent is uncertain, it could call a retrieval tool to recover only the necessary log lines or perform a targeted program-slicing probe. Evaluation should track final patch accuracy and token usage **plus** the rate of unsupported confident diagnoses and the cost of retrieving evidence.

The key idea is that a strong debugging agent should not only reason well when the right information is present; it should **know when the right information is missing**.

**Model:** https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507  
**Public Hugging Face Bucket:** Not published yet. The supplied Colab notebook includes the authenticated public bucket publication step. Insert the verified bucket URL after publishing.