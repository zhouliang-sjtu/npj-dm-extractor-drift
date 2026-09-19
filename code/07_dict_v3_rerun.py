# -*- coding: utf-8 -*-
"""07_dict_v3_rerun.py —— 词典v3全库重跑 + v1×v3年份交互（不依赖LLM/金标准，2026-09-02）
目的：量化"抽取器版本×年份"交互——同一文本库、两个词典版本（v1主库现状 vs v3口径）：
  1) v3 全库重抽取（main.extract_ecg）
  2) v1/v3 任何异常 的总体+分年份一致率（Cohen κ）
  3) 三套离散时间Cox（暴露=MASLD prev波）：v1结局 / v1+yearFE / v3结局 / v3+yearFE
输出: results/dict_v1_v3_agreement.csv
      results/phantom_v1_vs_v3_cox.csv
      results/fig_v1_v3_interact.png
用法: python code/07_dict_v3_rerun.py
"""
import os
import sys

import matplotlib
import numpy as np
import pandas as pd
from lifelines import CoxTimeVaryingFitter

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
RES = os.path.join(BASE, "results")
os.makedirs(RES, exist_ok=True)
sys.path.insert(0, os.path.join(BASE, "code"))
from main import extract_ecg, norm  # noqa: E402

df = pd.read_csv(H3 + "/data/processed/H_analysis_long.csv", encoding="utf-8-sig",
                 dtype={"id": str, "ecg_text": str}, low_memory=False)
df = df.sort_values(["id", "year"]).reset_index(drop=True)
print(f"H_analysis_long: {len(df)} 行 / {df['id'].nunique()} 人")

# ---------- 1. v3 全库重抽取 ----------
m = df["ecg_text"].notna()
res = df.loc[m, "ecg_text"].map(lambda t: extract_ecg(norm(t)))
v3 = pd.DataFrame(res.tolist())
for c in v3.columns:
    df.loc[m, "v3_" + c] = v3[c].values
df["v3_abnormal"] = ((df["v3_ecg_normal"] == 0) & (df["v3_ecg_unreadable"] == 0)).astype(float)
df.loc[~m, "v3_abnormal"] = np.nan
df["v1_abnormal"] = df["ecg_abnormal"].astype(float)
print(f"v3可判读: {int(df['v3_abnormal'].notna().sum())} 行；v1可判读: {int(df['v1_abnormal'].notna().sum())} 行")

# ---------- 2. v1×v3 分年份一致率 ----------
def kappa(a, b):
    po = float((a == b).mean())
    pe = sum(float((a == L).mean()) * float((b == L).mean()) for L in (0, 1))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


d = df.dropna(subset=["v1_abnormal", "v3_abnormal"])
rows = [{"scope": "overall", "year": "all", "n": len(d),
         "pct_agree": round(float((d["v1_abnormal"] == d["v3_abnormal"]).mean()) * 100, 2),
         "cohen_kappa": round(kappa(d["v1_abnormal"].astype(int), d["v3_abnormal"].astype(int)), 3),
         "pct_v1_abn": round(float(d["v1_abnormal"].mean()) * 100, 2),
         "pct_v3_abn": round(float(d["v3_abnormal"].mean()) * 100, 2)}]
for y, g in d.groupby("year"):
    rows.append({"scope": "by_year", "year": int(y), "n": len(g),
                 "pct_agree": round(float((g["v1_abnormal"] == g["v3_abnormal"]).mean()) * 100, 2),
                 "cohen_kappa": round(kappa(g["v1_abnormal"].astype(int), g["v3_abnormal"].astype(int)), 3),
                 "pct_v1_abn": round(float(g["v1_abnormal"].mean()) * 100, 2),
                 "pct_v3_abn": round(float(g["v3_abnormal"].mean()) * 100, 2)})
agr = pd.DataFrame(rows)
agr.to_csv(RES + "/dict_v1_v3_agreement.csv", index=False, encoding="utf-8-sig")
print("\n=== v1×v3 任何异常一致率（分年份） ===")
print(agr.to_string(index=False))

# ---------- 3. 四套Cox（v1/v3 × 原始/yearFE） ----------
COVS = ["masld", "sii_q", "proteinuria", "bmi", "htn_screen", "dm_screen"]


