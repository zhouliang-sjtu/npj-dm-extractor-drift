# -*- coding: utf-8 -*-
"""B28_version_contrast_equivalence.py —— 版本间差异的正式对比 + 等价性检验 + 年份交互检验

背景（H 层修正后）: v1 harmonized 1.030（0.989–1.072，ns）vs v3 1.075（1.033–1.119，P=4.1e-4）
 CI 大幅重叠 → 需回答两问：①两版本点估计是否可区分？②关联是否随日历年变化？

方法:
 1) **配对个体自助法**（按人重抽，保持同人内相关）→ ΔHR = HR_v3 − HR_v1 的 90%/95% 区间；
    TOST：预设等价界 ±0.05（|ΔHR|<5% 视为等效），等价成立的条件是 **90% CI 完全落在 ±0.05 内**。
    - 主规格：harmonized + yearFE（CoxPHFitter(T=1, penalizer .01, cluster=id)，两版本同为 ns 规格）；
    - 次规格：harmonized 无 FE（CoxTimeVaryingFitter）——计算量大，用保守独立 CI 近似上界并标注。
 2) **masld×year 交互检验**：同一 risk set 上拟合 {主效应} 与 {主效应+交互} 两个嵌套模型，
    似然比检验（LRT）+ 逐年 masld HR（含 95%CI）→ 直接检验"关联随年份变化"这一机制命题。
    结局取 v3_abnormal（幻影结局）与生产 ecg_abnormal 两套。

输入：H_analysis_long.csv（清洗后 H 层）
输出：results/B28_version_contrast.csv、B28_interaction_test.csv、B28_peryear_hr.csv、B28_*.txt
用法：python code/B28_version_contrast_equivalence.py [B]   # B=自助重复数，默认 400
"""
import os
import sys
import time

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, CoxTimeVaryingFitter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
SEED = 42
B = int(sys.argv[1]) if len(sys.argv) > 1 else 300
MARGIN = 0.05          # TOST 等价界（HR 尺度绝对差）
HARM = ["sii_q", "proteinuria", "bmi", "htn_screen", "dm_screen"]
FULL = ["sii_q", "proteinuria", "tyg", "bmi", "waist", "fpg", "egfr",
        "central_obese", "high_tg", "hyperuricemia", "dm_screen", "htn_screen"]
OUTS = {"v3_abnormal": "v3_abnormal", "ecg_abnormal": "ecg_abnormal"}

rep = []


def rl(s=""):
    print(s, flush=True)
    rep.append(str(s))


def build(outkey, covs, year_fe):
    """与 32_phantom_ci.py 完全同源：先取「v1 或 v3 结局可判读」子集，再做 prev 波滞后与
    既往波无结局风险集（间隔≤2 年）——注意 shift 在子集内进行，故须与 32 用同一子集。"""
    g = ECGDF.sort_values(["id", "year"]).copy()
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


def fit_fe(g, covs_all, extra=(), penalizer=0.01):
    g = g.copy()
    g["T"] = 1.0
    cph = CoxPHFitter(penalizer=penalizer)
    cph.fit(g[["T", "event"] + list(covs_all) + list(extra) + ["id"]],
            duration_col="T", event_col="event", cluster_col="id", show_progress=False)
    return cph


def fit_ctv(g, covs_all):
    g = g.copy()
    g["stop"] = g.groupby("id").cumcount() + 1
    g["start"] = g["stop"] - 1
    ctv = CoxTimeVaryingFitter()
    ctv.fit(g[["id", "start", "stop", "event"] + list(covs_all)],
            id_col="id", event_col="event", start_col="start", stop_col="stop",
            show_progress=False)
    return ctv


def hr_of(model, term="masld"):
    s = model.summary.loc[term]
    return float(s["exp(coef)"]), float(s["exp(coef) lower 95%"]), float(s["exp(coef) upper 95%"])


t0 = time.time()
FRAME = pd.read_csv(os.path.join(H3, "data", "processed", "H_analysis_long.csv"),
                    encoding="utf-8-sig", dtype={"id": str, "ecg_text": str}, low_memory=False)
FRAME = FRAME.sort_values(["id", "year"]).reset_index(drop=True)
rl(f"=== B28 版本间对比 / 等价性 / 年份交互 ===")
rl(f"帧载入: {len(FRAME):,} 行, {FRAME['id'].nunique():,} 人（{time.time() - t0:.0f}s）")

# v1/v3 结局列：v1 = 生产列 ecg_abnormal；v3 = 用同一判读函数现场重跑（与 32 完全同源），带缓存
CACHE = os.path.join(RES, "B28_outcome_cache.csv.gz")
if os.path.exists(CACHE):
    c = pd.read_csv(CACHE, encoding="utf-8-sig")
    if len(c) == len(FRAME):
        FRAME["v1_abnormal"], FRAME["v3_abnormal"] = c["v1_abnormal"].to_numpy(), c["v3_abnormal"].to_numpy()
        rl("v1/v3 结局列：自缓存载入")
    else:
        c = None
