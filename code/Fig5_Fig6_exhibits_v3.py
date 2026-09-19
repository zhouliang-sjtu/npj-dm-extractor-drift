# -*- coding: utf-8 -*-
"""Fig5_Fig6_exhibits_v3.py —— field-domain drift forms & four-stratum adjudication exhibits (v3, 2026-09-18)
Figure 6: 四层判读设计+结果（森林图+分歧结构）→ figures/Figure6_adjudication_strata.png/.pdf
Figure 5: 三种漂移形态 × 聚合规则稳健性矩阵 → figures/Figure5_drift_forms_matrix.png/.pdf
数据源：adjudicated workbook（gold_annotation_workbook_final.xlsx 判读 panel 实测）、B31 v3.5（逐年口径）
"""
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

P1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
FIG = os.path.join(P1, "figures")
os.makedirs(FIG, exist_ok=True)

BLUE, RED, GREEN, GRAY = "#2F5B8F", "#C0392B", "#1E8449", "#7F8C8D"

# ================= Figure 6（四层判读，n=160） =================
fig = plt.figure(figsize=(12.2, 6.4))
gs = fig.add_gridspec(1, 2, width_ratios=[1.25, 1], wspace=0.30)

ax = fig.add_subplot(gs[0, 0])
strata = [
    ("Stratum 1  2023 sparse divergent (n=100, decision)", 0.15, 0.093, 0.233, "#1a1a1a"),
    ("Stratum 2  2023 anchor: agreed-abnormal (n=20)", 1.00, 0.839, 1.000, GRAY),
    ("Stratum 3  2023 anchor: explicit-normal (n=20)", 0.00, 0.000, 0.161, GRAY),
    ("Stratum 4  2021 cross-year control (n=20)", 0.05, 0.009, 0.236, "#1a1a1a"),
]
ys = np.arange(len(strata))[::-1]
for y, (label, p, lo, hi, color) in zip(ys, strata):
    ax.plot([lo, hi], [y, y], color=color, lw=2.2, solid_capstyle="round", zorder=2)
    ax.plot([lo, lo], [y - 0.13, y + 0.13], color=color, lw=1.6, zorder=2)
    ax.plot([hi, hi], [y - 0.13, y + 0.13], color=color, lw=1.6, zorder=2)
    ax.scatter([p], [y], s=64, color=color, zorder=3)
    ax.annotate(f"p = {p:.2f}", xy=(max(p, hi) + 0.03, y), va="center", fontsize=9)
ax.axvline(0.30, color=RED, ls="--", lw=1.2)   # 与 Fig2(b)/Fig3 的 gate 红虚线同语义
ax.annotate("A: explicit-positive\n(pre-registered CI upper < 0.30 → fired)", xy=(0.72, -0.68),
            ha="center", fontsize=8, color=GREEN)   # 右移至下方空白区，避开门限线与坐标注记
ax.annotate("naive rule labelled\nall 100 abnormal", xy=(0.99, 3), ha="right", fontsize=8.5, color=RED)
ax.set_yticks(ys)
ax.set_yticklabels([s[0] for s in strata], fontsize=9)
ax.set_xlim(-0.02, 1.13)
ax.set_ylim(-1.0, len(strata) - 0.2)
ax.set_xlabel("Panel proportion adjudicated abnormal (with 95% Wilson CI)", fontsize=10)
ax.set_title("(a)  Pre-registered four-stratum adjudication (n=160, corrected library)", fontsize=11, loc="left")
ax.spines[["top", "right"]].set_visible(False)

ax2 = fig.add_subplot(gs[0, 1])
cats = ["0 vs 1", "2 vs 1", "0 vs 2"]
vals = [0, 1, 0]
cols = [BLUE, "#E67E22", RED]
bars = ax2.bar(cats, vals, color=cols, width=0.55, zorder=2)
for b, val in zip(bars, vals):
    ax2.annotate(f"{val}", xy=(b.get_x() + b.get_width() / 2, val + 0.03), ha="center",
                 fontsize=11, fontweight="bold")
# 说明文字压成 5 行收窄块，置于 "0 vs 2" 零值条上方空白带（右侧扩 xlim 容纳）
ax2.annotate("single disagreement (A075)\nJ-point elevation without the\nearly-repolarization qualifier\nadjudicated abnormal by\nthe arbitrator",
             xy=(2.1, 0.42), ha="center", va="center", fontsize=7.8, color="#922B21")
