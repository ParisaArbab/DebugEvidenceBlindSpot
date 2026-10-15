"""Build a self-contained Colab notebook, embedding an archive of all code + dataset."""
from pathlib import Path
from io import BytesIO
import base64,zipfile,nbformat
R=Path(__file__).resolve().parent
archive_files=['README.md','SUBMISSION.md','MODEL_REFERENCE.json','requirements.txt','generate_data.py','evaluate.py','analyze.py','smoke_test.py','publish_bucket.py','data/paired_cases.jsonl','data/manifest.json','results/README.md']
buf=BytesIO()
with zipfile.ZipFile(buf,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for fn in archive_files:z.write(R/fn,arcname=fn)
encoded=base64.b64encode(buf.getvalue()).decode()
n=nbformat.v4.new_notebook()
n.metadata={'colab':{'name':'CED_Qwen3_4B_Colab.ipynb','provenance':[],'gpuType':'T4'},'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'},'language_info':{'name':'python'}}
n.cells=[
 nbformat.v4.new_markdown_cell('''# Causal Evidence Deletion: a debugging-agent blind spot

**Open-weight model:** [Qwen3-4B-Instruct-2507](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507), 4 billion parameters.  
**Question:** Does a coding LLM keep guessing after compression removes the decisive debugging evidence, or does it ask to recover the missing line?

This notebook contains the **complete synthetic benchmark** and experiment code inside an embedded archive, so you do not have to upload a second file. The main results are real only after executing the GPU inference cell. The publication cell creates a **public** Hugging Face Bucket under your account.

**Colab:** Runtime → Change runtime type → T4 GPU. Do not claim this notebook's results until GPU inference has run successfully.'''),
 nbformat.v4.new_code_cell('''%pip -q install "transformers>=4.55,<6" "accelerate>=1.2" "bitsandbytes>=0.45" "safetensors>=0.5" "huggingface_hub>=1.20" matplotlib pandas'''),
 nbformat.v4.new_code_cell('''# Unpack all scripts, dataset, and README embedded in this notebook.
import base64, io, zipfile, os
from pathlib import Path
BASE=Path('/content/ced') if Path('/content').exists() else Path('./ced')
BASE.mkdir(parents=True,exist_ok=True)
PACKAGED_ZIP = "'''+encoded+'''"
with zipfile.ZipFile(io.BytesIO(base64.b64decode(PACKAGED_ZIP))) as z:
    z.extractall(BASE)
print('Unpacked:',BASE)
print('README:',BASE/'README.md')
print('Cases:',len((BASE/'data'/'paired_cases.jsonl').read_text().splitlines()))'''),
 nbformat.v4.new_code_cell('''# Confirm a real CUDA device and validate the paired dataset (not model evaluation).
import torch, subprocess, sys
assert torch.cuda.is_available(), 'No CUDA GPU is enabled. Choose a GPU runtime in Colab first.'
print('GPU:',torch.cuda.get_device_name(0))
subprocess.run([sys.executable,'smoke_test.py'],cwd=BASE,check=True)'''),
 nbformat.v4.new_markdown_cell('''## Run the model (actual open-weight evaluation)

48 cases x 5 contexts = 240 genuine model generations. Greedy decoding, identical prompt across conditions, NF4 4-bit quantization. Output records contain **unmodified model responses** as well as parsed decisions. This cell does **not** create fake or simulated results.'''),
 nbformat.v4.new_code_cell('''# Full benchmark. To start with 4 families instead, set MAX_FAMILIES = 4.
# For an application submission, set 0 and finish all 24 families.
MAX_FAMILIES=0
subprocess.run([sys.executable,'evaluate.py','--max-families',str(MAX_FAMILIES),
                '--output','results/actual_generations.jsonl'],
               cwd=BASE,check=True)
print('Model generations:',sum(1 for _ in open(BASE/'results/actual_generations.jsonl')))'''),
 nbformat.v4.new_code_cell('''# Score ONLY actual model outputs. Do not reuse metrics from a different model.
subprocess.run([sys.executable,'analyze.py','results/actual_generations.jsonl',
               '--save','results/metrics.json'],cwd=BASE,check=True)
import json, pandas as pd
summary=json.loads((BASE/'results'/'metrics.json').read_text())
rows=[]
for k,v in summary['metrics'].items():
    if k in ('policy_simulation','matched_pair_reversal'):continue
    rows.append({'condition':k,'n':v['n'],
                 'diagnosis_accuracy':v.get('ground_truth_accuracy'),
                 'correct_request_rate':v.get('correct_request_rate'),
                 'unsupported_guess_rate':v.get('guessed_when_underdetermined_rate'),
                 'prompt_tokens':v['mean_prompt_tokens']})
display(pd.DataFrame(rows))
print('Matched-pair reversal:',summary['metrics']['matched_pair_reversal'])
print('Retrieval policy:',summary['metrics']['policy_simulation'])'''),
 nbformat.v4.new_code_cell('''# Optional figure created from measured model results only.
import matplotlib.pyplot as plt
results = summary['metrics']
labels=['raw','tail_only','cause_preserved','decoy_only','restored']
values=[]
for cond in labels:
    data=results.get(cond,{})
    values.append(data.get('ground_truth_accuracy') if cond in ('raw','cause_preserved','restored') else data.get('correct_request_rate'))
fig,ax=plt.subplots(figsize=(9,4))
ax.bar(labels,[x or 0 for x in values])
ax.set_ylim(0,1.05)
ax.set_ylabel('Correct evidence-aware action rate')
ax.set_title('CED on Qwen3-4B-Instruct-2507')
plt.xticks(rotation=15)
fig.tight_layout()
fig.savefig(BASE/'results'/'measured_rates.png',dpi=180)
plt.show()'''),
 nbformat.v4.new_markdown_cell('''## Publish a public Hugging Face Bucket

This requires Hugging Face authorization with permission to create buckets and write files. The bucket is **public**, exactly as requested. The publication script checks for authentic saved model outputs and metrics before uploading. It uploads source code, synthetic dataset, README, run metadata, model identifier, and result files, **not an unnecessary second copy of the model's 8GB of weights**. [Official model weights are already public](https://huggingface.co/Qwen/Qwen3-4B-Instruct-2507).'''),
 nbformat.v4.new_code_cell('''from huggingface_hub import notebook_login
notebook_login()
subprocess.run([sys.executable,'publish_bucket.py','--bucket-name','causal-evidence-deletion-debugging'],
               cwd=BASE,check=True)
print('Check the exact public bucket URL shown above. Do not guess a link before publication.')'''),
 nbformat.v4.new_code_cell('''# Optional: download actual results and study assets after the run.
import shutil
archive=shutil.make_archive('/content/CED_completed_evaluation','zip',root_dir=BASE)
print(archive)
try:
  from google.colab import files
  files.download(archive)
except ImportError:
  pass''')
]
output=R/'CED_Qwen3_4B_Colab.ipynb'
nbformat.write(n,output)
print('Created:',output,'Bytes:',output.stat().st_size, 'embedded archive bytes:',len(buf.getvalue()))