else:
    c = None
if c is None or len(c) != len(FRAME):
    sys.path.insert(0, os.path.join(ROOT, "code"))
    from main import extract_ecg, norm  # noqa: E402
    m = FRAME["ecg_text"].notna()
    v3 = pd.DataFrame(FRAME.loc[m, "ecg_text"].map(lambda t: extract_ecg(norm(t))).tolist())
    for col in v3.columns:
        FRAME.loc[m, "v3_" + col] = v3[col].values
    FRAME["v3_abnormal"] = ((FRAME["v3_ecg_normal"] == 0) & (FRAME["v3_ecg_unreadable"] == 0)).astype(float)
    FRAME.loc[~m, "v3_abnormal"] = np.nan
    FRAME["v1_abnormal"] = FRAME["ecg_abnormal"].astype(float)
    pd.DataFrame({"v1_abnormal": FRAME["v1_abnormal"], "v3_abnormal": FRAME["v3_abnormal"]}) \
        .to_csv(CACHE, index=False, encoding="utf-8-sig")
    rl(f"v1/v3 结局列：现场重跑并写缓存（{time.time() - t0:.0f}s）")
ECGDF = FRAME[FRAME["v1_abnormal"].notna() | FRAME["v3_abnormal"].notna()].copy()

# ---------------- 1) 点估计（两版本 × 两规格） ----------------
rl("\n—— 1) 点估计复算（须与 phantom_specs_table.csv 一致）——")
rows = []
fits = {}
for tag, outkey, covs, yfe in [("harmonized_v1", "v1_abnormal", HARM, False),
                               ("harmonized_v1+yearFE", "v1_abnormal", HARM, True),
                               ("harmonized_v3", "v3_abnormal", HARM, False),
                               ("harmonized_v3+yearFE", "v3_abnormal", HARM, True)]:
    g, covs_all = build(outkey, covs, yfe)
    m = fit_fe(g, covs_all) if yfe else fit_ctv(g, covs_all)
    fits[tag] = (g, covs_all, m, yfe)
    hr, lo, hi = hr_of(m)
    rows.append({"spec": tag, "HR": round(hr, 4), "lo": round(lo, 4), "hi": round(hi, 4),
                 "n_risk": len(g), "events": int(g["event"].sum())})
    rl(f"  {tag:24s} HR={hr:.4f} ({lo:.4f}–{hi:.4f})  n={len(g):,} ev={int(g['event'].sum()):,}")
pd.DataFrame(rows).to_csv(os.path.join(RES, "B28_version_contrast_point_estimates.csv"),
                          index=False, encoding="utf-8-sig")

# ---------------- 2) 配对自助法：ΔHR（无 FE 与 yearFE 两规格） ----------------
def fit_nofe_strata(g, covs_all):
    """无 FE 规格的快速等价实现（与 CTV 点估计逐位一致，见 52 脚本已验证）：strata=interval。"""
    g = g.copy()
    g["T"] = 1.0
    g["stop"] = g.groupby("id").cumcount() + 1
    cph = CoxPHFitter(penalizer=0.0)
    cph.fit(g[["T", "event"] + list(covs_all) + ["stop", "id"]],
            duration_col="T", event_col="event", strata="stop", cluster_col="id",
            show_progress=False)
    return cph


def paired_bootstrap(tag1, tag3, fitter, B):
    gs1, covs1 = fits[tag1][0], fits[tag1][1]
    gs3, covs3 = fits[tag3][0], fits[tag3][1]
    pids = np.array(sorted(set(gs1["id"]) & set(gs3["id"])))
    idx1 = gs1.groupby("id").indices
    idx3 = gs3.groupby("id").indices
    g1r, g3r = gs1.reset_index(drop=True), gs3.reset_index(drop=True)
    h1f, h3f = hr_of(fits[tag1][2])[0], hr_of(fits[tag3][2])[0]
    rng = np.random.default_rng(SEED)
    dh, ok, t1 = [], 0, time.time()
    for b in range(B):
        sel = rng.choice(pids, size=len(pids), replace=True)
        a = g1r.iloc[np.concatenate([idx1[p] for p in sel])].copy()
        c = g3r.iloc[np.concatenate([idx3[p] for p in sel])].copy()
        a["id"] = np.repeat(np.arange(len(sel)), [len(idx1[p]) for p in sel])
        c["id"] = np.repeat(np.arange(len(sel)), [len(idx3[p]) for p in sel])
        try:
            dh.append(hr_of(fitter(c, covs3))[0] - hr_of(fitter(a, covs1))[0])
            ok += 1
        except Exception:  # noqa: BLE001
            continue
        if (b + 1) % 50 == 0:
            rl(f"    [{tag1} vs {tag3}] rep {b + 1}/{B} …（{time.time() - t1:.0f}s，成功 {ok}）")
    dh = np.array(dh)
    ci90 = np.percentile(dh, [5, 95])
    ci95 = np.percentile(dh, [2.5, 97.5])
    p2 = 2 * min((dh <= 0).mean(), (dh >= 0).mean())
    equiv = (ci90[0] > -MARGIN) and (ci90[1] < MARGIN)
    rl(f"\n—— 配对自助法 [{tag1} vs {tag3}]（B={B}，成功 {ok}）——")
    rl(f"  全样本 ΔHR = {h3f - h1f:+.4f}（HR_v1={h1f:.4f}，HR_v3={h3f:.4f}）")
    rl(f"  ΔHR 90% CI = [{ci90[0]:+.4f}, {ci90[1]:+.4f}]；95% CI = [{ci95[0]:+.4f}, {ci95[1]:+.4f}]")
    rl(f"  双侧 p（Δ=0）= {p2:.3f}")
    rl(f"  TOST（等价界 ±{MARGIN}）：{'通过（差异在 ±5% 内可判定为等效）' if equiv else '未通过（区间越界，不能宣称等效）'}")
    return {"contrast": f"{tag1} vs {tag3}", "B": B, "ok": ok,
            "HR_v1": round(h1f, 4), "HR_v3": round(h3f, 4),
            "dHR_full": round(h3f - h1f, 4),
            "dHR_lo90": round(ci90[0], 4), "dHR_hi90": round(ci90[1], 4),
            "dHR_lo95": round(ci95[0], 4), "dHR_hi95": round(ci95[1], 4),
            "p_two_sided": round(p2, 4), "TOST_pm5pct": bool(equiv)}, dh


