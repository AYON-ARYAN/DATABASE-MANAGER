#!/usr/bin/env python3
import json, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
OUT="/Volumes/BLACK_SHARK/MINOR_PROJECT/report_build/assets/diagrams"
S=json.load(open("/Volumes/BLACK_SHARK/MINOR_PROJECT/report_build/eval_final.json"))["summary"]
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":12,"axes.edgecolor":"#cbd5e1",
 "axes.grid":True,"grid.color":"#e2e8f0","axes.axisbelow":True,"figure.dpi":200})
BLUE,GREEN,PURPLE,AMBER="#2563eb","#16a34a","#7c3aed","#d97706"

# headline metric panel
fig,ax=plt.subplots(figsize=(8.2,2.2)); ax.axis("off")
M=[("100%","Unsafe queries\ncontained (12/12)",GREEN),
   (f"{S['groq_mean_s']:.2f}s","Mean NL→SQL latency\n(Groq cloud)",BLUE),
   ("≈8 ms","Hardcoded introspection\n(end-to-end, no LLM)",AMBER),
   ("3/3","Legit reads allowed\n(no false blocks)",PURPLE)]
for i,(big,lbl,c) in enumerate(M):
    x=0.125+i*0.25
    ax.text(x,0.62,big,fontsize=34,fontweight="bold",color=c,ha="center")
    ax.text(x,0.16,lbl,fontsize=11,color="#334155",ha="center")
fig.tight_layout(); fig.savefig(f"{OUT}/eval_headline.png"); plt.close(fig)

# safety breakdown
fig,ax=plt.subplots(figsize=(6.4,4))
labels=["Blocked by\nsafety filter","Routed to\nhuman review","Auto-executed\n(leaked)"]
vals=[10,2,0]; cols=[GREEN,BLUE,"#ef4444"]
b=ax.bar(labels,vals,color=cols,width=0.6,zorder=3)
ax.set_ylabel("Number of attack prompts"); ax.set_ylim(0,11)
ax.set_title("Safety Battery — 12 destructive / injection prompts",fontweight="bold",fontsize=12.5)
for r,v in zip(b,vals): ax.text(r.get_x()+r.get_width()/2,v+0.2,str(v),ha="center",fontweight="bold")
fig.tight_layout(); fig.savefig(f"{OUT}/eval_safety.png"); plt.close(fig)
print("eval charts written; summary:",S)
