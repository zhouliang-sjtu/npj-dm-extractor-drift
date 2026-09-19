# -*- coding: utf-8 -*-
"""Fig2_Fig3_calibration_acceptance.py v2 —— 修正排版
Figure 2: (a) 四域 (b) 31变量κ分组条形 (c) test-retest (d) codebook演进
Figure 3: (a) κ热图 (b) freeze规则 (c) below-gate明细
"""
import os
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

P1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
RES, DAT, FIG = os.path.join(P1, "results"), os.path.join(P1, "data"), os.path.join(P1, "figures")
NAVY, BLUE, GREEN, RED, ORANGE, GRAY, PURPLE = "#1F3864", "#2F5B8F", "#1E8449", "#C0392B", "#B9770E", "#7F8C8D", "#7D3C98"
GATE = 0.80

def load_agree(fname):
    d = pd.read_csv(os.path.join(DAT, fname), dtype=str)
    d.columns = [c.strip() for c in d.columns]
    d = d[~d["variable"].str.contains("@", na=False)].copy()
    d["cohen_kappa"] = d["cohen_kappa"].astype(float)
    return d

ecg = load_agree("agreement_ECG_H.csv")
echo = load_agree("agreement_ECHO_PG.csv")
apg = load_agree("agreement_ABDUS_PG.csv")
ah = load_agree("agreement_ABDUS_H.csv")
intra = pd.read_csv(os.path.join(RES, "round2_selfrepeat_intra.csv"))

fig = plt.figure(figsize=(14.5, 14.6))
gs = fig.add_gridspec(2, 2, height_ratios=[1.0, 1.0], hspace=0.42, wspace=0.42)

# ---- (a) ----
ax = fig.add_subplot(gs[0, 0])
domains = [("ECG_H  ·  ECG conclusions", 570, 12, BLUE),
           ("ECHO_PG  ·  Echo reports", 300, 9, GREEN),
           ("ABDUS_PG  ·  Abd. US (site 1)", 300, 7, ORANGE),
           ("ABDUS_H  ·  Abd. US (site 2)", 300, 7, PURPLE)]
ys = np.arange(len(domains))[::-1]
for y, (lab, n, nv, c) in zip(ys, domains):
    ax.barh(y, n, color=c, alpha=0.85, height=0.6, zorder=2)
    ax.annotate(f"n = {n:,}   ·   {nv} variables", xy=(n + 10, y), va="center", fontsize=9)
ax.set_yticks(ys); ax.set_yticklabels([d[0] for d in domains], fontsize=9)
ax.set_xlim(0, 780); ax.set_xlabel("Records (dual-annotated, blinded)", fontsize=10)
ax.set_title("(a)  Four domains · 1,470 records · 35 flag columns (28 variable definitions)", fontsize=11, loc="left")
ax.spines[["top", "right"]].set_visible(False)

# ---- (b) 分组条形：4 域块，组间留空 ----
ax = fig.add_subplot(gs[0, 1])
frames = [("ECG_H", ecg, BLUE, "ecg_"), ("ECHO_PG", echo, GREEN, "echo_"),
          ("ABDUS_PG", apg, ORANGE, "us_|main_"), ("ABDUS_H", ah, PURPLE, "us_|main_")]
y = 0; yticks = []; ylabels = []
for dom, d, c, pfx in frames:
    dd = d.sort_values("cohen_kappa")
    for _, r in dd.iterrows():
        vname = r["variable"]
        for p in pfx.split("|"):
            vname = vname.replace(p, "")
        ax.barh(y, r["cohen_kappa"], color=c, alpha=0.85, height=0.62, zorder=2)
        if r["cohen_kappa"] < 0.995:  # κ=1.00 不标注，避免右缘堆叠
            ax.annotate(f"{r['cohen_kappa']:.2f}", xy=(r["cohen_kappa"] + 0.008, y), va="center", fontsize=6.8)
        yticks.append(y); ylabels.append(vname)
        y += 1
    y += 1.5  # 组间空隙（加大，避免相邻组标签视觉粘连）
ax.axvline(GATE, color=RED, ls="--", lw=1.4, zorder=3)
ax.set_ylim(-1.0, y + 1.6)
# gate 标签横排、置于顶部留白带：左缘贴 gate 线右侧但留出间距，不压任何数据条
ax.annotate("gate κ ≥ 0.80", xy=(GATE + 0.012, y + 1.42), fontsize=7.6, color=RED,
            ha="left", va="top")
ax.set_yticks(yticks); ax.set_yticklabels(ylabels, fontsize=8.0)
ax.set_xlim(0.55, 1.06); ax.set_xlabel("Inter-annotator Cohen κ (A1 vs A2, blinded)", fontsize=10)
ax.set_title("(b)  31/31 variables meet the κ ≥ 0.80 gate (grouped by domain)", fontsize=11, loc="left")
ax.spines[["top", "right"]].set_visible(False)

# ---- (c) test-retest ----
ax = fig.add_subplot(gs[1, 0])
ecg_intra = intra[intra.domain == "ECG_H"]
vars_order = ["ecg_normal","ecg_af","ecg_pac_pvc","ecg_stt","ecg_avblock","ecg_bbb",
              "ecg_rate","ecg_srirr","ecg_axis","ecg_qwave_mi","ecg_other","ecg_unreadable"]
