"""Plot independently derived Qwen accuracy and evidence-request rates."""
import json
from pathlib import Path
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parent
M=json.loads((ROOT/'results/analysis_metrics.json').read_text())['runs']
conditions=['raw','tail_only','causal_slice','decoy_summary','retrieval_enabled']
labels=['Full log','Deleted','Causal slice','Decoy summary','Retrieval']

for measure, title, ylabel, file, subset in [
    ('verified_repairs','Qwen3-4B: verified repairs by evidence condition','Successful repairs / 16','verified_repairs_comparison.png',conditions),
    ('initial_evidence_requests','Qwen3-4B: evidence requests when evidence is missing','Evidence requests / 16','missing_evidence_requests.png',['tail_only','decoy_summary','retrieval_enabled']),
]:
    cs=subset
    x=list(range(len(cs)))
    width=0.35
    fig,ax=plt.subplots(figsize=(9,4.7))
    left=[M['baseline'][c][measure] for c in cs]
    right=[M['evidence_aware'][c][measure] for c in cs]
    b1=ax.bar([i-width/2 for i in x],left,width,label='Baseline')
    b2=ax.bar([i+width/2 for i in x],right,width,label='Evidence-aware')
    ax.set_xticks(x, [labels[conditions.index(c)] for c in cs])
    ax.set_ylim(0,17)
    ax.set_ylabel(ylabel)
    ax.set_title(title)
    ax.legend()
    ax.bar_label(b1,padding=2)
    ax.bar_label(b2,padding=2)
    fig.tight_layout()
    fig.savefig(ROOT/'results'/file,dpi=160)
    plt.close(fig)
print('Saved independent plots')
