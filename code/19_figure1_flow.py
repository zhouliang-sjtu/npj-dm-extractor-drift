# -*- coding: utf-8 -*-
"""19_figure1_flow.py — Figure 1: Study design, cohort assembly and gold-standard construction.
npj Digital Medicine style: Arial 8pt, 300 dpi, white background, colour-blind-safe
(Okabe-Ito palette; no red/green contrast), panels a)-b)-c) on a single page.
2026-09-10 layout revision: even vertical rhythm (auto-computed gaps), body text
rewrapped to <=42 chars/line at 5.7 pt (no box overflow), bar chart aligned to the
box column, inter-panel arrows rewired to true data provenance (PG -> cardiac and
abdominal-ultrasound samples), counts synced to the audited build
(30,677 individuals; 121,543 non-empty; 121,283 analysed).
Outputs: figures/fig1_cohort_flow.png (300 dpi) + figures/fig1_cohort_flow.pdf (vector)
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.path import Path
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "figures")
os.makedirs(OUT, exist_ok=True)

# ---- palette (Okabe-Ito, colour-blind-safe) ----
BLUE, ORANGE, GREEN, VERM = "#0072B2", "#E69F00", "#009E73", "#D55E00"
GREY, LIGHT = "#4D4D4D", "#F5F5F5"

plt.rcParams.update({
    "font.family": "Arial",
    "font.size": 8,
    "axes.linewidth": 0.6,
    "savefig.dpi": 300,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
})

fig = plt.figure(figsize=(7.05, 4.65))
axa = fig.add_axes([0.020, 0.030, 0.305, 0.845])
axa.axis("off")
axb = fig.add_axes([0.360, 0.030, 0.290, 0.845])
axb.axis("off")
axc = fig.add_axes([0.685, 0.030, 0.305, 0.845])
axc.axis("off")


def box(ax, x, y, w, h, title, body="", ec=GREY, fc="#FFFFFF", lw=0.9,
        tfs=7.0, bfs=5.7, tf=0.72, bf=0.28):
    """Rounded box with a bold title line and an optional body block.

    tf/bf = vertical centre fractions of the title/body blocks (axes units);
    raise tf and bf for 3-4 line bodies so the text stays inside the frame.
    """
    ax.add_patch(FancyBboxPatch(
        (x, y), w, h,
        boxstyle="round,pad=0.004,rounding_size=0.012",
        linewidth=lw, edgecolor=ec, facecolor=fc, mutation_aspect=1.0))
    if body:
        ax.text(x + w / 2, y + h * tf, title, ha="center", va="center",
                fontsize=tfs, fontweight="bold", color="#111111")
        ax.text(x + w / 2, y + h * bf, body, ha="center", va="center",
                fontsize=bfs, color="#222222", linespacing=1.35)
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center",
                fontsize=tfs, fontweight="bold", color="#111111")


def arrow(ax, y1, y2, x=0.5):
    ax.add_patch(FancyArrowPatch((x, y1), (x, y2), arrowstyle="-|>",
                                 mutation_scale=6.5, color=GREY, lw=0.9))


def stack(heights, y0=0.020, y1=0.990, pad=0.010):
    """Even-rhythm vertical layout: equal gaps, top-anchored at y1, bottom at y0.

    Returns list of (y_bottom, h) top-first and the common gap; arrow spans use
    `pad` clearance inside each gap.
    """
    gap = (y1 - y0 - sum(heights)) / (len(heights) - 1)
    pos, y = [], y1
    for h in heights:
        pos.append((y - h, h))
        y -= h + gap
    return pos, gap


def stack_arrows(ax, pos, pad=0.006):
    for i in range(len(pos) - 1):
        y_low_top = pos[i + 1][0] + pos[i + 1][1]
        y_up_bot = pos[i][0]
        arrow(ax, y_low_top + pad, y_up_bot - pad)


def panel_label(ax, letter):
    ax.text(-0.015, 1.015, letter, transform=ax.transAxes, fontsize=10,
            fontweight="bold", ha="left", va="top")


# ================= panel a — cohort assembly =================
panel_label(axa, "a")
box(axa, 0.03, 0.855, 0.94, 0.135,
    "Community health-checkup cohort",
    "2018\u20132024 \u00b7 7 annual waves\n30,677 individuals \u00b7 122,575 visit-records")
arrow(axa, 0.851, 0.804)
box(axa, 0.03, 0.695, 0.94, 0.105,
    "Readable ECG narratives",
    "121,543 non-empty (\u2264150 characters)\n121,283 classifiable \u2192 analysed")
arrow(axa, 0.691, 0.652)

# per-year bar chart (analysed narratives, audited build; sums to 121,283)
years = [2018, 2019, 2020, 2021, 2022, 2023, 2024]
narr = [14303, 16278, 16095, 15547, 17149, 21357, 20554]
trans = {2022, 2023}
axbar = fig.add_axes([0.031, 0.178, 0.277, 0.400])  # 上移+降高：a2→柱图箭杆加长，且与 PG 框保持间距（柱轴顶 axa 0.648）
cols = [ORANGE if y in trans else BLUE for y in years]
axbar.bar(range(7), narr, width=0.62, color=cols, edgecolor="none")
for i, v in enumerate(narr):
    axbar.text(i, v + 500, f"{v:,}", ha="center", va="bottom",
               fontsize=5.0, rotation=90, color="#111111")
axbar.set_xticks(range(7))
axbar.set_xticklabels([str(y) for y in years], fontsize=5.6, rotation=45)
axbar.set_yticks([])
axbar.set_ylim(0, 27500)
# 标题画在轴内左上（避免 set_title 与上方 a2 框底边冲突），Σn 注记紧随其下
axbar.text(0.02, 0.995, "Analysed ECG narratives per year", transform=axbar.transAxes,
           fontsize=6.8, fontweight="bold", ha="left", va="top", color="#111111")
axbar.text(0.02, 0.895, "\u03a3n = 121,283\norange: template\ntransition (2022\u201323)",
           transform=axbar.transAxes, ha="left", va="top",
           fontsize=5.0, color="#444444", linespacing=1.3)
for s in ("top", "right", "left"):
    axbar.spines[s].set_visible(False)
axbar.tick_params(axis="x", length=1.5, pad=1)

# deep-phenotyping source box (feeds echo branches in panel b)
box(axa, 0.03, 0.012, 0.94, 0.098,
    "Deep-phenotyping cardiac ultrasound (PG)",
    "2023\u20132026 \u00b7 3 waves \u00b7 independent\nof the checkup cohort",
    ec=ORANGE, tfs=6.6)

# ================= panel b — stratified sampling =================
panel_label(axb, "b")
b_pos, b_gap = stack([0.135, 0.175, 0.175, 0.185, 0.095])
box(axb, 0.03, b_pos[0][0], 0.94, b_pos[0][1],
    "Hierarchical stratified sampling",
    "nested parent\u2013subset design \u00b7 seed = 42\nsampling frame frozen before annotation",
    tf=0.76, bf=0.32)
box(axb, 0.03, b_pos[1][0], 0.94, b_pos[1][1],
    "1. ECG conclusions \u2014 n = 570",
    "mother 600 = 60/year + 50/layer\n(AF \u00b7 conduction block \u00b7 ST-T)\n\u2192 570 reports (de-duplicated), all analysed",
    ec=BLUE, tf=0.76, bf=0.32)
box(axb, 0.03, b_pos[2][0], 0.94, b_pos[2][1],
    "2. Cardiac ultrasound \u2014 n = 300",
    "source: deep-phenotyping (panel a, bottom)\nparent 600: rule-predicted 304/149/147\n\u2192 300 nested (150/75/75)",
    ec=ORANGE, tf=0.76, bf=0.32)
box(axb, 0.03, b_pos[3][0], 0.94, b_pos[3][1],
    "3. Abdominal ultrasound \u2014 300 + 300",
    "deep-phenotyping source: 300\n(150 rule+ / 150 rule\u2212)\ncommunity source: 300\n(30/year + 90 positive top-up)",
    ec=GREEN, tfs=6.8, tf=0.80, bf=0.34)
box(axb, 0.03, b_pos[4][0], 0.94, b_pos[4][1],
    "Double-annotated adjudicated gold standard",
    "n = 1,470 (570 + 300 + 300 + 300)", fc=LIGHT, tfs=6.3)
stack_arrows(axb, b_pos)

# ================= panel c — annotation & governance =================
panel_label(axc, "c")
c_pos, c_gap = stack([0.135, 0.125, 0.105, 0.170, 0.170])
box(axc, 0.03, c_pos[0][0], 0.94, c_pos[0][1],
    "Dual independent blinded annotation",
    "two clinicians per domain (A1 \u00d7 A2)\n+ 10% intra-rater self-repeats",
    tf=0.76, bf=0.32)
box(axc, 0.03, c_pos[1][0], 0.94, c_pos[1][1],
    "Adjudication",
    "flag/note \u2192 senior-clinician ruling\ncodebook v2.0 revisions logged",
    tf=0.76, bf=0.32)
box(axc, 0.03, c_pos[2][0], 0.94, c_pos[2][1],
    "Gold standard \u2014 n = 1,470",
    "adjudicated reference standard (frozen)", fc=LIGHT)
box(axc, 0.03, c_pos[3][0], 0.94, c_pos[3][1],
    "Acceptance gates",
    "\u03ba \u2265 0.80 \u00b7 class F1 \u2265 0.90\naccuracy \u2265 95% \u00b7 stratum \u2265 90%\nfailing layer \u2192 codebook v2.0\n+ re-annotation of that layer",
    ec=VERM, tf=0.80, bf=0.34)
box(axc, 0.03, c_pos[4][0], 0.94, c_pos[4][1],
    "Frozen extractor manifest",
    "prompt SHA-256 \u00b7 dual-track archive\nupgrades = sensitivity analyses only\n\u2192 \u03ba\u2192HR bias grids + year-FE\nfalsification test",
    tf=0.80, bf=0.34)
stack_arrows(axc, c_pos)

# ================= inter-panel arrows (data provenance) =================
def to_fig(a, xy):
    """panel 轴坐标 → figure 坐标（跨面板折弯箭头用统一坐标系）"""
    return fig.transFigure.inverted().transform(a.transAxes.transform(xy))


def elbow(a, ya, b, yb, xm):
    """Z 形折弯虚线箭头：A 右缘水平出发 → 面板间隙中线垂直走段 → 水平进入 B 左缘。
    xm 显式错开可避免多条垂直段相互重叠。"""
    x0, y0 = to_fig(a, (1.0, ya))
    x1, y1 = to_fig(b, (0.0, yb))
    verts = [(x0, y0), (xm, y0), (xm, y1), (x1, y1)]
    codes = [Path.MOVETO, Path.LINETO, Path.LINETO, Path.LINETO]
    fig.add_artist(FancyArrowPatch(path=Path(verts, codes), arrowstyle="-|>",
                                   mutation_scale=9, color=GREY, lw=0.9,
                                   linestyle=(0, (4, 2)), shrinkA=1, shrinkB=1))


def mid(pos_i):
    return pos_i[0] + pos_i[1] / 2.0

XM_AB, XM_AB2, XM_AB3 = 0.3425, 0.3375, 0.3475   # a-b 间隙中线（PG 两臂错开避让）
XM_BC = 0.6675                                    # b-c 间隙中线
elbow(axa, 0.9225, axb, mid(b_pos[0]), XM_AB)   # checkup cohort -> sampling frame
elbow(axa, 0.7475, axb, mid(b_pos[1]), XM_AB)   # readable ECG -> ECG sample
elbow(axa, 0.0860, axb, mid(b_pos[2]), XM_AB2)  # PG source -> cardiac ultrasound
elbow(axa, 0.0300, axb, mid(b_pos[3]), XM_AB3)  # PG source -> abdominal ultrasound (PG arm)
elbow(axb, mid(b_pos[4]), axc, mid(c_pos[2]), XM_BC)  # assembled gold standard (b) = frozen reference (c)

png = os.path.join(OUT, "fig1_cohort_flow.png")
pdf = os.path.join(OUT, "fig1_cohort_flow.pdf")
fig.savefig(png, dpi=300, facecolor="white")
fig.savefig(pdf, facecolor="white")
print("saved:", png)
print("saved:", pdf)