xpos = np.arange(len(vars_order))
for i, vv in enumerate(vars_order):
    for rater, mk, off in [("A1", "o", -0.1), ("A2", "s", 0.1)]:
        row = ecg_intra[(ecg_intra.variable == vv) & (ecg_intra.rater == rater)]
        if len(row):
            k = float(row["cohen_kappa"].iloc[0])
            affected = bool(row["v2_affected"].iloc[0])
            ax.scatter(i + off, max(k, 0.0), s=48, marker=mk, zorder=3,
                       color=ORANGE if affected else BLUE, edgecolors="white", linewidths=0.6)
ax.axhline(GATE, color=RED, ls="--", lw=1.2, zorder=1)
ax.set_xticks(xpos)
ax.set_xticklabels([v.replace("ecg_", "") for v in vars_order], rotation=40, ha="right", fontsize=8.2)
ax.set_ylim(-0.06, 1.12)
ax.set_ylabel("Intra-rater Cohen κ (≥3-day re-annotation)", fontsize=10)
ax.set_title("(c)  Test–retest stability (ECG_H: 57 records × 12 variables × 2 annotators)", fontsize=10.5, loc="left")
ax.scatter([], [], s=46, marker="o", color=BLUE, label="A1 · rule-stable variable")
ax.scatter([], [], s=46, marker="s", color=BLUE, label="A2 · rule-stable variable")
ax.scatter([], [], s=46, marker="o", color=ORANGE, label="arbitration-revised variable")
ax.legend(fontsize=7.4, loc="lower left", framealpha=0.92)
ax.spines[["top", "right"]].set_visible(False)

# ---- (d) codebook evolution（纵向流程：5 节点竖排宽框，左侧插两段说明） ----
ax = fig.add_subplot(gs[1, 1])
ax.axis("off")
ax.set_xlim(0, 1); ax.set_ylim(0, 1)
NX0, NX1 = 0.06, 0.72                    # 框横向范围：宽框装下全部文字，右侧留说明带
NC = (NX0 + NX1) / 2
BH, GAP = 0.125, 0.062                   # 框高 / 间隔（流程箭头空间）
nodes = [
    ("Codebook v1.0", "literature-based · 28 variable defs", NAVY),
    ("Dual annotation", "1,470 records · A1 / A2 blinded", BLUE),
    ("Arbitration", "43 rulings + flags · reasons recorded", BLUE),
    ("Codebook V2.0", "8 revisions from arbitration", GREEN),
    ("Codebook V3.0", "outcome clause (Stage-2 ruling)", ORANGE),
]
_total = len(nodes) * BH + (len(nodes) - 1) * GAP
_y = 1 - (1 - _total) / 2                # 垂直居中
tops = []
for name, sub, c in nodes:
    ax.add_patch(FancyBboxPatch((NX0, _y - BH), NX1 - NX0, BH,
                                boxstyle="round,pad=0.010", fc="white", ec=c, lw=1.4, zorder=3))
    ax.text(NX0 + 0.025, _y - 0.040, name, ha="left", va="center", fontsize=7.6,
            fontweight="bold", color=c, zorder=4)
    ax.text(NX0 + 0.025, _y - 0.088, sub, ha="left", va="center", fontsize=6.6,
            color="#333333", zorder=4)
    tops.append(_y)
    _y -= BH + GAP
# 纵向流程箭头（框间）
for k in range(len(nodes) - 1):
    ax.annotate("", xy=(NC, tops[k + 1] + 0.006), xytext=(NC, tops[k] - BH - 0.006),
                arrowprops=dict(arrowstyle="-|>", lw=1.6, color=NAVY))
# 两段说明：移至流程右侧的说明带，左对齐（43 裁定→V2.0；n=160→V3.0）
_mid_34 = ((tops[2] - BH) + tops[3]) / 2
_mid_45 = ((tops[3] - BH) + tops[4]) / 2
ax.text(NX1 + 0.045, _mid_34, "43 arbitration\ndecisions", ha="left", va="center",
        fontsize=7.0, color=GREEN, fontweight="bold")
ax.text(NX1 + 0.045, _mid_45, "outcome clause\n(Stage-2, n=160)", ha="left", va="center",
        fontsize=7.0, color=ORANGE, fontweight="bold")
ax.set_title("(d)  Every disagreement became a durable codebook rule", fontsize=10.5, loc="left")

fig.suptitle("Calibration: a four-component annotation protocol yields a four-domain gold standard",
             fontsize=13, fontweight="bold", y=0.995)
fig.savefig(os.path.join(FIG, "Figure2_calibration.png"), dpi=200, bbox_inches="tight")
fig.savefig(os.path.join(FIG, "Figure2_calibration.pdf"), bbox_inches="tight")
plt.close(fig)
print("Figure 2 v2 done")