ax2.set_xlim(-0.5, 3.0)
ax2.set_ylim(0, 1.35)
ax2.set_yticks([0, 1])
ax2.set_ylabel("Annotator-pair disagreements (of 160)", fontsize=10)
ax2.set_xlabel("pair types: 0 vs 1 = normal vs unreadable;  2 vs 1 = abnormal vs normal;  0 vs 2 = unreadable vs abnormal",
               fontsize=7.6)
ax2.set_title("(b)  Disagreement structure and calibration", fontsize=10.5, loc="left")
ax2.text(0.02, 0.97, "Calibration anchors: agreed-abnormal 20/20 → abnormal;\n"
                     "explicit-normal 20/20 → normal  (ceiling on both sides)",
         transform=ax2.transAxes, va="top", fontsize=8.5,
         bbox=dict(boxstyle="round,pad=0.35", fc="#eef4fa", ec=BLUE, lw=0.8))
ax2.spines[["top", "right"]].set_visible(False)
fig.suptitle("Pre-registered outcome-definition adjudication (Stage 2 redesign, n=160, blinded + arbitration)",
             fontsize=12.5, fontweight="bold", y=0.995)
fig.savefig(os.path.join(FIG, "Figure6_adjudication_strata.png"), dpi=200, bbox_inches="tight")
fig.savefig(os.path.join(FIG, "Figure6_adjudication_strata.pdf"), bbox_inches="tight")
plt.close(fig)
print("Figure6 (n=160) done")

# ================= Figure 5（漂移形态 × 聚合规则矩阵） =================
fig, ax = plt.subplots(figsize=(10.5, 5.6))
forms = [
    ("Form 1  Template enumeration (2022)", "Enumerated flags extracted;\nrhythm-only lines →\ncounted abnormal", "Enumerated flags\nextracted correctly;\nno outcome distortion"),
    ("Form 2  Misplaced field content (2023)", "Any misplaced content →\nrecord counted abnormal\n(panel verdict: unreadable)", "Pre-registered rule:\nmisplaced content →\nunreadable (excluded)"),
    ("Form 3  Conclusion sparsification (2023)", "Rhythm-only lines →\nrecord counted abnormal\n(panel verdict: normal)", "No flag positive →\nnormal by enumeration;\nno distortion"),
]
cols_h = ["Upstream drift form\n(unforeseeable)", 'Aggregation rule A:\n"not-explicitly-normal"\n(never approved)', 'Aggregation rule B:\n"explicit-positive + unreadable"\n(V3.0, adjudicated)']
table = ax.table(cellText=[[f[1], f[2]] for f in forms], rowLabels=[f[0] for f in forms],
                 colLabels=cols_h[1:], cellLoc="center", loc="center")
table.auto_set_font_size(False)
table.set_fontsize(9.5)
table.scale(1, 3.4)
RED_BG, GREEN_BG = "#FADBD8", "#D5F5E3"
for (r, c), cell in table.get_celld().items():
    cell.set_edgecolor("#B9C4CE")
    if r == 0:
        cell.set_facecolor("#DDEBF7"); cell.set_text_props(weight="bold")
    elif c == 0:
        cell.set_facecolor(RED_BG)
        cell.set_text_props(color="#922B21", weight="bold")
    elif c == 1:
        cell.set_facecolor(GREEN_BG); cell.set_text_props(color="#145A32", weight="bold")
ax.axis("off")
ax.set_title("Documentation drift takes unforeseeable forms;\n"
             'only "explicit-positive + unreadable" aggregation is robust to all of them',
             fontsize=12.5, fontweight="bold", pad=18)
fig.text(0.5, 0.015, "Definition-divergent stratum (2023): 3,204 records = 14.8% of the 2023 cohort (3.6\u20138.3 pp in 2018\u20132022). "
         "Panel adjudication of the 2023 decision stratum (n = 100): 15% abnormal, 76% normal, 9% unreadable.",
         ha="center", fontsize=9, color="#555555")
fig.savefig(os.path.join(FIG, "Figure5_drift_forms_matrix.png"), dpi=200, bbox_inches="tight")
fig.savefig(os.path.join(FIG, "Figure5_drift_forms_matrix.pdf"), bbox_inches="tight")
plt.close(fig)
print("Figure5 done")
