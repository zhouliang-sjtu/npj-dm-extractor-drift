# -*- coding: utf-8 -*-
"""53_unadjusted_sensitivity.py —— 未调整（crude）估计补充（R12 镜头轮 F-1：STROBE 条目 16a）
背景：主稿全部为调整后模型；STROBE 16a 要求同时给出 unadjusted estimates。本脚本对 4 个
production 结局在**同一风险集口径**下拟合仅含 MASLD 的离散时间 Cox（无任何协变量），
产出 crude HR，作为 released 工件补齐 STROBE 16a。
数据准备与 32_phantom_ci.py fit() 逐行同源（滞后、既往波无结局、gap≤2），唯一差别：
complete-case 仅约束 masld（无协变量 → 不因协变量缺失删行，n_risk 会大于调整模型）。
输出: results/unadjusted_sensitivity.csv
用法: python code/53_unadjusted_sensitivity.py
"""
import os
import sys

import numpy as np
import pandas as pd
from lifelines import CoxTimeVaryingFitter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
RES = os.path.join(ROOT, "results")


def fit_crude(frame, outkey):
    """与 32_phantom_ci.py fit() 数据准备同源；仅 masld 一个预测变量（crude）。"""
    g = frame.sort_values(["id", "year"]).copy()
    g["_prev_y"] = g.groupby("id")[outkey].shift()
    g["_prev_t"] = g.groupby("id")["year"].shift()
    g["masld"] = g.groupby("id")["masld"].shift()  # 暴露滞后一波
    keep = g["_prev_y"].notna() & g[outkey].notna() & ((g["year"] - g["_prev_t"]) <= 2)
    g = g[keep & (g["_prev_y"] == 0) & g["masld"].notna()].copy()
    g["event"] = g[outkey].astype(int)
    g["stop"] = g.groupby("id").cumcount() + 1
    g["start"] = g["stop"] - 1
    ctv = CoxTimeVaryingFitter()
    ctv.fit(g[["id", "start", "stop", "event", "masld"]], id_col="id", event_col="event",
            start_col="start", stop_col="stop", show_progress=False)
    s = ctv.summary.reset_index()
    s = s[s["covariate"] == "masld"].iloc[0]
    coef, se = float(s["coef"]), float(s["se(coef)"])
    return dict(n_risk=len(g), n_events=int(g["event"].sum()),
                HR_crude=round(float(np.exp(coef)), 4),
                CI_lo=round(float(np.exp(coef - 1.959964 * se)), 4),
                CI_hi=round(float(np.exp(coef + 1.959964 * se)), 4),
                p=float(s["p"]))


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
        print(f"fit crude {tag}", flush=True)
        r = fit_crude(ecg, outk)
        rows.append(dict(spec=f"crude_{tag}", outcome=outk, **r))
        print(f"  crude HR={r['HR_crude']} ({r['CI_lo']}–{r['CI_hi']}) p={r['p']:.4g} "
              f"n={r['n_risk']} ev={r['n_events']}", flush=True)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "unadjusted_sensitivity.csv"), index=False,
               encoding="utf-8-sig")
    print("-> results/unadjusted_sensitivity.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
