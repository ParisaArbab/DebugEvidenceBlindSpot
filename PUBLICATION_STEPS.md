# Publish the verified study from AIScalar

The model runs were already executed on AIScalar. **Do not repeat them just to publish.** The bundle includes both complete raw JSONL results and independent analysis.

## 1. Transfer the updated package

Download `DebugEvidenceBlindSpot_AnalyzedStudy.zip` from this conversation to your Mac. In a **Mac terminal**:

```bash
scp ~/Downloads/DebugEvidenceBlindSpot_AnalyzedStudy.zip \
    parbab@aiscalar.cdm.depaul.edu:/scratch/parbab/
```

On **AIScalar**:

```bash
cd /scratch/parbab
mkdir -p final_study
python -m zipfile -e DebugEvidenceBlindSpot_AnalyzedStudy.zip final_study
cd /scratch/parbab/final_study/DebugEvidenceBlindSpot
conda activate /scratch/parbab/envs/debug-evidence
export HF_HOME=/scratch/parbab/hf_cache
export TMPDIR=/scratch/parbab/tmp
```

This unpacks a standalone copy without overwriting your existing cloned repository.

## 2. Verify results locally

```bash
python analyze_actual_results.py
python publish_live_bucket.py --preview-only
```

The first command should report exactly **160 model decisions** and matching known scores. The preview should list files to be published without using your HF credentials.

## 3. Authenticate to Hugging Face for publishing

```bash
python -m pip install --upgrade 'huggingface_hub>=1.5.0'
hf auth login
hf auth whoami
```

Use a Hugging Face token with **write** permission. Paste it **only into the interactive terminal prompt**, never into ChatGPT, a script, or Git. Do not put secrets inside published files.

## 4. Publish the public Hugging Face Bucket

```bash
python publish_live_bucket.py --bucket-name debug-evidence-blindspot-live
```

The script verifies both 80-decision result files and their matching model revision, stages an allowlisted artifact set, creates a **public** bucket, uploads it and prints the verified URL.

The model weights are **not** duplicated. `MODEL_REFERENCE.json` records the exact Qwen checkpoint revision and links to the original open-weight repository.

## 5. Finish the application

Open the printed Bucket URL in a private/incognito browser window to confirm everyone can read the files. Replace the Bucket placeholder in `SUBMISSION.md` with this real URL. Do not claim the Bucket is public until publication and access checks succeed.

If you also want to update your **private GitHub** after reviewing the final files, copy the amended files into your existing AIScalar clone and commit locally with:

```bash
cd /scratch/parbab/DebugEvidenceBlindSpot
git config user.name 'Parisa Arbab'
git config user.email 'pa.arbab@gmail.com'
# Copy in the approved updated files before running the next commands.
git add -A
git commit -m 'Document verified Qwen evidence blindness experiments'
git push origin main
```

Do not copy the `.git` directory from the standalone package or commit any local credentials.
