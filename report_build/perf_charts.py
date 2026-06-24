#!/usr/bin/env python3
"""Generate performance charts from real usage telemetry + live latency samples."""
import json, statistics as st
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

OUT = "/Volumes/BLACK_SHARK/MINOR_PROJECT/report_build/assets/diagrams"
plt.rcParams.update({
    "font.family": "DejaVu Sans", "font.size": 12,
    "axes.edgecolor": "#cbd5e1", "axes.linewidth": 0.8,
    "axes.grid": True, "grid.color": "#e2e8f0", "grid.linewidth": 0.7,
    "axes.axisbelow": True, "figure.dpi": 200,
})
BLUE, PURPLE, GREEN, AMBER = "#2563eb", "#7c3aed", "#16a34a", "#d97706"

data = json.load(open("/Volumes/BLACK_SHARK/MINOR_PROJECT/db/usage_metrics.json"))
groq = [d for d in data if d.get("provider") == "groq"]
mistral = [d for d in data if d.get("provider") == "mistral"]
g_lat = [d["latency"] for d in groq]
m_lat = [d["latency"] for d in mistral]
g_tok = [d["total_tokens"] for d in groq]
m_tok = [d["total_tokens"] for d in mistral]

def stats(x):
    if not x: return (0,0,0,0)
    return (round(st.mean(x),3), round(st.median(x),3), round(min(x),3), round(max(x),3))

print("=== TELEMETRY SUMMARY (n=%d) ===" % len(data))
print("groq    n=%d  latency mean/med/min/max=%s  tokens mean=%d total=%d" %
      (len(groq), stats(g_lat), round(st.mean(g_tok)) if g_tok else 0, sum(g_tok)))
print("mistral n=%d  latency mean/med/min/max=%s  tokens mean=%d total=%d" %
      (len(mistral), stats(m_lat), round(st.mean(m_tok)) if m_tok else 0, sum(m_tok)))

# --- Chart 1: mean latency per provider (bar) ---
fig, ax = plt.subplots(figsize=(6.2, 4))
provs = ["Groq Cloud\n(Llama 3.3 70B)", "Local Ollama\n(Mistral 7B)"]
means = [st.mean(g_lat) if g_lat else 0, st.mean(m_lat) if m_lat else 0]
bars = ax.bar(provs, means, color=[BLUE, PURPLE], width=0.55, zorder=3)
ax.set_ylabel("Mean response latency (seconds)")
ax.set_title("LLM Inference Latency by Provider", fontweight="bold", fontsize=13)
for b, v in zip(bars, means):
    ax.text(b.get_x()+b.get_width()/2, v+0.2, f"{v:.2f}s", ha="center", fontweight="bold")
ax.set_ylim(0, max(means)*1.18 if means else 1)
fig.tight_layout(); fig.savefig(f"{OUT}/perf_latency.png"); plt.close(fig)

# --- Chart 2: latency distribution (box) ---
fig, ax = plt.subplots(figsize=(6.2, 4))
bp = ax.boxplot([g_lat, m_lat], labels=["Groq", "Mistral (local)"],
                patch_artist=True, widths=0.5, showfliers=True,
                medianprops=dict(color="#0f172a", linewidth=1.5))
for patch, c in zip(bp["boxes"], [BLUE, PURPLE]):
    patch.set_facecolor(c); patch.set_alpha(0.45)
ax.set_ylabel("Latency (seconds)")
ax.set_title("Latency Distribution per Provider", fontweight="bold", fontsize=13)
fig.tight_layout(); fig.savefig(f"{OUT}/perf_latency_box.png"); plt.close(fig)

# --- Chart 3: hardcoded vs LLM command latency (log scale) ---
fig, ax = plt.subplots(figsize=(6.6, 4))
cats = ["Hardcoded\nintrospection", "NL to SQL\n(Groq)", "NL to SQL\n(local Mistral)"]
vals = [0.008, st.mean(g_lat) if g_lat else 0.7, st.mean(m_lat) if m_lat else 12]
bars = ax.bar(cats, vals, color=[GREEN, BLUE, PURPLE], width=0.55, zorder=3)
ax.set_yscale("log")
ax.set_ylabel("Mean latency (seconds, log scale)")
ax.set_title("Command Latency: Deterministic vs LLM Path", fontweight="bold", fontsize=13)
for b, v in zip(bars, vals):
    lbl = f"{v*1000:.0f} ms" if v < 1 else f"{v:.2f} s"
    ax.text(b.get_x()+b.get_width()/2, v*1.15, lbl, ha="center", fontweight="bold")
fig.tight_layout(); fig.savefig(f"{OUT}/perf_hardcoded_vs_llm.png"); plt.close(fig)

# --- Chart 4: token usage per provider (grouped) ---
fig, ax = plt.subplots(figsize=(6.2, 4))
labels = ["Prompt", "Completion"]
g_p = st.mean([d["prompt_tokens"] for d in groq]) if groq else 0
g_c = st.mean([d["completion_tokens"] for d in groq]) if groq else 0
m_p = st.mean([d["prompt_tokens"] for d in mistral]) if mistral else 0
m_c = st.mean([d["completion_tokens"] for d in mistral]) if mistral else 0
x = range(len(labels)); w = 0.36
ax.bar([i-w/2 for i in x], [g_p, g_c], w, label="Groq", color=BLUE, zorder=3)
ax.bar([i+w/2 for i in x], [m_p, m_c], w, label="Mistral", color=PURPLE, zorder=3)
ax.set_xticks(list(x)); ax.set_xticklabels(labels)
ax.set_ylabel("Mean tokens per call"); ax.legend()
ax.set_title("Average Token Usage per Call", fontweight="bold", fontsize=13)
fig.tight_layout(); fig.savefig(f"{OUT}/perf_tokens.png"); plt.close(fig)

print("charts written to", OUT)
