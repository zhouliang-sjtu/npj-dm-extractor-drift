# -*- coding: utf-8 -*-
"""06_phantom_simex.py —— 幻影信号分解 + SIMEX错分-衰减网格（不依赖金标准/LLM，2026-09-02）
Part A: 幻影信号分解——MASLD暴露×4个ECG结局，原始Cox vs 年份FE Cox（数据源: 03-/results）
Part B: SIMEX网格——对称错分(Se=Sp=s)解析矩阵法：给定κ与患病率π解出s，
        HR_obs = [πSe·HR+(1-π)(1-Sp)] / [π(1-Se)·HR+(1-π)Sp]
        κ∈[0.60,0.95]×HR_true∈[1.0,1.8]；实测κ出来后在其行标注即可
输出: results/phantom_decomposition.csv + results/simex_kappa_grid.csv
      results/fig3_phantom_forest.png + results/fig5_simex_grid.png
用法: python code/06_phantom_simex.py
"""
import os

import matplotlib
import numpy as np
import pandas as pd
from scipy.optimize import brentq

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
RES = os.path.join(BASE, "results")
os.makedirs(RES, exist_ok=True)

# ================= Part A: 幻影信号分解 =================
orig = pd.read_csv(H3 + "/results/ecg_newonset_cox.csv")
yfe = pd.read_csv(H3 + "/results/ecg_newonset_cox_yearfe.csv")

rows = []
for oc in ["anyAbnormal", "STT", "AF", "anyBlock"]:
    o = orig[(orig["outcome"] == oc) & (orig["covariate"] == "masld")].iloc[0]
    y = yfe[(yfe["outcome"] == oc + "_yearFE") & (yfe["covariate"] == "masld")]
    hr_o, p_o = float(o["exp(coef)"]), float(o["p"])
    hr_y = float(y.iloc[0]["exp(coef)"]) if len(y) else np.nan
    p_y = float(y.iloc[0]["p"]) if len(y) else np.nan
    if pd.isna(p_y):
        verdict = "no_yearFE_fit"
    elif p_o >= 0.05:
        verdict = "no_signal"
    elif p_y >= 0.05:
        verdict = "vanishes_under_yearFE"
    elif hr_y < hr_o * 0.98:
        verdict = "attenuates"
    else:
        verdict = "robust"
    rows.append({"outcome": oc, "exposure": "masld",
                 "HR_orig": round(hr_o, 3), "p_orig": round(p_o, 4),
                 "HR_yearFE": round(hr_y, 3), "p_yearFE": round(p_y, 4),
                 "delta_pct": round((hr_o - hr_y) / hr_o * 100, 1), "verdict": verdict})
dec = pd.DataFrame(rows)
dec.to_csv(RES + "/phantom_decomposition.csv", index=False, encoding="utf-8-sig")
print("=== Part A 幻影信号分解（暴露=MASLD，结局=ECG异常新发） ===")
print(dec.to_string(index=False))

# Fig3初版: 森林图
fig, ax = plt.subplots(figsize=(7.5, 4.2))
ys = np.arange(len(dec))[::-1]
for i, (_, r) in zip(ys, dec.iterrows()):
    ax.plot([1, max(r["HR_orig"], r["HR_yearFE"] or 0, 1.15) * 1.05], [i, i],
            color="#cccccc", lw=0.8, zorder=1)
    ax.scatter([r["HR_orig"]], [i + 0.12], marker="s", s=55, color="#d62728",
               label="Original HR" if i == ys[0] else None, zorder=3)
    if pd.notna(r["HR_yearFE"]):
        ax.scatter([r["HR_yearFE"]], [i - 0.12], marker="D", s=55, color="#1f77b4",
                   label="Year-FE HR" if i == ys[0] else None, zorder=3)
