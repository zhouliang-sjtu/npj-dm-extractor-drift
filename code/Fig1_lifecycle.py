# -*- coding: utf-8 -*-
"""Fig1_lifecycle.py v3 —— Figure 1：治理生命周期总览（最终排版）"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import os

FIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "figures")
NAVY, GREEN, RED, ORANGE = "#1F3864", "#1E8449", "#C0392B", "#B9770E"
STAGE_FILL = ["#EAF1F8", "#E8F4EC", "#FDEDEC", "#FDF3E0"]
STAGE_EDGE = [NAVY, GREEN, RED, ORANGE]

fig, ax = plt.subplots(figsize=(15, 9.2))
ax.set_xlim(0, 100)
ax.set_ylim(0, 98)
ax.axis("off")

stages = [
    dict(x=1.5, w=22, num="STAGE 1", name="CALIBRATION", fill=STAGE_FILL[0], edge=STAGE_EDGE[0],
         q=["How is the gold", "standard produced?"],
         lines=[
             ("Evidence-based codebook v1.0", "4 domains · 28 variable defs · negation-first"),
             ("Blinded dual annotation", "A1 / A2 · 1,470 records · 4 domains"),
             ("Test–retest after ≥3 days", "intra-rater stability"),
             ("Rule-first arbitration", "every disagreement + reason"),
         ],
         badge="κ ≥ 0.80 on 31/31 variables\ngold standard + codebook V2.0"),
    dict(x=26, w=22, num="STAGE 2", name="ACCEPTANCE", fill=STAGE_FILL[1], edge=STAGE_EDGE[1],
         q=["When is the tool", "frozen for production?"],
         lines=[
             ("Pre-registered gates", "κ ≥ 0.80 · F1 ≥ 0.90 · acc ≥ 95%"),
             ("Dual-track vs gold standard", "dictionary track + LLM track"),
             ("Per-variable, per-year strata", "below-gate variables documented"),
             ("Freeze mechanism", "model + prompt → manifest"),
         ],
         badge="LLM track: 10/12 PASS\n→ FROZEN via manifest"),
    dict(x=50.5, w=22, num="STAGE 3", name="MONITORING", fill=STAGE_FILL[2], edge=STAGE_EDGE[2],
         q=["How is silent failure", "detected without gold standard?"],
         lines=[
             ("Drift monitor (8 signals)", "robust z vs 2018–2022 baseline"),
             ("Style family", "2022: enumeration z = 9.1 / 15.0"),
             ("Consistency family", "2023: collapse z = −4.7"),
             ("Field-domain validation", "cross-library control: no drop"),
         ],
         badge="ALARM: 2022 style · 2023 consistency\n→ failure in aggregation, not extractor"),
    dict(x=75, w=23.5, num="STAGE 4", name="RE-CALIBRATION", fill=STAGE_FILL[3], edge=STAGE_EDGE[3],
         q=["How is the failure", "adjudicated and fixed?"],
         lines=[
             ("Pre-registered adjudication", "4 strata · n = 160 · blinded"),
             ("Panel verdict (decision stratum)", "15% abnormal · 76% normal · 9% unreadable"),
             ("Decision rule fires", "→ explicit-positive outcome\n(CI upper 0.233 < 0.30)"),
             ("Dictionary updated + re-analysis", "naive HR 0.959 → 0.961 (FE);\nadjudicated 0.960"),
         ],
         badge="Codebook V3.0 + dictionary updated\nany-abnormality: 0/6 year-FE specs sig."),
]

BY = 36  # block bottom
for st in stages:
    ax.add_patch(FancyBboxPatch((st["x"], BY), st["w"], 58, boxstyle="round,pad=0.6",
                                fc=st["fill"], ec=st["edge"], lw=1.8, zorder=2))
    cx = st["x"] + st["w"] / 2
    ax.text(cx, 89.5, st["num"], ha="center", fontsize=9.5, color=st["edge"], fontweight="bold")
    ax.text(cx, 85.5, st["name"], ha="center", fontsize=13, color=st["edge"], fontweight="bold")
    for i, ql in enumerate(st["q"]):
        ax.text(cx, 82.2 - i * 2.6, ql, ha="center", fontsize=8.6, style="italic", color="#4a4a4a")
    ytxt = 76.5
    for main, sub in st["lines"]:
        ax.text(st["x"] + 1.0, ytxt, "▸ " + main, fontsize=8.6, fontweight="bold", va="top")
        for j, sl in enumerate(sub.split("\n")):
            ax.text(st["x"] + 2.2, ytxt - 2.7 - j * 2.5, sl, fontsize=7.5, color="#333333", va="top")
        ytxt -= 8.2
    ax.add_patch(FancyBboxPatch((st["x"] + 0.8, BY + 0.8), st["w"] - 1.6, 6.6,
                                boxstyle="round,pad=0.3", fc="white", ec=st["edge"], lw=1.0, zorder=3))
    ax.text(cx, BY + 4.1, st["badge"], ha="center", va="center", fontsize=7.0,
            color=st["edge"], fontweight="bold", zorder=4)

for x0, x1 in [(24.0, 25.6), (48.5, 50.1), (73.0, 74.6)]:
    ax.add_patch(FancyArrowPatch((x0, 67), (x1, 67), arrowstyle="-|>",
                                 mutation_scale=24, lw=2.4, color=NAVY, zorder=5))

# 闭环箭头（Re-calibration → 下一次 Calibration）
ax.add_patch(FancyArrowPatch((86.7, 30.0), (12.5, 30.0), arrowstyle="-|>",
                             mutation_scale=22, lw=2.2, color=ORANGE, zorder=5,
                             linestyle=(0, (6, 3))))
ax.text(50, 33.2, "Codebook V3.0 + updated dictionary feed the next calibration cycle — "
                  "a closed loop, not a one-shot validation",
        ha="center", fontsize=9.8, color=ORANGE, fontweight="bold")

# ---------- 底部时间轴（上：阶段注记；中：年份；下：箭头） ----------
ty = 11.5
ax.add_patch(FancyBboxPatch((1.5, 4.5), 97, 13, boxstyle="round,pad=0.3",
                            fc="#F7F9FB", ec="#B9C4CE", lw=1.0, zorder=1))
years = list(range(2018, 2025))
xs = [1.5 + 97 * (i + 0.5) / 7 for i in range(7)]
# 两段阶段注记：va="top" 顶对齐、整体压入色带内（带顶 17.5，字顶 ≈16.6）
ax.text(2 + 97 * 2 / 7, 16.6, "2018–2021 · tool calibrated, accepted, in production",
        ha="center", va="top", fontsize=9.2, color=GREEN, fontweight="bold", zorder=3)
ax.text(2 + 97 * 5.7 / 7, 16.6, "2022–2024 · drift alarms fired;\nadjudication + re-calibration executed",
        ha="center", va="top", fontsize=9.2, color=RED, fontweight="bold", zorder=3)
for x, y in zip(xs, years):
    ax.text(x, 10.6, str(y), ha="center", va="center", fontsize=10,
            fontweight="bold", color=NAVY, zorder=3)
# 箭头移到年份数字下方（留出间距，仍在色带内）
ax.annotate("", xy=(97.0, 7.6), xytext=(3.0, 7.6),
            arrowprops=dict(arrowstyle="-|>", lw=2.0, color=NAVY), zorder=2)
ax.text(50, 2.0, "Seven calendar years · 120,000+ person-year records · four text domains "
                 "(ECG conclusions · echocardiography · abdominal ultrasound × 2 sites)",
        ha="center", fontsize=9.2, color="#333333")

plt.savefig(os.path.join(FIG, "Figure1_lifecycle.png"), dpi=220, bbox_inches="tight")
plt.savefig(os.path.join(FIG, "Figure1_lifecycle.pdf"), bbox_inches="tight")
plt.close(fig)
print("Figure 1 v3 done")