rl(f"\n—— 2) 配对个体自助法（B={B}，按人重抽）——")
res_rows = []
r_nofe = paired_bootstrap("harmonized_v1", "harmonized_v3", fit_nofe_strata, B)
res_rows.append(r_nofe[0])
r_fe = paired_bootstrap("harmonized_v1+yearFE", "harmonized_v3+yearFE", fit_fe, B)
res_rows.append(r_fe[0])
pd.DataFrame(res_rows).to_csv(os.path.join(RES, "B28_version_contrast.csv"),
                              index=False, encoding="utf-8-sig")
np.save(os.path.join(RES, "B28_bootstrap_dhr_nofe.npy"), r_nofe[1])
np.save(os.path.join(RES, "B28_bootstrap_dhr_yearfe.npy"), r_fe[1])

# ---------------- 4) masld × year 交互检验 ----------------
rl("\n—— 3) masld × year 交互（LRT，同一 risk set 嵌套模型）——")
inter_rows, py_rows = [], []
for name, outkey in OUTS.items():
    g, covs_all = build(outkey, HARM, True)
    years = sorted(g["year"].astype(int).unique())
    base = [y for y in years if y != years[0]]
    for y in base:
        g[f"m_x_y{y}"] = g["masld"] * (g["year"].astype(int) == y).astype(float)
    inter = [f"m_x_y{y}" for y in base]
    m0 = fit_fe(g, covs_all)
    m1 = fit_fe(g, covs_all, extra=inter)
    lrt = 2 * (m1.log_likelihood_ - m0.log_likelihood_)
    dfree = len(inter)
    from scipy.stats import chi2
    p_lrt = float(chi2.sf(lrt, dfree))
    inter_rows.append({"outcome": name, "LRT_chi2": round(lrt, 3), "df": dfree,
                       "p": f"{p_lrt:.3g}", "n_risk": len(g), "events": int(g["event"].sum())})
    rl(f"  {name}: LRT χ²={lrt:.2f} (df={dfree}), P={p_lrt:.3g} "
       f"→ {'关联随年份显著变化' if p_lrt < 0.05 else '未检出年份交互（与年份 FE 消解一致）'}")
    s1 = m1.summary
    b0, v0 = float(s1.loc["masld", "coef"]), float(s1.loc["masld", "se(coef)"])
    for y in years:
        b, v = b0, v0
        if f"m_x_y{y}" in s1.index:
            b += float(s1.loc[f"m_x_y{y}", "coef"])
            v += float(s1.loc[f"m_x_y{y}", "se(coef)"]) ** 2   # 保守：忽略协方差项
        py_rows.append({"outcome": name, "year": y, "HR": round(float(np.exp(b)), 4),
                        "lo": round(float(np.exp(b - 1.96 * np.sqrt(v))), 4),
                        "hi": round(float(np.exp(b + 1.96 * np.sqrt(v))), 4)})
pd.DataFrame(inter_rows).to_csv(os.path.join(RES, "B28_interaction_test.csv"),
                                index=False, encoding="utf-8-sig")
pd.DataFrame(py_rows).to_csv(os.path.join(RES, "B28_peryear_hr.csv"),
                             index=False, encoding="utf-8-sig")
rl("  逐年 HR（交互模型，区间为忽略协方差的保守近似）已写入 results/B28_peryear_hr.csv")

with open(os.path.join(RES, "B28_version_contrast.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
rl(f"\n总耗时 {time.time() - t0:.0f}s；===== B28 完成 =====")