ax.axvline(1, color="black", lw=1)
ax.set_yticks(ys)
ax.set_yticklabels(dec["outcome"])
ax.set_xlabel("HR (MASLD -> incident ECG abnormality)")
ax.set_title("Phantom signal decomposition: original vs year-FE (dict v1)")
ax.legend(loc="lower right", frameon=False)
fig.tight_layout()
fig.savefig(RES + "/fig3_phantom_forest.png", dpi=200)
plt.close(fig)
print(f"-> {RES}/fig3_phantom_forest.png")

# ================= Part B: SIMEX κ网格（解析矩阵法） =================
dfh = pd.read_csv(H3 + "/data/processed/H_analysis_long.csv", encoding="utf-8-sig", low_memory=False)
pi = float(dfh["masld"].dropna().mean())
print(f"\nMASLD患病率 π = {pi:.4f}")


def solve_s(kappa, pi):
    """对称错分 Se=Sp=s：po=s, p1*=pi*s+(1-pi)*(1-s), pe=p1*^2+(1-p1*)^2, kappa=(po-pe)/(1-pe)"""
    def f(s):
        p1 = pi * s + (1 - pi) * (1 - s)
        pe = p1 * p1 + (1 - p1) ** 2
        po = s
        return (po - pe) / (1 - pe) - kappa
    return brentq(f, 0.5, 0.99999)


rows = []
for kappa in np.round(np.arange(0.60, 0.96, 0.05), 2):
    s = solve_s(kappa, pi)
    p1 = pi * s + (1 - pi) * (1 - s)   # 观察阳性率
    p0 = 1 - p1
    for hr_true in np.round(np.arange(1.0, 1.81, 0.1), 2):
        num = pi * s * hr_true + (1 - pi) * (1 - s)   # P(X=1|X*=1)*h1 + P(X=0|X*=1)*h0（未归一）
        den = pi * (1 - s) * hr_true + (1 - pi) * s   # P(X=1|X*=0)*h1 + P(X=0|X*=0)*h0
        hr_obs = (num / p1) / (den / p0)              # 归一化后相除（HR=1时恒等于1）
        rows.append({"kappa": kappa, "Se=Sp": round(s, 4), "prevalence_pi": round(pi, 4),
                     "HR_true": hr_true, "HR_obs": round(hr_obs, 4),
                     "attenuation_pct": round((1 - hr_obs / hr_true) * 100, 1)})
grid = pd.DataFrame(rows)
grid.to_csv(RES + "/simex_kappa_grid.csv", index=False, encoding="utf-8-sig")
print("=== Part B SIMEX κ网格（节选） ===")
print(grid[grid["HR_true"].isin([1.0, 1.3, 1.5])].pivot(
    index="kappa", columns="HR_true", values="HR_obs").to_string())

# Fig5: 衰减曲线族
fig, ax = plt.subplots(figsize=(7.5, 5.2))
cmap = plt.get_cmap("viridis")
for i, (k, g) in enumerate(grid.groupby("kappa")):
    g = g.sort_values("HR_true")
    ax.plot(g["HR_true"], g["HR_obs"], color=cmap(i / 7), lw=1.8,
            label=f"κ={k:.2f} (Se=Sp={g['Se=Sp'].iloc[0]:.2f})")
ax.plot([1, 1.8], [1, 1.8], "k--", lw=1, label="No misclassification (diagonal)")
ax.axhline(1, color="grey", lw=0.6)
ax.set_xlabel("True effect HR_true")
ax.set_ylabel("Observed HR_obs (under nondifferential misclassification)")
ax.set_title(f"Misclassification attenuation grid (pi={pi:.2f}, Se=Sp symmetric)\n"
             "Annotate measured kappa here after double-annotation")
ax.legend(loc="upper left", fontsize=8, frameon=False)
fig.tight_layout()
fig.savefig(RES + "/fig5_simex_grid.png", dpi=200)
plt.close(fig)
print(f"-> {RES}/fig5_simex_grid.png")
