# -*- coding: utf-8 -*-
"""32_phantom_ci.py —— 方法学审计③：幻影 Cox 全规格重估（含 95%CI 与事件数）
复用 07/10 的离散时间 Cox 设定，但保留 se(coef) → HR 95%CI（Wald）。
规格：A) 全协变量(13协变量)×4结局×{orig,yearFE}（10_explore 口径）
      B) harmonized 8协变量×{v1,v3}×{orig,yearFE}（07 口径）
输出：results/phantom_specs_table.csv（Table 1 数据源）
用法：python code/32_phantom_ci.py
"""
import os
import sys

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, CoxTimeVaryingFitter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
RES = os.path.join(ROOT, "results")

FULL_COVS = ["sii_q", "proteinuria", "tyg", "bmi", "waist", "fpg", "egfr",
             "central_obese", "high_tg", "hyperuricemia", "dm_screen", "htn_screen"]
HARM_COVS = ["sii_q", "proteinuria", "bmi", "htn_screen", "dm_screen"]


def fit(frame, outkey, covs, tag, year_fe=False):
    g = frame.sort_values(["id", "year"]).copy()
    g["_prev_y"] = g.groupby("id")[outkey].shift()
    g["_prev_t"] = g.groupby("id")["year"].shift()
    # 与 07/10 口径一致：暴露（masld）与全部协变量均取 prev 波（shift 滞后）
    for c in ["age", "sex_male", "masld"] + covs:
        g[c] = g.groupby("id")[c].shift()
    g = g.rename(columns={"age": "p_age", "sex_male": "p_male"})
    keep = g["_prev_y"].notna() & g[outkey].notna() & ((g["year"] - g["_prev_t"]) <= 2)
    g = g[keep & (g["_prev_y"] == 0)].copy()
    if len(g) < 200:
        return None
    g["event"] = g[outkey].astype(int)
    covs_all = ["p_age", "p_male", "masld"] + covs
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
    s = s[s["covariate"] == "masld"].iloc[0]
    coef = float(s["coef"])
    se = float(s["se(coef)"])
    return dict(spec=tag, outcome=outkey, n_risk=len(g), n_events=int(g["event"].sum()),
                HR=round(float(np.exp(coef)), 4),
                CI_lo=round(float(np.exp(coef - 1.959964 * se)), 4),
                CI_hi=round(float(np.exp(coef + 1.959964 * se)), 4),
                p=float(s["p"]))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    df = pd.read_csv(H3 + "/data/processed/H_analysis_long.csv", encoding="utf-8-sig",
                     dtype={"id": str, "ecg_text": str}, low_memory=False)
    df = df.sort_values(["id", "year"]).reset_index(drop=True)
    sys.path.insert(0, os.path.join(ROOT, "code"))
    from main import extract_ecg, norm  # noqa: E402

    m = df["ecg_text"].notna()
    v3 = pd.DataFrame(df.loc[m, "ecg_text"].map(lambda t: extract_ecg(norm(t))).tolist())
    for c in v3.columns:
        df.loc[m, "v3_" + c] = v3[c].values
    df["v3_abnormal"] = ((df["v3_ecg_normal"] == 0) & (df["v3_ecg_unreadable"] == 0)).astype(float)
    df.loc[~m, "v3_abnormal"] = np.nan
    df["v1_abnormal"] = df["ecg_abnormal"].astype(float)

    rows = []
    # A. 全协变量 × 4结局（v1）
    ecg = df[df["ecg_abnormal"].notna()].copy()
    for outk, tag in [("ecg_abnormal", "anyAbnormal"), ("ecg_stt", "STT"),
                      ("ecg_af", "AF"), ("ecg_anyBlock", "anyBlock")]:
        for yfe in (False, True):
            print(f"fit full-cov {tag} yearFE={yfe}", flush=True)
            r = fit(ecg, outk, FULL_COVS, f"fullcov_{tag}" + ("+yearFE" if yfe else ""), yfe)
            if r:
                rows.append(r)
    # B. harmonized × {v1,v3}
    ecgdf = df[df["v1_abnormal"].notna() | df["v3_abnormal"].notna()].copy()
    for key, ver in [("v1_abnormal", "v1"), ("v3_abnormal", "v3")]:
        for yfe in (False, True):
            print(f"fit harmonized {ver} yearFE={yfe}", flush=True)
            r = fit(ecgdf, key, HARM_COVS, f"harmonized_{ver}" + ("+yearFE" if yfe else ""), yfe)
            if r:
                rows.append(r)
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "phantom_specs_table.csv"), index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
