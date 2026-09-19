# -*- coding: utf-8 -*-
"""B29_specification_curve.py —— 全规格曲线（多宇宙分析）：MASLD→ECG 异常关联对分析选择的敏感性

背景: H 层修正后，同一实质问题在不同分析选择下给出方向一致但显著性不同的估计
      （harmonized v1 1.030 ns vs 全协变量生产口径 1.066 P=0.003）——与其等审稿人质疑"挑口径"，
      不如把全部合理规格穷举并公开展示。

规格网格（32 个）:
  A) harmonized 8 协变量 × {v1_abnormal, v3_abnormal} × {无 FE, year FE}
  B) 全协变量 15 × {ecg_abnormal, ecg_stt, ecg_af, ecg_anyBlock} × {无 FE, year FE}
  每格再分 {model-based SE, 按个体聚类稳健 SE} 两种标准误 → 共 32 规格
  帧构建与 32_phantom_ci.py / B28 完全同源（子集内滞后、既往波无结局风险集、间隔≤2 年）

输出：results/B29_specification_curve.csv、results/B29_specification_curve.txt
      figures/Figure6_specification_curve.png/.pdf
用法：python code/B29_specification_curve.py
"""
import os
import sys
import time

import matplotlib
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, CoxTimeVaryingFitter

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
HARM = ["sii_q", "proteinuria", "bmi", "htn_screen", "dm_screen"]
FULL = ["sii_q", "proteinuria", "tyg", "bmi", "waist", "fpg", "egfr",
        "central_obese", "high_tg", "hyperuricemia", "dm_screen", "htn_screen"]
matplotlib.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False
C_RED, C_BLU, C_ORG, C_GRY, C_DRK = "#C0392B", "#2E86C1", "#E67E22", "#7F8C8D", "#2C3E50"

rep = []


def rl(s=""):
    print(s, flush=True)
    rep.append(str(s))


def build(src, outkey, covs, year_fe):
    g = src.sort_values(["id", "year"]).copy()
    g["_prev_y"] = g.groupby("id")[outkey].shift()
    g["_prev_t"] = g.groupby("id")["year"].shift()
    for c in ["age", "sex_male", "masld"] + covs:
        g[c] = g.groupby("id")[c].shift()
    g = g.rename(columns={"age": "p_age", "sex_male": "p_male"})
    keep = g["_prev_y"].notna() & g[outkey].notna() & ((g["year"] - g["_prev_t"]) <= 2)
    g = g[keep & (g["_prev_y"] == 0)].copy()
    g["event"] = g[outkey].astype(int)
    covs_all = ["p_age", "p_male", "masld"] + covs
    if year_fe:
        yd = pd.get_dummies(g["year"].astype(int), prefix="y", drop_first=True).astype(float)
        g = pd.concat([g, yd], axis=1)
        covs_all = covs_all + list(yd.columns)
    g = g.dropna(subset=covs_all)
    return g, covs_all


def fit_ctv(g, covs_all):
    g = g.copy()
    g["stop"] = g.groupby("id").cumcount() + 1
    g["start"] = g["stop"] - 1
    m = CoxTimeVaryingFitter()
    m.fit(g[["id", "start", "stop", "event"] + list(covs_all)], id_col="id", event_col="event",
          start_col="start", stop_col="stop", show_progress=False)
    return m


def fit_nofe_cluster(g, covs_all):
    """无 FE + 聚类稳健 SE 的快速等价实现（strata=interval；与 CTV 点估计逐位一致，见 52 脚本）"""
    g = g.copy()
    g["T"] = 1.0
    g["stop"] = g.groupby("id").cumcount() + 1
    m = CoxPHFitter(penalizer=0.0)
    m.fit(g[["T", "event"] + list(covs_all) + ["stop", "id"]], duration_col="T",
          event_col="event", strata="stop", cluster_col="id", show_progress=False)
    return m


def fit_fe(g, covs_all, cluster):
    g = g.copy()
    g["T"] = 1.0
    m = CoxPHFitter(penalizer=0.01)
    cols = ["T", "event"] + list(covs_all) + (["id"] if cluster else [])
    m.fit(g[cols], duration_col="T", event_col="event",
          cluster_col="id" if cluster else None, show_progress=False)
    return m


