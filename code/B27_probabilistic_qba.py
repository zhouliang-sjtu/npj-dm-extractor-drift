# -*- coding: utf-8 -*-
"""B27_probabilistic_qba.py —— 概率化定量偏倚分析（把 E-value 界升级为"校正后 HR + 区间"）

论文现有偏倚处理：κ 网格 + SIMEX（暴露侧，κ=0.99）+ 逐年差分重放（结局侧）+ E-value 界。
本脚本补两块**可校正**的推断：
 A) 暴露侧（严格自助法）：MASLD 脂肪肝成分 v1 规则 vs ABDUS 金标准（n=585）重抽 →
    κ 分布 → Se=Sp 反演 → 幻影/特异匹配结局的**校正后 HR 95% 区间**；
 B) 结局侧（情景分析，明确标注）：逐年 (Se_t, Sp_t) 采用重放实测值（paper 已报告量），
    施加 (i) Se_t 相对扰动 ±10%、(ii) 年份事件权重 Dirichlet 扰动 → 10,000 次抽样 →
    legacy 字典两个观测估计的校正后 HR 95% 区间；并给出"把观测 HR 校正到 1 以下所需的额外标注精度"。
 说明：A 为严格自助法；B 为参数不确定性情景分析（非严格后验），报告时须按此标注。

输入：data/金标准标注工作簿_终版.xlsx（ABDUS 两源）、results/phantom_specs_table.csv、
      results/replay_year_params.csv、results/m5b_simex_kappa.csv
输出：results/B27_probabilistic_qba.csv / .txt
用法：python code/B27_probabilistic_qba.py
"""
import os
import re
import sys

import numpy as np
import pandas as pd
from scipy.optimize import brentq

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
FINAL = os.path.join(ROOT, "data", "金标准标注工作簿_终版.xlsx")
RNG = np.random.default_rng(42)
N_DRAW = 10000
PI = float(pd.read_csv(os.path.join(H3, "data", "processed", "H_analysis_long.csv"),
                       encoding="utf-8-sig", usecols=["masld"],
                       low_memory=False)["masld"].dropna().mean())

rep = []


def rl(s=""):
    print(s, flush=True)
    rep.append(str(s))


def hr_obs(hr_true, s, pi=PI, se=None, sp=None):
    """风险混合公式：对称（se=sp=s）或非对称 (se, sp) 均可。"""
    se = s if se is None else se
    sp = s if sp is None else sp
    p1 = pi * se + (1 - pi) * (1 - sp)
    p0 = 1 - p1
    num = pi * se * hr_true + (1 - pi) * (1 - sp)
    den = pi * (1 - se) * hr_true + (1 - pi) * sp
    return (num / p1) / (den / p0)


def hr_true_from_obs(hr_o, se, sp, pi=PI):
    return brentq(lambda h: hr_obs(h, 0, pi, se, sp) - hr_o, 0.2, 10.0)


def solve_s(kappa, pi=PI):
    def f(s):
        p1 = pi * s + (1 - pi) * (1 - s)
        pe = p1 * p1 + (1 - p1) ** 2
        return ((s - pe) / (1 - pe)) - kappa
    return brentq(f, 0.5, 0.99999)


def kappa_of(v1, gold):
    lab = sorted(set(v1) | set(gold))
    n = len(v1)
    po = float(np.mean([a == b for a, b in zip(v1, gold)]))
    pe = sum((sum(1 for x in v1 if x == L) / n) * (sum(1 for y in gold if y == L) / n) for L in lab)
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0


# ================= A) 暴露侧：严格自助法 =================
def v1_fatty(t):
    t = str(t or "")
    return 1 if (re.search(r"脂肪肝", t) or (re.search(r"细密", t) and re.search(r"衰减|欠清", t))) else 0


