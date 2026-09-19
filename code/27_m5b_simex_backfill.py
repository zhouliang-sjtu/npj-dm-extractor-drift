# -*- coding: utf-8 -*-
"""27_m5b_simex_backfill.py —— M5b：实测κ回填SIMEX网格 + 校正HR（R2/Fig5b）
实测κ = 生产词典 v1 的 us_fatty vs 金标准终值（ABDUS_PG 300 + ABDUS_H 300，共识终值），
v1 规则与生产 main.py extract_abd 完全一致（"脂肪肝"字样 或 细密+衰减/欠清 描述式）。
推导：κ→Se=Sp（对称，解析法同 code/06）；HR_obs(HR_true) 风险混合公式数值反演出 HR_true。
对两个已报告 HR 做校正：v3 anyAbnormal（幻影）、fullcov ST-T（特异匹配）；
观测值由 results/phantom_specs_table.csv 读取（不硬编码）。
输出：results/m5b_simex_kappa.csv、results/m5b_simex_backfill.csv、results/fig5b_simex_measured.png
用法：python code/27_m5b_simex_backfill.py
"""
import os
import re
import sys

import matplotlib
import numpy as np
import pandas as pd
from scipy.optimize import brentq

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FINAL = os.path.join(ROOT, "data", "金标准标注工作簿_终版.xlsx")
RES = os.path.join(ROOT, "results")
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
PI = None  # 运行时按 06 同口径取（下方计算），避免硬编码随数据修正漂移
# 观测HR 一律从权威表读取（code/32 phantom_specs_table.csv），避免硬编码随数据修正漂移
_SPEC_SRC = os.path.join(ROOT, "results", "phantom_specs_table.csv")
_SPEC = pd.read_csv(_SPEC_SRC, encoding="utf-8-sig").set_index("spec")["HR"].astype(float)
OBS_HRS = {"HR_obs_v3_anyAbnormal": float(_SPEC["harmonized_v3"]),
           "HR_obs_fullcov_STT": float(_SPEC["fullcov_STT"])}


def v1_fatty(text):
    """生产词典 v1 us_fatty 规则（main.py extract_abd 的 fatty 分支，逐字对齐）"""
    t = str(text or "")
    in_us = bool(re.search(r"脂肪肝", t))          # gold 文本已合并所见+主检，单次检索等价
    desc_hit = bool(re.search(r"细密", t) and re.search(r"衰减|欠清", t))
    return 1 if (in_us or desc_hit) else 0


def solve_s(kappa, pi=None):
    pi = PI if pi is None else pi

    def f(s):
        p1 = pi * s + (1 - pi) * (1 - s)
        pe = p1 * p1 + (1 - p1) ** 2
        return ((s - pe) / (1 - pe)) - kappa
    return brentq(f, 0.5, 0.99999)


def hr_obs(hr_true, s, pi=None):
    pi = PI if pi is None else pi
    p1 = pi * s + (1 - pi) * (1 - s)
    p0 = 1 - p1
    num = pi * s * hr_true + (1 - pi) * (1 - s)
    den = pi * (1 - s) * hr_true + (1 - pi) * s
    return (num / p1) / (den / p0)


def kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in labels)
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0, po


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    global PI
    PI = float(pd.read_csv(os.path.join(H3, "data", "processed", "H_analysis_long.csv"),
                           encoding="utf-8-sig", usecols=["masld"],
                           low_memory=False)["masld"].dropna().mean())
    print(f"MASLD 患病率 π（与 code/06 网格同口径，H 层修正后实测）= {PI:.6f}")
    book = pd.read_excel(FINAL, sheet_name=None, dtype=str)
    rows, pooled = [], []
    for sheet in ["ABDUS_PG", "ABDUS_H"]:
        e = book[sheet]
        for i in e.index:
            a1, a2, arb = e.at[i, "A1_us_fatty"], e.at[i, "A2_us_fatty"], e.at[i, "arbitration"]
            gold = a1 if (pd.notna(a1) and a1 == a2) else \
                (str(arb).strip() if pd.notna(arb) and str(arb).strip() else "")
            if gold == "":
                continue
            pooled.append((v1_fatty(e.at[i, "text"]), gold, sheet))
    pooled_df = pd.DataFrame(pooled, columns=["v1", "gold", "domain"])
    for dom in ["ABDUS_PG", "ABDUS_H"]:
        s = pooled_df[pooled_df.domain == dom]
        k, po = kappa(s.v1.astype(str).tolist(), s.gold.astype(str).tolist())
        rows.append(dict(domain=dom, n=len(s), prevalence_gold=round((s.gold == "1").mean(), 4),
                         agreement=round(po, 4), cohen_kappa=round(k, 4)))
    k, po = kappa(pooled_df.v1.astype(str).tolist(), pooled_df.gold.astype(str).tolist())
    rows.append(dict(domain="POOLED", n=len(pooled_df),
                     prevalence_gold=round((pooled_df.gold == "1").mean(), 4),
                     agreement=round(po, 4), cohen_kappa=round(k, 4)))
    kd = pd.DataFrame(rows)
    kd.to_csv(os.path.join(RES, "m5b_simex_kappa.csv"), index=False, encoding="utf-8-sig")
    print("== 实测κ（词典v1 us_fatty vs 金标准终值）==")
    print(kd.to_string(index=False))

    # κ定位网格 + SIMEX 反演
    s = solve_s(k)
    back = []
    for name, hr_o in OBS_HRS.items():
        hr_t = brentq(lambda h: hr_obs(h, s) - hr_o, 0.8, 3.0)
        back.append(dict(outcome=name, HR_observed=hr_o, kappa_measured=round(k, 4),
                         Se_eq_Sp=round(s, 4), HR_corrected=round(hr_t, 4),
                         attenuation_pct=round((1 - hr_o / hr_t) * 100, 1)))
    bd = pd.DataFrame(back)
    bd.to_csv(os.path.join(RES, "m5b_simex_backfill.csv"), index=False, encoding="utf-8-sig")
    print("\n== SIMEX 校正（对称错分，π=%.4f）==" % PI)
    print(bd.to_string(index=False))

    # Fig5b：网格曲线族 + 实测κ曲线高亮 + 校正点
    grid = pd.read_csv(os.path.join(RES, "simex_kappa_grid.csv"))
    fig, ax = plt.subplots(figsize=(7.5, 5.2))
    cmap = plt.get_cmap("viridis")
    for i, (kg, gg) in enumerate(grid.groupby("kappa")):
        gg = gg.sort_values("HR_true")
        hit = abs(kg - round(k * 20) / 20) < 0.026
        ax.plot(gg["HR_true"], gg["HR_obs"], color=cmap(i / 7), lw=1.4,
                alpha=0.45 if not hit else 1.0,
                label=f"κ={kg:.2f}" + (" (measured band)" if hit else ""))
    # 实测κ连续曲线
    hr_t_grid = np.linspace(1.0, 1.8, 60)
    s_c = solve_s(k)
    ax.plot(hr_t_grid, [hr_obs(h, s_c) for h in hr_t_grid], color="#d62728", lw=2.6,
            label=f"Measured κ={k:.2f} (dict v1 us_fatty vs gold, n=585)")
    colors = ["#1f77b4", "#9467bd", "#2ca02c"]
    for (name, hr_o), c in zip(OBS_HRS.items(), colors):
        hr_t = brentq(lambda h: hr_obs(h, s_c) - hr_o, 0.8, 3.0)
        ax.scatter([hr_t], [hr_o], s=70, color=c, zorder=5,
                   label=f"{name.replace('HR_obs_', '')}: {hr_o}→{hr_t:.3f}")
    ax.plot([1, 1.8], [1, 1.8], "k--", lw=1)
    ax.set_xlabel("True effect HR_true")
    ax.set_ylabel("Observed HR_obs")
    ax.set_title(f"Measured κ locates the cohort on the attenuation grid\n"
                 f"(κ={k:.2f}, Se=Sp={s_c:.2f}, π={PI:.2f}; SIMEX-corrected points marked)")
    ax.legend(loc="upper left", fontsize=7.5, frameon=False)
    fig.tight_layout()
    FIGD = os.path.join(ROOT, "figures")
    os.makedirs(FIGD, exist_ok=True)
    for ext in ("png", "pdf"):    # PNG+PDF 双格式，避免只更新 PNG 导致 PDF 陈旧
        fig.savefig(os.path.join(RES, f"fig5b_simex_measured.{ext}"), dpi=300, bbox_inches="tight")
        fig.savefig(os.path.join(FIGD, f"SupplementaryFigureS2_SIMEX_measured_kappa.{ext}"), dpi=300,
                    bbox_inches="tight")
    plt.close(fig)
    print(f"\n-> {RES}/m5b_simex_kappa.csv, m5b_simex_backfill.csv, fig5b_simex_measured.png, figures/SupplementaryFigureS2_SIMEX_measured_kappa.png")
    return 0


if __name__ == "__main__":
    sys.exit(main())