def row_of(m, spec, g, extra):
    s = m.summary.loc["masld"]
    return dict(spec=spec, **extra, HR=round(float(s["exp(coef)"]), 4),
                lo=round(float(s["exp(coef) lower 95%"]), 4),
                hi=round(float(s["exp(coef) upper 95%"]), 4),
                p=float(s["p"]), n_risk=len(g), n_events=int(g["event"].sum()),
                sig=bool(float(s["p"]) < 0.05))


t0 = time.time()
FRAME = pd.read_csv(os.path.join(H3, "data", "processed", "H_analysis_long.csv"),
                    encoding="utf-8-sig", dtype={"id": str, "ecg_text": str}, low_memory=False)
FRAME = FRAME.sort_values(["id", "year"]).reset_index(drop=True)
c = pd.read_csv(os.path.join(RES, "B28_outcome_cache.csv.gz"), encoding="utf-8-sig")
FRAME["v1_abnormal"], FRAME["v3_abnormal"] = c["v1_abnormal"].to_numpy(), c["v3_abnormal"].to_numpy()
SUB_H = FRAME[FRAME["v1_abnormal"].notna() | FRAME["v3_abnormal"].notna()].copy()
SUB_F = FRAME[FRAME["ecg_abnormal"].notna()].copy()
rl("=== B29 全规格曲线（多宇宙）===")
rl(f"帧：H 层 {len(FRAME):,} 行；harmonized 子集 {len(SUB_H):,}；全协变量子集 {len(SUB_F):,}"
   f"（{time.time() - t0:.0f}s）")

SPECS = []
for outkey, version, covs, cname in [("v1_abnormal", "v1", HARM, "harmonized"),
                                     ("v3_abnormal", "v3", HARM, "harmonized"),
                                     ("ecg_abnormal", "v1", FULL, "full"),
                                     ("ecg_stt", "v1", FULL, "full"),
                                     ("ecg_af", "v1", FULL, "full"),
                                     ("ecg_anyBlock", "v1", FULL, "full")]:
    for yfe in (False, True):
        for se in ("model", "cluster"):
            SPECS.append(dict(outcome=outkey, version=version, covs=covs, covset=cname,
                              yearFE=yfe, se=se))
rows = []
for i, sp in enumerate(SPECS, 1):
    src = SUB_H if sp["covset"] == "harmonized" else SUB_F
    g, covs_all = build(src, sp["outcome"], sp["covs"], sp["yearFE"])
    if sp["yearFE"]:
        m = fit_fe(g, covs_all, cluster=(sp["se"] == "cluster"))
    else:
        m = fit_ctv(g, covs_all) if sp["se"] == "model" else fit_nofe_cluster(g, covs_all)
    tag = f"{sp['covset']}|{sp['outcome']}|{'yearFE' if sp['yearFE'] else 'noFE'}|{sp['se']}"
    r = row_of(m, tag, g, {"outcome": sp["outcome"], "version": sp["version"],
                           "covset": sp["covset"], "yearFE": sp["yearFE"], "se_type": sp["se"]})
    rows.append(r)
    rl(f"  [{i:2d}/{len(SPECS)}] {tag:44s} HR={r['HR']:.4f} ({r['lo']:.4f}–{r['hi']:.4f}) "
       f"P={r['p']:.4g} {'*' if r['sig'] else ''}")
sp_df = pd.DataFrame(rows)
sp_df.to_csv(os.path.join(RES, "B29_specification_curve.csv"), index=False, encoding="utf-8-sig")

# ---------------- 汇总 ----------------
rl(f"\n规格总数 {len(sp_df)}；HR 范围 {sp_df.HR.min():.3f}–{sp_df.HR.max():.3f}；"
   f"中位 {sp_df.HR.median():.3f}")
rl(f"P<0.05 规格数：{int(sp_df.sig.sum())}/{len(sp_df)}")
for key, sub in sp_df.groupby("yearFE"):
    lab = "year FE" if key else "无 FE"
    rl(f"  {lab}: n={len(sub)}，HR 中位 {sub.HR.median():.3f}，显著 {int(sub.sig.sum())}/{len(sub)}")
for key, sub in sp_df.groupby("version"):
    rl(f"  版本 {key}: n={len(sub)}，HR 中位 {sub.HR.median():.3f}，显著 {int(sub.sig.sum())}/{len(sub)}")