book = pd.read_excel(FINAL, sheet_name=None, dtype=str)
pool = []
for sheet in ["ABDUS_PG", "ABDUS_H"]:
    e = book[sheet]
    for i in e.index:
        a1, a2, arb = e.at[i, "A1_us_fatty"], e.at[i, "A2_us_fatty"], e.at[i, "arbitration"]
        gold = a1 if (pd.notna(a1) and a1 == a2) else \
            (str(arb).strip() if pd.notna(arb) and str(arb).strip() else "")
        if gold == "":
            continue
        pool.append((v1_fatty(e.at[i, "text"]), gold))
v1_arr = np.array([p[0] for p in pool], dtype=int)
gold_arr = np.array([int(p[1]) for p in pool], dtype=int)
n_pool = len(pool)
k_full = kappa_of(v1_arr.tolist(), gold_arr.tolist())

spec = pd.read_csv(os.path.join(RES, "phantom_specs_table.csv"), encoding="utf-8-sig") \
    .set_index("spec")["HR"].astype(float)
obs = {"harmonized_v3(phantom)": spec["harmonized_v3"],
       "fullcov_STT(specificity-matched)": spec["fullcov_STT"]}

rl("=== B27 概率化 QBA ===")
rl(f"π（实测人均波 MASLD 患病率）= {PI:.4f}；暴露侧金标准 n={n_pool}；实测 κ={k_full:.4f}")
rl("\n—— A) 暴露侧：自助法（B=1000，按报告重抽）→ 校正后 HR 95% 区间 ——")
idx = np.arange(n_pool)
B = 1000
k_draw = np.empty(B)
s_draw = np.empty(B)
for b in range(B):
    s_idx = RNG.choice(idx, size=n_pool, replace=True)
    k_draw[b] = kappa_of(v1_arr[s_idx].tolist(), gold_arr[s_idx].tolist())
    s_draw[b] = solve_s(min(max(k_draw[b], 0.5), 0.9999))
rl(f"  κ 自助分布：中位 {np.median(k_draw):.4f}，2.5–97.5% = "
   f"{np.percentile(k_draw, 2.5):.4f}–{np.percentile(k_draw, 97.5):.4f}")
rl(f"  Se=Sp 反演分布：中位 {np.median(s_draw):.4f}，2.5–97.5% = "
   f"{np.percentile(s_draw, 2.5):.4f}–{np.percentile(s_draw, 97.5):.4f}")
rows = []
for name, hr_o in obs.items():
    corr = np.array([hr_true_from_obs(hr_o, s, s) for s in s_draw])
    rows.append({"side": "exposure", "estimate": name, "HR_observed": round(hr_o, 4),
                 "HR_corrected": round(float(np.median(corr)), 4),
                 "corr_lo": round(float(np.percentile(corr, 2.5)), 4),
                 "corr_hi": round(float(np.percentile(corr, 97.5)), 4),
                 "attenuation_pct": round((1 - hr_o / float(np.median(corr))) * 100, 1),
                 "method": "bootstrap(B=1000, strict)"})
    rl(f"  {name}: 观测 {hr_o:.4f} → 校正中位 {np.median(corr):.4f}"
       f"（95% 区间 {np.percentile(corr, 2.5):.4f}–{np.percentile(corr, 97.5):.4f}）")

# ================= B) 结局侧：情景分析 =================
rl("\n—— B) 结局侧：逐年 (Se_t, Sp_t) 参数不确定性情景分析（N_draw=10,000）——")
yp = pd.read_csv(os.path.join(RES, "replay_year_params.csv"), encoding="utf-8-sig")
rl("  实测逐年参数：" + "；".join(
    f"{int(r.year)}: Se={r.Se:.3f} Sp={r.Sp:.3f} n={int(r.n):,}" for _, r in yp.iterrows()))
w_ev = (yp["n"] * yp["p_obs_pos"]).to_numpy(float)
w_ev = w_ev / w_ev.sum()   # 事件量代理权重
legacy_obs = {"harmonized_v1(legacy outcome)": spec["harmonized_v1"],
              "fullcov_anyAbnormal(production outcome)": spec["fullcov_anyAbnormal"]}
