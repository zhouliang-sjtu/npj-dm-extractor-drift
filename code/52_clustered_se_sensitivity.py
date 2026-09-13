# -*- coding: utf-8 -*-
"""52_clustered_se_sensitivity.py —— 非 FE 规格的聚类稳健 SE 敏感性（rebuttal 预备，R7 镜头轮 D-4）
背景：主稿非 FE 规格用 CoxTimeVaryingFitter 模型基线 SE（Table 1 脚注已披露）；person-period
多行/人存在个体内相关，审稿人可能问聚类稳健 SE 下结论是否不变。

lifelines 的 CoxTimeVaryingFitter.fit(robust=True) 未实现（NotImplementedError），故用等价公式：
离散时间 Cox 的 (start, stop] 分区基线 = CoxPHFitter 以 strata=stop 分层（层内单事件时点、
风险集=该区间全部行、Efron 并列处理一致 → 偏似然相同、点估计应逐位一致），而 CoxPHFitter
原生支持 cluster_col="id" 的聚类 sandwich。

三步：(a) CTV 模型基线（对照，须复现 Table 1 → phantom_specs_table.csv）；
      (b) PHFitter(strata=stop) 模型基线（点估计等价性校验）；
      (c) PHFitter(strata=stop, cluster_col="id") 聚类稳健 SE。
数据准备与 32_phantom_ci.py fit() 逐行同源（滞后、既往波无结局、gap≤2、complete-case）。
输出: results/clustered_se_sensitivity.csv
用法: python code/52_clustered_se_sensitivity.py
"""
import os
import sys

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, CoxTimeVaryingFitter

BASE = r"D:/projects/Paper/论文01-金标准标注-LLM抽取验证"
H3 = r"D:/projects/Paper/00-三线探索-多模态动态队列"
RES = os.path.join(BASE, "results")

FULL_COVS = ["sii_q", "proteinuria", "tyg", "bmi", "waist", "fpg", "egfr",
             "central_obese", "high_tg", "hyperuricemia", "dm_screen", "htn_screen"]


def prep(frame, outkey, covs):
    """与 32_phantom_ci.py fit() 的数据准备逐行同源。"""
    g = frame.sort_values(["id", "year"]).copy()
    g["_prev_y"] = g.groupby("id")[outkey].shift()
    g["_prev_t"] = g.groupby("id")["year"].shift()
    # 与 07/10 口径一致：暴露（masld）与全部协变量均取 prev 波（shift 滞后）
    for c in ["age", "sex_male", "masld"] + covs:
        g[c] = g.groupby("id")[c].shift()
    g = g.rename(columns={"age": "p_age", "sex_male": "p_male"})
    keep = g["_prev_y"].notna() & g[outkey].notna() & ((g["year"] - g["_prev_t"]) <= 2)
    g = g[keep & (g["_prev_y"] == 0)].copy()
    g["event"] = g[outkey].astype(int)
    covs_all = ["p_age", "p_male", "masld"] + covs
    g = g.dropna(subset=covs_all)
    g["stop"] = g.groupby("id").cumcount() + 1  # 区间序号 = 离散时间；strata=stop 即分区基线
    return g


def masld_row(summary):
    s = summary.reset_index()
    s = s[s["covariate"] == "masld"].iloc[0]
    coef, se = float(s["coef"]), float(s["se(coef)"])
    return dict(HR=round(float(np.exp(coef)), 4),
                CI_lo=round(float(np.exp(coef - 1.959964 * se)), 4),
                CI_hi=round(float(np.exp(coef + 1.959964 * se)), 4),
                p=float(s["p"]))


def fit_ctv(g, covs_all):
    g = g.copy()
    g["start"] = g["stop"] - 1
    ctv = CoxTimeVaryingFitter()
    ctv.fit(g[["id", "start", "stop", "event"] + covs_all], id_col="id", event_col="event",
            start_col="start", stop_col="stop", show_progress=False)
    return masld_row(ctv.summary)


def fit_phf(g, covs_all, clustered):
    g = g.copy()
    g["T"] = 1.0  # 层内单事件时点：duration=1、strata=stop ⇒ 每区间独立基线，等价 (start,stop] 分区模型
    ph = CoxPHFitter(penalizer=0.0)
    kwargs = dict(duration_col="T", event_col="event", strata=["stop"],
                  show_progress=False)
    if clustered:
        kwargs["cluster_col"] = "id"
        cols = ["id", "T", "event", "stop"] + covs_all
    else:
        cols = ["T", "event", "stop"] + covs_all
    ph.fit(g[cols], **kwargs)
    return masld_row(ph.summary)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    df = pd.read_csv(H3 + "/data/processed/H_analysis_long.csv", encoding="utf-8-sig",
                     dtype={"id": str}, low_memory=False)
    df = df.sort_values(["id", "year"]).reset_index(drop=True)
    ecg = df[df["ecg_abnormal"].notna()].copy()

    rows = []
    for outk, tag in [("ecg_abnormal", "anyAbnormal"), ("ecg_stt", "STT"),
                      ("ecg_af", "AF"), ("ecg_anyBlock", "anyBlock")]:
        g = prep(ecg, outk, FULL_COVS)
        covs_all = ["p_age", "p_male", "masld"] + FULL_COVS
        print(f"fit full-cov {tag}: CTV model-based (对照)", flush=True)
        ctv = fit_ctv(g, covs_all)
        print(f"fit full-cov {tag}: PHF(strata=stop) model-based（等价性校验）", flush=True)
        ph = fit_phf(g, covs_all, clustered=False)
        print(f"fit full-cov {tag}: PHF(strata=stop, cluster=id) 聚类稳健 SE", flush=True)
        rob = fit_phf(g, covs_all, clustered=True)
        rows.append(dict(spec=f"fullcov_{tag}", outcome=outk,
                         n_risk=len(g), n_events=int(g["event"].sum()),
                         HR_ctv=ctv["HR"], CI_lo_ctv=ctv["CI_lo"], CI_hi_ctv=ctv["CI_hi"],
                         p_ctv=ctv["p"],
                         HR_phf=ph["HR"], CI_lo_phf=ph["CI_lo"], CI_hi_phf=ph["CI_hi"],
                         p_phf=ph["p"],
                         HR_robust=rob["HR"], CI_lo_robust=rob["CI_lo"],
                         CI_hi_robust=rob["CI_hi"], p_robust=rob["p"]))
        r = rows[-1]
        print(f"  CTV   HR={r['HR_ctv']} ({r['CI_lo_ctv']}–{r['CI_hi_ctv']}) p={r['p_ctv']:.4f}", flush=True)
        print(f"  PHF   HR={r['HR_phf']} ({r['CI_lo_phf']}–{r['CI_hi_phf']}) p={r['p_phf']:.4f}"
              f"  [点估计等价性: |ΔHR|={abs(r['HR_phf']-r['HR_ctv']):.5f}]", flush=True)
        print(f"  ROBUST HR={r['HR_robust']} ({r['CI_lo_robust']}–{r['CI_hi_robust']}) "
              f"p={r['p_robust']:.4f}", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "clustered_se_sensitivity.csv"), index=False,
               encoding="utf-8-sig")
    print("-> results/clustered_se_sensitivity.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