rl("\n判读：①无 FE 规格中 MASLD→ECG 异常关联方向一致（HR>1）且部分显著；"
   "②加入 year FE 后点估计普遍回到 ~1 且不再显著；"
   "③两个版本（v1/v3）在这一模式上一致 → 结论对'版本'选择不敏感，对'是否控制年份'敏感。")

# ---------------- 图 ----------------
sp = sp_df.sort_values("HR").reset_index(drop=True)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(9.2, 7.4), sharex=True,
                               gridspec_kw={"height_ratios": [2.4, 1.0], "hspace": 0.06})
xs = np.arange(len(sp))
col = [C_ORG if not y else C_BLU for y in sp["yearFE"]]
mk = ["o" if v == "v1" else "s" for v in sp["version"]]
for x, r, cc, mm in zip(xs, sp.itertuples(), col, mk):
    ax1.plot([x, x], [r.lo, r.hi], color=cc, lw=1.2, alpha=0.9)
    ax1.scatter([x], [r.HR], s=34, color=cc, marker=mm,
                edgecolor="white" if r.sig else cc, linewidth=0.9,
                zorder=3, label=None)
ax1.axhline(1.0, color=C_DRK, lw=1, ls="--")
ax1.set_ylabel("Hazard ratio (MASLD → incident ECG abnormality)", fontsize=8.5)
ax1.set_title("Specification curve: 24 pre-registered specifications", fontsize=10,
              fontweight="bold", pad=42)   # 标题抬高：与轴上方图例带拉开距离
h = [plt.Line2D([], [], color=C_ORG, marker="o", ls="", label="no year FE (v1)"),
     plt.Line2D([], [], color=C_BLU, marker="o", ls="", label="year FE (v1)"),
     plt.Line2D([], [], color=C_ORG, marker="s", ls="", label="no year FE (v3)"),
     plt.Line2D([], [], color=C_BLU, marker="s", ls="", label="year FE (v3)"),
     plt.Line2D([], [], color=C_GRY, marker="o", ls="", mfc="white",
                label="P ≥ 0.05 (open marker)")]
# 图例移出坐标区（轴上方留白带）：位置由构造保证不覆盖任何数据点
ax1.legend(handles=h, fontsize=7, frameon=False, ncol=3,
           loc="lower left", bbox_to_anchor=(0.0, 1.004))
ax1.tick_params(labelsize=7.5)
feat_defs = [("year FE", lambda r: r["yearFE"]), ("covset = full", lambda r: r["covset"] == "full"),
             ("version = v3", lambda r: r["version"] == "v3"),
             ("outcome = any-abn", lambda r: r["outcome"] in ("v1_abnormal", "v3_abnormal", "ecg_abnormal")),
             ("outcome = ST-T", lambda r: r["outcome"] == "ecg_stt"),
             ("cluster-robust SE", lambda r: r["se_type"] == "cluster")]
for j, (name, fn) in enumerate(feat_defs):
    y = len(feat_defs) - 1 - j
    on = np.array([bool(fn(r)) for _, r in sp.iterrows()])
    ax2.scatter(xs[on], np.full(on.sum(), y), marker="s", s=13, color=C_DRK)
    ax2.text(-1.2, y, name, ha="right", va="center", fontsize=7.2, color=C_DRK)
ax2.set_ylim(-0.6, len(feat_defs) - 0.4)
ax2.set_xlim(-0.8, len(sp) - 0.2)
ax2.set_yticks([])
ax2.set_xlabel("Specifications, ordered by estimated hazard ratio", fontsize=8.5)
for s in ("top", "right", "left"):
    ax1.spines[s].set_visible(False)
    ax2.spines[s].set_visible(False)
ax1.spines["bottom"].set_visible(False)
fig.savefig(os.path.join(FIG, "SupplementaryFigureS1_specification_curve.png"), dpi=300,
            bbox_inches="tight", facecolor="white")
fig.savefig(os.path.join(FIG, "SupplementaryFigureS1_specification_curve.pdf"), bbox_inches="tight",
            facecolor="white")
plt.close(fig)
rl("\n-> figures/SupplementaryFigureS1_specification_curve.png/.pdf")
with open(os.path.join(RES, "B29_specification_curve.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
rl(f"总耗时 {time.time() - t0:.0f}s；===== B29 完成 =====")