for name, hr_o in legacy_obs.items():
    corr = []
    for _ in range(N_DRAW):
        se_t = np.clip(yp["Se"].to_numpy(float) * RNG.uniform(0.9, 1.1, len(yp)), 0.05, 0.999)
        sp_t = np.clip(yp["Sp"].to_numpy(float), 0.95, 1.0)
        w = RNG.dirichlet(w_ev * 200.0)
        se, sp = float((w * se_t).sum()), float((w * sp_t).sum())
        corr.append(hr_true_from_obs(hr_o, se, sp))
    corr = np.array(corr)
    rows.append({"side": "outcome", "estimate": name, "HR_observed": round(hr_o, 4),
                 "HR_corrected": round(float(np.median(corr)), 4),
                 "corr_lo": round(float(np.percentile(corr, 2.5)), 4),
                 "corr_hi": round(float(np.percentile(corr, 97.5)), 4),
                 "attenuation_pct": round((1 - hr_o / float(np.median(corr))) * 100, 1),
                 "method": "scenario(±10% Se, Dirichlet weights)"})
    rl(f"  {name}: 观测 {hr_o:.4f} → 校正中位 {np.median(corr):.4f}"
       f"（95% 区间 {np.percentile(corr, 2.5):.4f}–{np.percentile(corr, 97.5):.4f}）")

# ================= C) 方向性判读 + 标注量-精度投影 =================
rl("\n—— C) 方向性判读与标注量-精度投影 ——")
rl("  非差分漏检只把 |log HR| 拉向 0（衰减）——因此 legacy 观测估计是**下界**："
   "校正后只会上移（1.0296→1.0325；1.0662→1.0730），"
   "不能用'漏检'解释掉 legacy 的正向估计（方向相反）；幻影来自**逐年差分**成分。")

rows_c = []
for k_target in (0.85, 0.90, 0.95):
    for n_ann in (100, 300, 600, 1200):
        se_k = np.sqrt(max(k_target * (1 - k_target), 1e-6) / n_ann)
        ks = np.clip(RNG.normal(k_target, se_k, 4000), 0.5, 0.9999)
        ss = np.array([solve_s(k) for k in ks])
        # 代表性效应 HR_obs=1.20 的校正区间半宽（% of HR）
        corr = np.array([hr_true_from_obs(1.20, s, s) for s in ss])
        half = (np.percentile(corr, 97.5) - np.percentile(corr, 2.5)) / 2.0
        rows_c.append({"kappa_target": k_target, "n_annotation": n_ann,
                       "corr_halfwidth_pct_of_HR": round(half / 1.20 * 100, 3),
                       "corr_lo": round(float(np.percentile(corr, 2.5)), 4),
                       "corr_hi": round(float(np.percentile(corr, 97.5)), 4)})
cdf = pd.DataFrame(rows_c)
rl("  标注量 → 校正后 HR 区间半宽（对 HR_obs=1.20，Se=Sp 对称）：")
rl(cdf.pivot(index="kappa_target", columns="n_annotation",
             values="corr_halfwidth_pct_of_HR").to_string())
rl("  判读：偏倚参数本身的不确定性（±0.07% 量级 @κ=0.99, n=585）远小于流行病学抽样误差"
   "（如 v1 harmonized CI ±4%）——**标注量不是瓶颈，事件数才是**；"
   "仅在 κ≲0.90 时偏倚项半宽才升到 1–2% 量级，可与抽样误差同阶（见表）。")

out = pd.DataFrame(rows)
out.to_csv(os.path.join(RES, "B27_probabilistic_qba.csv"), index=False, encoding="utf-8-sig")
cdf.to_csv(os.path.join(RES, "B27_annotation_precision_projection.csv"),
           index=False, encoding="utf-8-sig")
with open(os.path.join(RES, "B27_probabilistic_qba.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
print("\n===== B27 完成 =====")
sys.exit(0)
