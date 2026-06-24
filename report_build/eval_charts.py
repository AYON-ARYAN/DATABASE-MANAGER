#!/usr/bin/env python3
"""Render evaluation charts from eval_results.json."""
import json, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT = "/Volumes/BLACK_SHARK/MINOR_PROJECT/report_build/assets/diagrams"
d = json.load(open("/Volumes/BLACK_SHARK/MINOR_PROJECT/report_build/eval_results.json"))
S = d["summary"]
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 12, "axes.edgecolor": "#cbd5e1",
    "axes.grid": True, "grid.color": "#e2e8f0", "axes.axisbelow": True, "figure.dpi": 200})
BLUE, GREEN, PURPLE, AMBER = "#2563eb", "#16a34a", "#7c3aed", "#d97706"

# --- Accuracy by category (horizontal bars) ---
cats = S["by_category"]
labels, pcts = [], []
for k, v in cats.items():
    p, t = v.split("/")
    labels.append(k); pcts.append(100*int(p)/int(t))
order = sorted(range(len(labels)), key=lambda i: pcts[i])
labels = [labels[i] for i in order]; pcts = [pcts[i] for i in order]
fig, ax = plt.subplots(figsize=(7.2, 4.2))
bars = ax.barh(labels, pcts, color=[GREEN if p>=100 else (BLUE if p>=50 else AMBER) for p in pcts], zorder=3)
ax.set_xlim(0, 108); ax.set_xlabel("Execution accuracy (%)")
ax.set_title(f"NL→SQL Execution Accuracy by Query Type  (overall {S['execution_accuracy_pct']}%)",
             fontweight="bold", fontsize=12.5)
for b, p in zip(bars, pcts):
    ax.text(b.get_width()+1.5, b.get_y()+b.get_height()/2, f"{p:.0f}%", va="center", fontsize=11)
fig.tight_layout(); fig.savefig(f"{OUT}/eval_accuracy_by_cat.png"); plt.close(fig)

# --- Headline metrics panel ---
fig, ax = plt.subplots(figsize=(7.6, 2.4)); ax.axis("off")
metrics = [
    (f"{S['execution_accuracy_pct']:.0f}%", f"Execution accuracy\n({S['passed']}/{S['n_questions']} questions)", GREEN),
    (f"{S['latency_mean_s']:.2f}s", "Mean NL→SQL latency\n(Groq cloud)", BLUE),
    (f"{S['safety_contained_pct']:.0f}%", f"Unsafe queries contained\n({S['n_attacks']} attacks)", PURPLE),
    (f"{S['hardcoded_mean_ms']:.0f}ms", "Hardcoded introspection\n(no LLM)", AMBER),
]
for i, (big, lbl, c) in enumerate(metrics):
    x = 0.02 + i*0.25
    ax.text(x+0.11, 0.62, big, fontsize=30, fontweight="bold", color=c, ha="center")
    ax.text(x+0.11, 0.20, lbl, fontsize=10.5, color="#334155", ha="center")
fig.tight_layout(); fig.savefig(f"{OUT}/eval_headline.png"); plt.close(fig)
print("charts written:", S)
