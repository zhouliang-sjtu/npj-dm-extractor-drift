# -*- coding: utf-8 -*-
"""30_audit_verify.py —— 方法学审计①：稿件量化声明 vs 结果工件 逐条自动核验
每条 = (编号, 稿件声明, 声明值, 实际值, 判定)。判定 PASS/FAIL/WARN(舍入口径内)。
输出：results/audit_number_check.csv + 控制台报告
用法：python code/30_audit_verify.py
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
RES = os.path.join(ROOT, "results")
WB = os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx")
checks = []


def add(cid, claim, claimed, actual, tol="exact"):
    if isinstance(claimed, float) or isinstance(actual, float):
        try:
            ok = abs(float(claimed) - float(actual)) <= (tol if isinstance(tol, float) else 5e-4)
        except Exception:
            ok = str(claimed) == str(actual)
    else:
        ok = str(claimed) == str(actual)
    checks.append(dict(id=cid, claim=claim, claimed=claimed, actual=actual,
                       verdict="PASS" if ok else "FAIL"))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    # ---------- 队列 ----------
    dfh = pd.read_csv(H3 + "/data/processed/H_analysis_long.csv", encoding="utf-8-sig",
                      dtype={"id": str, "ecg_text": str}, low_memory=False)
    add("C1", "visit-records 122,575", 122575, len(dfh))
    add("C2", "individuals 30,673", 30673, dfh["id"].nunique())
    v1_read = int(dfh["ecg_abnormal"].notna().sum())
    add("C3", "v1-readable ECG narratives 122,059", 122059, v1_read)
    add("C4", "MASLD prevalence 34.6%", 34.6, round(float(dfh["masld"].dropna().mean()) * 100, 1),
        0.05)

    # ---------- 金标准 ----------
    book = pd.read_excel(WB, sheet_name=None, dtype=str)
    n_gold = sum(len(book[s]) for s in ["ECG_H", "ECHO_PG", "ABDUS_PG", "ABDUS_H"])
    add("G1", "gold total 1,470", 1470, n_gold)
    arb = pd.read_csv(os.path.join(RES, "arbitration_decisions.csv"), dtype=str)
    add("G2", "34 disagreeing labels arbitrated", 34, len(arb))
    flg = pd.read_csv(os.path.join(RES, "arbitration_flag_decisions.csv"), dtype=str)
    add("G3", "33 uncertainty flags upheld", 33, len(flg))
    ks = []
    for s in ["ECG_H", "ECHO_PG", "ABDUS_PG", "ABDUS_H"]:
        a = pd.read_csv(os.path.join(RES, f"agreement_{s}.csv"))
        ks += a["cohen_kappa"].dropna().tolist()
    add("G4", "annotator κ range min 0.81", 0.81, round(min(ks), 2), 0.005)
    add("G5", "annotator κ range max 1.00", 1.00, round(max(ks), 2), 0.005)
    # re-annotation
    a1 = pd.read_csv(os.path.join(RES, "agreement_ECHO_PG.csv"))
    rl = pd.read_csv(os.path.join(RES, "round2_relabel_agreement.csv")).set_index("variable")
    add("G6", "lvh re-annot κ 0.83→0.98 (v2.0)", 0.98, rl.loc["echo_lvh", "cohen_kappa"], 0.005)
    add("G7", "lvh round1 κ was 0.83", 0.83, rl.loc["echo_lvh", "kappa_round1"], 0.005)
    add("G8", "la_dilate re-annot κ 0.81→1.00", 1.00, rl.loc["echo_la_dilate", "cohen_kappa"], 0.005)
    add("G9", "la_dilate round1 κ was 0.81", 0.81, rl.loc["echo_la_dilate", "kappa_round1"], 0.005)
    add("G10", "lvh v2.0 F1 0.98", 0.98, rl.loc["echo_lvh", "F1_pos"], 0.005)
    e = book["ECHO_PG"]
    con = e[e.A1_echo_lvh == e.A2_echo_lvh]
    prev_lvh2 = int((con.A1_echo_lvh == "1").sum())
    add("G11", "lvh final prevalence 28/300", 28, prev_lvh2)
    conla = e[e.A1_echo_la_dilate == e.A2_echo_la_dilate]
    add("G12", "la_dilate final prevalence 33/300", 33,
        int((conla.A1_echo_la_dilate == "1").sum()))
    ni = pd.read_csv(os.path.join(RES, "round2_echo_nested_intra.csv"))
    ncmp = int(ni["n"].sum())
    nchg = int(pd.to_numeric(ni["changed"], errors="coerce").fillna(0).sum())
    sr = pd.read_csv(os.path.join(RES, "round2_selfrepeat_intra.csv"))
    add("G13", "self-repeat 60/66 pairs raw≥0.90", 60,
        int((sr["raw_agreement"] >= 0.90).sum()))
    add("G14", "self-repeat κ<0.85 in 19/66", 19,
        int((sr["cohen_kappa"].dropna() < 0.85).sum()))
    ch = pd.read_csv(os.path.join(RES, "round2_changed_cases.csv"), dtype=str)
    add("G15a", "changed labels total 84", 84, len(ch))
    add("G15b", "46/84 changed labels rule-revised", 46,
        int(ch["v2_affected"].astype(str).str.lower().isin(["1", "true"]).sum()))
    add("G16", "nested re-annotation 120/120", 120, f"{ncmp} cmp, {nchg} changed")
    aec = pd.read_csv(os.path.join(RES, "agreement_ECG_H.csv")).set_index("variable")
    abh = pd.read_csv(os.path.join(RES, "agreement_ABDUS_H.csv")).set_index("variable")
    add("G17", "residual F1 gap ECG other 0.86", 0.86, round(float(aec.loc["ecg_other", "F1_1"]), 2), 0.005)
    add("G18", "residual F1 gap main_discrepant 0.82", 0.82,
        round(float(abh.loc["main_discrepant", "F1_1"]), 2) if "main_discrepant" in abh.index else "check-col",
        0.005)

    # ---------- 词典 v1×v3 ----------
    da = pd.read_csv(os.path.join(RES, "dict_v1_v3_agreement.csv"))
    o = da[da.scope == "overall"].iloc[0]
    add("D1", "v1-v3 overall raw 82.2%", 82.2, o["pct_agree"], 0.05)
    add("D2", "v1-v3 overall κ=0.65", 0.65, round(o["cohen_kappa"], 2), 0.005)
    by = da[da.scope == "by_year"].copy()
    by["year"] = by["year"].astype(int)
    by = by.set_index("year")
    k22, k23, k24 = by.loc[2022, "cohen_kappa"], by.loc[2023, "cohen_kappa"], by.loc[2024, "cohen_kappa"]
    stable = [by.loc[y, "cohen_kappa"] for y in [2018, 2019, 2020, 2021]]
    add("D3", "collapse 2022 κ=0.26", 0.26, round(k22, 2), 0.005)
    add("D4", "collapse 2023 κ=0.256", 0.256, k23, 0.0005)
    add("D5", "partial recovery 2024 κ=0.72", 0.72, round(k24, 2), 0.005)
    add("D6", "stable years κ 0.88–0.97 (min)", 0.88, round(min(stable), 2), 0.005)
    add("D7", "stable years κ 0.88–0.97 (max)", 0.97, round(max(stable), 2), 0.005)
    mix = da[da.scope == "by_year"].copy()
    mix["year"] = mix["year"].astype(int)
    p22 = mix[mix.year == 2022].iloc[0]
    add("D8", "2022 positive-call v1 22%", 22, round(p22["pct_v1_abn"], 0) if 22 <=
        p22["pct_v1_abn"] <= 23 else round(p22["pct_v1_abn"], 1), 0.5)
    add("D9", "2022 positive-call v3 64%", 64, round(p22["pct_v3_abn"], 0) if 64 <=
        p22["pct_v3_abn"] <= 65 else round(p22["pct_v3_abn"], 1), 0.5)

    # ---------- phantom ----------
    pc = pd.read_csv(H3 + "/results/ecg_newonset_cox.csv")
    m = pc[pc.covariate == "masld"].set_index("outcome")
    add("P1", "v1 anyAbnormal HR 1.094 p=0.001", 1.094, round(m.loc["anyAbnormal", "exp(coef)"], 3), 5e-4)
    add("P2", "v1 anyAbnormal events 8026", 8026, int(m.loc["anyAbnormal", "n_events"]))
    add("P3", "STT HR 1.128 p=0.0006", 1.128, round(m.loc["STT", "exp(coef)"], 3), 5e-4)
    add("P4", "AF HR 0.872 p=0.43", 0.872, round(m.loc["AF", "exp(coef)"], 3), 5e-4)
    add("P5", "anyBlock HR 0.979 p=0.72", 0.979, round(m.loc["anyBlock", "exp(coef)"], 3), 5e-4)
    py = pd.read_csv(H3 + "/results/ecg_newonset_cox_yearfe.csv")
    my = py[py.covariate == "masld"].set_index("outcome")
    add("P6", "v1+FE anyAbnormal HR 1.017 p=0.59", 1.017, round(my.loc["anyAbnormal_yearFE", "exp(coef)"], 3), 5e-4)
    add("P7", "STT+FE HR 1.127 p=0.0027", 1.127, round(my.loc["STT_yearFE", "exp(coef)"], 3), 5e-4)
    pv = pd.read_csv(os.path.join(RES, "phantom_v1_vs_v3_cox.csv")).set_index("model")
    add("P8", "v1 harmonized HR 0.980 p=0.34", 0.980, round(pv.loc["v1_orig", "exp(coef)"], 3), 5e-4)
    add("P9", "v3 harmonized HR 1.120 p=1.1e-9", 1.120, round(pv.loc["v3_orig", "exp(coef)"], 3), 5e-4)
    add("P10", "v3+FE HR 0.980 p=0.35", 0.980, round(pv.loc["v3_yearFE", "exp(coef)"], 3), 5e-4)
    add("P11", "v3 events 16,243", 16243, int(pv.loc["v3_orig", "n_events"]))
    add("P12", "v1 events 12,905", 12905, int(pv.loc["v1_orig", "n_events"]))

    # ---------- 网格 / M5b ----------
    gr = pd.read_csv(os.path.join(RES, "simex_kappa_grid.csv"))
    for kk, expect in [(0.60, 1.17), (0.80, 1.23), (0.95, 1.28)]:
        v = gr[(gr.kappa == kk) & (gr.HR_true == 1.3)].iloc[0]["HR_obs"]
        add(f"B1 κ={kk}", f"HR_true=1.30 → observed {expect}", expect, round(v, 2), 0.005)
    m5k = pd.read_csv(os.path.join(RES, "m5b_simex_kappa.csv"))
    add("S1", "measured κ 0.99 (0.9929)", 0.99, round(m5k[m5k.domain == 'POOLED'].iloc[0]["cohen_kappa"], 2), 0.005)
    add("S2", "n=585", 585, int(m5k[m5k.domain == 'POOLED'].iloc[0]["n"]))
    m5b = pd.read_csv(os.path.join(RES, "m5b_simex_backfill.csv"))
    r1 = m5b[m5b.outcome == "HR_obs_v1_anyAbnormal"].iloc[0]
    add("S3", "phantom corrected 1.094→1.095", 1.095, r1["HR_corrected"], 5e-4)
    r3 = m5b[m5b.outcome == "HR_obs_STT"].iloc[0]
    add("S4", "STT corrected 1.127→1.128", 1.128, r3["HR_corrected"], 5e-4)

    # ---------- M2d echo ----------
    acc = pd.read_csv(os.path.join(RES, "m2d_acceptance.csv"))
    a14 = acc[acc.model == "qwen2.5:14b"].set_index("variable")
    add("E1", "JSON compliance 300/300 (14b)", 300,
        int(round(float(pd.read_csv(os.path.join(RES, "m2c_qc.csv"))
                  [pd.read_csv(os.path.join(RES, "m2c_qc.csv")).model == "qwen2.5:14b"]
                  .iloc[0]["json_rate"]) * 300)))
    add("E2", "lvh κ=0.944", 0.944, a14.loc["echo_lvh", "cohen_kappa"], 5e-4)
    add("E3", "lvh F1 0.949", 0.949, a14.loc["echo_lvh", "F1_1"], 5e-4)
    add("E4", "echo_normal κ=0.973", 0.973, a14.loc["echo_normal", "cohen_kappa"], 5e-4)
    add("E5", "ef κ=1.000", 1.000, a14.loc["ef_abnormal", "cohen_kappa"], 5e-4)
    add("E6", "reflux κ=0.935", 0.935, a14.loc["reflux_grade", "cohen_kappa"], 5e-4)
    add("E7", "la_dilate κ=0.877 F1=0.892", 0.892, a14.loc["echo_la_dilate", "F1_1"], 5e-4)
    add("E8", "echo_variant κ=0.833", 0.833, a14.loc["echo_variant", "cohen_kappa"], 5e-4)
    add("E9", "14b 5/7 PASS", 5, int((acc[(acc.model == "qwen2.5:14b") &
        (acc.variable != "_SUMMARY_")].verdict == "PASS").sum()))
    add("E10", "7b 4/7 PASS", 4, int((acc[(acc.model == "qwen2.5:7b") &
        (acc.variable != "_SUMMARY_")].verdict == "PASS").sum()))
    add("E11", "glm4 3/7 PASS", 3, int((acc[(acc.model == "glm4:9b") &
        (acc.variable != "_SUMMARY_")].verdict == "PASS").sum()))
    lat = pd.read_csv(os.path.join(RES, "m3c_latency_summary.csv")).set_index("model")
    add("L1", "14b median 4.12s", 4.12, lat.loc["qwen2.5:14b", "median_latency_s"], 0.005)
    add("L2", "7b median 2.47s", 2.47, lat.loc["qwen2.5:7b", "median_latency_s"], 0.005)
    add("L3", "glm4 median 2.66s", 2.66, lat.loc["glm4:9b", "median_latency_s"], 0.005)
    add("L4", "GPU-h/1000 0.69–1.23 (max)", 1.23, lat["est_gpu_hours_per_1000"].max(), 0.005)

    # ---------- M2e ECG ----------
    ec = pd.read_csv(os.path.join(RES, "m2d_acceptance_ecg.csv"))
    e14 = ec[ec.model == "qwen2.5:14b"]
    e14 = e14[e14.variable != "_SUMMARY_"]
    npass = int((e14.verdict == "PASS").sum())
    add("T1", "14b 11/12 PASS", 11, npass)
    kk = e14[e14.verdict == "PASS"]["cohen_kappa"].astype(float)
    add("T2", "passing κ min 0.93", 0.93, round(kk.min(), 2), 0.005)
    add("T3", "passing κ max 1.00", 1.00, round(kk.max(), 2), 0.005)
    add("T4", "avblock κ=0.93", 0.93, round(float(e14[e14.variable == "ecg_avblock"].iloc[0]["cohen_kappa"]), 2), 0.005)
    add("T5", "rate κ=0.92", 0.92, round(float(e14[e14.variable == "ecg_rate"].iloc[0]["cohen_kappa"]), 2), 0.005)
    add("T6", "ecg_other κ=0.69 (FAIL)", 0.69, round(float(e14[e14.variable == "ecg_other"].iloc[0]["cohen_kappa"]), 2), 0.005)
    add("T7", "7b 7/12", 7, int((ec[(ec.model == "qwen2.5:7b") & (ec.variable != "_SUMMARY_")].verdict == "PASS").sum()))
    add("T8", "glm4 7/12", 7, int((ec[(ec.model == "glm4:9b") & (ec.variable != "_SUMMARY_")].verdict == "PASS").sum()))

    # ---------- Fig4 / Fig2b ----------
    py4 = pd.read_csv(os.path.join(RES, "m3d_peryear.csv"))
    p14 = py4[(py4.domain == "ECG") & (py4.extractor == "qwen2.5:14b") & (py4.year != "overall")]
    add("F1", "14b 2022 κ=0.966", 0.966, float(p14[p14.year == "2022"].iloc[0]["cohen_kappa"]), 5e-4)
    add("F2", "14b 2023 κ=1.000", 1.000, float(p14[p14.year == "2023"].iloc[0]["cohen_kappa"]), 5e-4)
    add("F3", "14b strata min 0.92", 0.92, round(p14.cohen_kappa.astype(float).min(), 2), 0.005)
    v1y = py4[(py4.domain == "ECG") & (py4.extractor == "dict v1") & (py4.year != "overall")]
    add("F4", "v1 2022 κ=0.41", 0.41, round(float(v1y[v1y.year == "2022"].iloc[0]["cohen_kappa"]), 2), 0.005)
    nmin, nmax = int(p14["n"].min()), int(p14["n"].max())
    add("F5", "strata n 71–85 (min)", 71, nmin)
    add("F6", "strata n 71–85 (max)", 85, nmax)
    for mdl, lo in [("qwen2.5:7b", 0.90), ("glm4:9b", 0.90)]:
        s = py4[(py4.domain == "ECG") & (py4.extractor == mdl) & (py4.year != "overall")]
        add(f"F7 {mdl}", "Fig2b claim min κ 0.90", lo, round(s.cohen_kappa.astype(float).min(), 2), 0.005)
    v3y = py4[(py4.domain == "ECG") & (py4.extractor == "dict v3") & (py4.year != "overall")]
    add("F8", "v3 all years κ=1.000", 1.000, float(v3y.cohen_kappa.astype(float).min()), 5e-4)

    dfc = pd.DataFrame(checks)
    dfc.to_csv(os.path.join(RES, "audit_number_check.csv"), index=False, encoding="utf-8-sig")
    nfail = int((dfc.verdict == "FAIL").sum())
    print(dfc.to_string(index=False))
    print(f"\n===== 核验完成：{int((dfc.verdict == 'PASS').sum())}/{len(dfc)} PASS，{nfail} FAIL =====")
    return 0


if __name__ == "__main__":
    sys.exit(main())