# ============ Figure 3 ============
m2d = pd.read_csv(os.path.join(RES, "m2d_acceptance_ecg.csv"))
models = [("qwen2.5:14b", "Qwen2.5-14B"), ("qwen2.5:7b", "Qwen2.5-7B"), ("glm4:9b", "GLM4-9B")]
mc = ["#2F5B8F", "#7D3C98", "#1E8449"]
VARS = ["ecg_normal","ecg_af","ecg_pac_pvc","ecg_stt","ecg_avblock","ecg_bbb",
        "ecg_rate","ecg_srirr","ecg_axis","ecg_qwave_mi","ecg_other","ecg_unreadable"]

fig, axes = plt.subplots(1, 3, figsize=(15, 5.4), gridspec_kw={"width_ratios": [1.55, 0.75, 1.1], "wspace": 0.36})

ax = axes[0]
mat = np.zeros((len(VARS), 3))
for j, (mk, _) in enumerate(models):
    for i, vv in enumerate(VARS):
        row = m2d[(m2d.model == mk) & (m2d.variable == vv)]
        mat[i, j] = float(row["cohen_kappa"].iloc[0]) if len(row) else np.nan
im = ax.imshow(mat, cmap="RdYlGn", vmin=0.0, vmax=1.0, aspect="auto")
ax.set_xticks(range(3)); ax.set_xticklabels([m[1] for m in models], fontsize=8.4, rotation=16, ha="right")
ax.set_yticks(range(len(VARS))); ax.set_yticklabels([v.replace("ecg_", "") for v in VARS], fontsize=8.4)
for i in range(len(VARS)):
    for j in range(3):
        ax.text(j, i, f"{mat[i, j]:.2f}", ha="center", va="center", fontsize=7.8,
                color="black", fontweight="bold" if mat[i, j] < GATE else "normal")
ax.set_title("(a)  LLM vs gold standard: Cohen κ per variable", fontsize=11, loc="left")
for i in range(len(VARS) + 1):
    ax.axhline(i - 0.5, color="white", lw=1.2)
for j in range(1, 3):
    ax.axvline(j - 0.5, color="white", lw=1.2)

ax = axes[1]
npass = [int(((m2d.model == mk) & (m2d.verdict == "PASS")).sum()) for mk, _ in models]
bars = ax.bar([m[1] for m in models], npass, color=mc, width=0.55, zorder=2)
ax.axhline(8, color=RED, ls="--", lw=1.6, zorder=3)
# 冻结规则标注移至右上空白区（上方条为 8/7，右侧高位无数据）
ax.annotate("freeze rule: n_pass ≥ 8/12", xy=(0.97, 0.965), xycoords="axes fraction",
            fontsize=8.6, color=RED, ha="right", va="top")
for b, val in zip(bars, npass):
    ax.annotate(f"{val}/12", xy=(b.get_x() + b.get_width()/2, val + 0.18), ha="center", fontsize=10.5, fontweight="bold")
ax.set_xticks(range(len(models)))
ax.set_xticklabels([m[1] for m in models], fontsize=8.4, rotation=16, ha="right")  # 防长模型名互撞
ax.set_ylim(0, 13.4); ax.set_ylabel("Variables passing all gates", fontsize=10)
ax.set_title("(b)  Pre-registered freeze rule", fontsize=11, loc="left")
ax.spines[["top", "right"]].set_visible(False)

ax = axes[2]
below = ["ecg_normal", "ecg_other", "ecg_rate", "ecg_unreadable"]
xpos = np.arange(len(below)); wdt = 0.24
for j, (mk, ml) in enumerate(models):
    ks = [float(m2d[(m2d.model == mk) & (m2d.variable == v)]["cohen_kappa"].iloc[0]) for v in below]
    ax.bar(xpos + (j - 1) * wdt, ks, width=wdt, color=mc[j], label=ml, zorder=2)
ax.axhline(GATE, color=RED, ls="--", lw=1.4, zorder=3)
# gate 标签与 (b) 的 freeze rule 同高对齐（同 axes-fraction、同右对齐），红字红线上下呼应
ax.annotate("gate κ ≥ 0.80", xy=(0.97, 0.965), xycoords="axes fraction",
            fontsize=8.6, color=RED, ha="right", va="top")
ax.set_xticks(xpos)
ax.set_xticklabels([v.replace("ecg_", "") for v in below], rotation=16, ha="right", fontsize=8.8)
ax.set_ylim(0, 1.45); ax.set_ylabel("LLM vs gold standard κ", fontsize=10)
ax.set_title("(c)  Below-gate variables are the definition-sensitive ones", fontsize=10.5, loc="left")
ax.legend(fontsize=7.6, loc="upper left", framealpha=0.92)   # 右上让位给 gate 标签
ax.spines[["top", "right"]].set_visible(False)

fig.suptitle("Acceptance: pre-registered gates freeze the LLM track for production (ECG_H, n = 570, blinded gold standard)",
             fontsize=12.5, fontweight="bold", y=1.0)
fig.savefig(os.path.join(FIG, "Figure3_acceptance.png"), dpi=200, bbox_inches="tight")
fig.savefig(os.path.join(FIG, "Figure3_acceptance.pdf"), bbox_inches="tight")
plt.close(fig)
print("Figure 3 v2 done")