def discrete_cox(frame, outkey, tag, year_fe=False):
    """结局=outkey新发；暴露与协变量均取prev波（与10_explore口径一致）。
    year_fe=False: CoxTimeVarying(区间)；True: CoxPHFitter(T=1, penalizer=0.01, cluster=id)——
    后者为23_yearfe_dm同款做法，规避year哑变量与区间序号共线奇异。"""
    from lifelines import CoxPHFitter
    g = frame.sort_values(["id", "year"]).copy()
    g["_prev_y"] = g.groupby("id")[outkey].shift()
    g["_prev_t"] = g.groupby("id")["year"].shift()
    for c in ["age", "sex_male"] + COVS:
        g[c] = g.groupby("id")[c].shift()
    g = g.rename(columns={"age": "p_age", "sex_male": "p_male"})
    keep = g["_prev_y"].notna() & g[outkey].notna() & ((g["year"] - g["_prev_t"]) <= 2)
    g = g[keep & (g["_prev_y"] == 0)].copy()
    if len(g) < 200:
        print(f"  {tag}: 风险集过小({len(g)})")
        return None
    g["event"] = g[outkey].astype(int)
    covs_all = ["p_age", "p_male"] + COVS
    if year_fe:
        ydum = pd.get_dummies(g["year"].astype(int), prefix="y", drop_first=True).astype(float)
        g = pd.concat([g, ydum], axis=1)
        covs_all = covs_all + list(ydum.columns)
    g = g.dropna(subset=covs_all)
    if year_fe:
        g["T"] = 1.0
        cph = CoxPHFitter(penalizer=0.01)
        cph.fit(g[["T", "event"] + covs_all + ["id"]], duration_col="T", event_col="event",
                cluster_col="id", show_progress=False)
        s = cph.summary.reset_index()
    else:
        g["stop"] = g.groupby("id").cumcount() + 1
        g["start"] = g["stop"] - 1
        ctv = CoxTimeVaryingFitter()
        ctv.fit(g[["id", "start", "stop", "event"] + covs_all], id_col="id", event_col="event",
                start_col="start", stop_col="stop", show_progress=False)
        s = ctv.summary.reset_index()
    s = s[s["covariate"] == "masld"]
    s.insert(0, "model", tag)
    s.insert(1, "n_risk", len(g))
    s.insert(2, "n_events", int(g["event"].sum()))
    return s[["model", "n_risk", "n_events", "covariate", "coef", "exp(coef)", "p"]]


ecgdf = df[df["v1_abnormal"].notna() | df["v3_abnormal"].notna()].copy()
fits = []
for tag, key, yfe in [("v1_orig", "v1_abnormal", False), ("v1_yearFE", "v1_abnormal", True),
                      ("v3_orig", "v3_abnormal", False), ("v3_yearFE", "v3_abnormal", True)]:
    print(f"拟合 {tag} ...")
    r = discrete_cox(ecgdf, key, tag, year_fe=yfe)
    if r is not None:
        fits.append(r)
cox = pd.concat(fits, ignore_index=True)
cox.to_csv(RES + "/phantom_v1_vs_v3_cox.csv", index=False, encoding="utf-8-sig")
print("\n=== MASLD→ECG任何异常新发：抽取器版本×年份FE 四套对比 ===")
print(cox[["model", "n_risk", "n_events", "exp(coef)", "p"]].to_string(index=False))

# ---------- 4. 交互图（英文标签，避免字体缺字形；标注错行防遮挡） ----------
fig, ax = plt.subplots(figsize=(8.4, 4.8))
models = cox["model"].tolist()
hrs = cox["exp(coef)"].tolist()
ps = cox["p"].tolist()
n = len(models)
ys = list(range(n))[::-1]
for i, (m_, hr, p_) in enumerate(zip(models, hrs, ps)):
    c = "#d62728" if "v1" in m_ else "#1f77b4"
    mk = "s" if "yearFE" not in m_ else "D"
    y = ys[i]
    ax.plot([1, hr], [y, y], color=c, lw=0.8, alpha=0.35, zorder=1)
    ax.scatter([hr], [y], marker=mk, s=85, color=c, zorder=3)
    ax.annotate(f"HR={hr:.3f}\np={p_:.2g}", xy=(hr, y), xytext=(10, 0),
                textcoords="offset points", va="center", fontsize=8.5, color=c)
ax.axvline(1, color="black", lw=1)
ax.set_yticks(ys)
ax.set_yticklabels(models)
ax.set_xlim(min(hrs + [1]) * 0.96, max(hrs) * 1.42)
ax.set_xlabel("HR (MASLD -> incident any-ECG-abnormality, discrete-time Cox)")
ax.set_title("Extractor-version x year-FE interaction (dict v1 vs v3)")
from matplotlib.lines import Line2D  # noqa: E402
handles = [
    Line2D([], [], marker="s", ls="", color="#d62728", label="dict v1"),
    Line2D([], [], marker="D", ls="", color="#d62728", label="dict v1 + year-FE"),
    Line2D([], [], marker="s", ls="", color="#1f77b4", label="dict v3"),
    Line2D([], [], marker="D", ls="", color="#1f77b4", label="dict v3 + year-FE"),
]
ax.legend(handles=handles, loc="lower right", fontsize=8.5, frameon=False)
fig.tight_layout()
fig.savefig(RES + "/fig_v1_v3_interact.png", dpi=200)
plt.close(fig)
print(f"-> {RES}/fig_v1_v3_interact.png")
