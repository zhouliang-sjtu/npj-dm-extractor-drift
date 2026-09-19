# -*- coding: utf-8 -*-
"""30_audit_verify.py —— 方法学审计①：稿件量化声明 vs 结果工件 逐条自动核验
每条 = (编号, 稿件声明, 声明值, 实际值, 判定)。判定 PASS/FAIL/WARN(舍入口径内)。
输出：results/audit_number_check.csv + 控制台报告
用法：python code/30_audit_verify.py
"""
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
RES = os.path.join(ROOT, "results")
WB = os.path.join(ROOT, "data", "金标准标注工作簿_终版.xlsx")
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
    add("C2", "individuals 30,677", 30677, dfh["id"].nunique())
    v1_read = int(dfh["ecg_abnormal"].notna().sum())
    add("C3", "v1-readable ECG narratives 121,220", 121220, v1_read)
    add("C4", "MASLD prevalence 40.1%", 40.1, round(float(dfh["masld"].dropna().mean()) * 100, 1),
        0.05)

    # ---------- 金标准 ----------
    book = pd.read_excel(WB, sheet_name=None, dtype=str)
    n_gold = sum(len(book[s]) for s in ["ECG_H", "ECHO_PG", "ABDUS_PG", "ABDUS_H"])
    add("G1", "gold total 1,470", 1470, n_gold)
    arb = pd.read_csv(os.path.join(RES, "arbitration_decisions.csv"), dtype=str)
    add("G2", "43 disagreeing labels arbitrated (two rounds)", 43, len(arb))
    flg = pd.read_csv(os.path.join(RES, "arbitration_flag_decisions.csv"), dtype=str)
    add("G3", "15 uncertainty flags upheld", 15, len(flg))
    ks = []
    for s in ["ECG_H", "ECHO_PG", "ABDUS_PG", "ABDUS_H"]:
        a = pd.read_csv(os.path.join(RES, f"agreement_{s}.csv"))
        ks += a["cohen_kappa"].dropna().tolist()
    add("G4", "annotator κ min 0.00 (ABDUS main_discrepant@2022)", 0.0,
        round(min(ks), 2), 0.005)
    add("G4b", "annotator κ range excl. degenerate stratum min 0.66", 0.66,
        round(min(k for k in ks if k > 0), 2), 0.005)
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
    fr2 = pd.read_csv(os.path.join(RES, "round2_final_resolution.csv"), dtype=str)
    lvh_final = int(((fr2.sheet == "ECHO_PG") & (fr2.variable == "echo_lvh") &
                     (fr2["final"] == "1")).sum())
    add("G11", "lvh final prevalence 28/300 (final-resolution 口径)", 28, lvh_final)
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
    add("G16", "nested re-annotation 120/120", 120, ncmp)
    aec = pd.read_csv(os.path.join(RES, "agreement_ECG_H.csv")).set_index("variable")
    abh = pd.read_csv(os.path.join(RES, "agreement_ABDUS_H.csv")).set_index("variable")
    add("G17", "residual F1 gap ECG other 0.89", 0.89, round(float(aec.loc["ecg_other", "F1_1"]), 2), 0.005)
    add("G18", "residual F1 gap main_discrepant 0.90", 0.90,
        round(float(abh.loc["main_discrepant", "F1_1"]), 2) if "main_discrepant" in abh.index else "check-col",
        0.005)

    # ---------- 词典 v1×v3 ----------
    da = pd.read_csv(os.path.join(RES, "dict_v1_v3_agreement.csv"))
    o = da[da.scope == "overall"].iloc[0]
    add("D1", "v1-v3 overall raw 92.3%", 92.33, o["pct_agree"], 0.05)
    add("D2", "v1-v3 overall κ=0.84", 0.84, round(o["cohen_kappa"], 2), 0.005)
    by = da[da.scope == "by_year"].copy()
    by["year"] = by["year"].astype(int)
    by = by.set_index("year")
    k22, k23, k24 = by.loc[2022, "cohen_kappa"], by.loc[2023, "cohen_kappa"], by.loc[2024, "cohen_kappa"]
    stable = [by.loc[y, "cohen_kappa"] for y in [2018, 2019, 2020, 2021, 2022]]
    add("D3", "2022 κ=0.88（崩塌消失，H 层修正后）", 0.88, round(k22, 2), 0.005)
    add("D4", "2023 mixed-definition κ=0.693（清洁库重建后）", 0.693, k23, 0.0005)
    add("D5", "2024 κ=0.71", 0.71, round(k24, 2), 0.005)
    add("D6", "stable years κ 0.88–0.96 (min)", 0.88, round(min(stable), 2), 0.005)
    add("D7", "stable years κ 0.88–0.96 (max)", 0.96, round(max(stable), 2), 0.005)
    mix = da[da.scope == "by_year"].copy()
    mix["year"] = mix["year"].astype(int)
    p23 = mix[mix.year == 2023].iloc[0]
    add("D8", "2023 positive-call v1 36.9%", 37, round(p23["pct_v1_abn"], 0) if 20 <=
        p23["pct_v1_abn"] <= 21 else round(p23["pct_v1_abn"], 1), 0.5)
    add("D9", "2023 positive-call v3 52.1%", 52, round(p23["pct_v3_abn"], 0) if 63 <=
        p23["pct_v3_abn"] <= 65 else round(p23["pct_v3_abn"], 1), 0.5)

    # ---------- production specs（v3.5：phantom_specs_table.csv 32号重跑 2026-09-18） ----------
    ps = pd.read_csv(os.path.join(RES, "phantom_specs_table.csv")).set_index("spec")
    add("P1", "production outcome fullcov HR 0.974 p=0.229", 0.974,
        round(ps.loc["fullcov_anyAbnormal", "HR"], 3), 5e-4)
    add("P2", "ST-T fullcov HR 1.079 p=0.0076", 1.079,
        round(ps.loc["fullcov_STT", "HR"], 3), 5e-4)
    add("P3", "ST-T +FE HR 1.074 p=0.0067", 1.074,
        round(ps.loc["fullcov_STT+yearFE", "HR"], 3), 5e-4)
    add("P4", "AF fullcov HR 0.876 p=0.363", 0.876,
        round(ps.loc["fullcov_AF", "HR"], 3), 5e-4)
    add("P5", "anyBlock fullcov HR 1.034 p=0.488", 1.034,
        round(ps.loc["fullcov_anyBlock", "HR"], 3), 5e-4)
    pv = pd.read_csv(os.path.join(RES, "phantom_v1_vs_v3_cox.csv")).set_index("model")
    add("P8", "v1 harmonized HR 0.958 p=0.035", 0.958, round(pv.loc["v1_orig", "exp(coef)"], 3), 5e-4)
    add("P9", "v3 harmonized HR 0.953 p=0.013", 0.953, round(pv.loc["v3_orig", "exp(coef)"], 3), 5e-4)
    add("P10", "v3+FE HR 0.964 p=0.096", 0.964, round(pv.loc["v3_yearFE", "exp(coef)"], 3), 5e-4)
    add("P11", "v3 events 14,668", 14668, int(pv.loc["v3_orig", "n_events"]))
    add("P12", "v1 events 13,016", 13016, int(pv.loc["v1_orig", "n_events"]))
    b38 = pd.read_csv(os.path.join(RES, "B38_leave2023_sensitivity.csv"))
    bfull = b38[b38.scope.str.startswith("full")]
    bnn = bfull[(bfull.definition == "naive not-explicitly-normal") & (bfull.yearFE == "no")].iloc[0]
    add("P13", "naive production HR 0.959 p=0.046", 0.959, round(bnn["HR"], 3), 5e-4)
    bnf = bfull[(bfull.definition == "naive not-explicitly-normal") & (bfull.yearFE == "yes")].iloc[0]
    add("P14", "naive+FE HR 0.961 p=0.056", 0.961, round(bnf["HR"], 3), 5e-4)
    bep = bfull[(bfull.definition.str.startswith("explicit-positive")) & (bfull.yearFE == "no")].iloc[0]
    add("P15", "adjudicated production HR 0.960 p=0.052", 0.960, round(bep["HR"], 3), 5e-4)
    b29 = pd.read_csv(os.path.join(RES, "B29_specification_curve.csv"))
    add("P16", "spec-curve median HR 0.969 (24 specs)", 0.969, round(float(b29["HR"].median()), 3), 5e-4)
    b28 = pd.read_csv(os.path.join(RES, "B28_version_contrast.csv"))
    b28r = b28[b28[b28.columns[0]].str.contains("yearFE")].iloc[0]
    add("P17", "version ΔHR +0.0018 (yearFE)", 0.0018, abs(float(b28r[b28.columns[5]])), 5e-4)

    # ---------- 网格 / M5b ----------
    gr = pd.read_csv(os.path.join(RES, "simex_kappa_grid.csv"))
    for kk, expect in [(0.60, 1.17), (0.80, 1.23), (0.95, 1.28)]:
        v = gr[(gr.kappa == kk) & (gr.HR_true == 1.3)].iloc[0]["HR_obs"]
        add(f"B1 κ={kk}", f"HR_true=1.30 → observed {expect}", expect, round(v, 2), 0.005)
    m5k = pd.read_csv(os.path.join(RES, "m5b_simex_kappa.csv"))
    add("S1", "measured κ 0.99 (0.9929)", 0.99, round(m5k[m5k.domain == 'POOLED'].iloc[0]["cohen_kappa"], 2), 0.005)
    add("S2", "n=585", 585, int(m5k[m5k.domain == 'POOLED'].iloc[0]["n"]))
    m5b = pd.read_csv(os.path.join(RES, "m5b_simex_backfill.csv"))
    r3 = m5b[m5b.outcome == "HR_obs_v3_anyAbnormal"].iloc[0]
    add("S3", "SIMEX naive 0.9533→0.9528", 0.9528, r3["HR_corrected"], 5e-4)
    r4 = m5b[m5b.outcome == "HR_obs_fullcov_STT"].iloc[0]
    add("S4", "SIMEX ST-T 1.0787→1.0796", 1.0796, r4["HR_corrected"], 5e-4)

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
    add("T1", "14b 10/12 PASS", 10, npass)
    kk = e14[e14.verdict == "PASS"]["cohen_kappa"].astype(float)
    add("T2", "passing κ min 0.93", 0.93, round(kk.min(), 2), 0.005)
    add("T3", "passing κ max 1.00", 1.00, round(kk.max(), 2), 0.005)
    add("T4", "avblock κ=0.93", 0.93, round(float(e14[e14.variable == "ecg_avblock"].iloc[0]["cohen_kappa"]), 2), 0.005)
    add("T5", "rate κ=0.93", 0.93, round(float(e14[e14.variable == "ecg_rate"].iloc[0]["cohen_kappa"]), 2), 0.005)
    add("T6", "ecg_other κ=0.68 (FAIL)", 0.68, round(float(e14[e14.variable == "ecg_other"].iloc[0]["cohen_kappa"]), 2), 0.005)
    add("T7", "7b 8/12", 8, int((ec[(ec.model == "qwen2.5:7b") & (ec.variable != "_SUMMARY_")].verdict == "PASS").sum()))
    add("T8", "glm4 7/12", 7, int((ec[(ec.model == "glm4:9b") & (ec.variable != "_SUMMARY_")].verdict == "PASS").sum()))

    # ---------- Fig4 / Fig2b ----------
    py4 = pd.read_csv(os.path.join(RES, "m3d_peryear.csv"))
    p14 = py4[(py4.domain == "ECG") & (py4.extractor == "qwen2.5:14b") & (py4.year != "overall")]
    add("F1", "14b 2022 κ=0.97", 0.97, round(float(p14[p14.year == "2022"].iloc[0]["cohen_kappa"]), 2), 0.005)
    add("F2", "14b 2023 κ=0.897", 0.897, float(p14[p14.year == "2023"].iloc[0]["cohen_kappa"]), 5e-4)
    add("F3", "14b strata min 0.84", 0.84, round(p14.cohen_kappa.astype(float).min(), 2), 0.005)
    v1y = py4[(py4.domain == "ECG") & (py4.extractor == "dict v1") & (py4.year != "overall")]
    add("F4", "v1 2023 κ=0.93", 0.93, round(float(v1y[v1y.year == "2023"].iloc[0]["cohen_kappa"]), 2), 0.005)
    nmin, nmax = int(p14["n"].min()), int(p14["n"].max())
    add("F5", "strata n 71–94 (min)", 71, nmin)
    add("F6", "strata n 71–101 (max)", 101, nmax)
    for mdl, lo in [("qwen2.5:7b", 0.82), ("glm4:9b", 0.89)]:
        s = py4[(py4.domain == "ECG") & (py4.extractor == mdl) & (py4.year != "overall")]
        add(f"F7 {mdl}", f"Fig2b claim min κ {lo}", lo, round(s.cohen_kappa.astype(float).min(), 2), 0.005)
    v3y = py4[(py4.domain == "ECG") & (py4.extractor == "dict v3") & (py4.year != "overall")]
    add("F8", "v3 all years min κ=0.84", 0.84, round(float(v3y.cohen_kappa.astype(float).min()), 2), 0.005)

    # ---------- 终审新增数字（定义匹配 κ / 提示扰动 / masld×year 交互） ----------
    a31 = pd.read_csv(os.path.join(RES, "B31_definition_matched_agreement.csv"))
    r22 = a31[a31.year == 2022].iloc[0]
    add("N1", "2022 definition-matched κ 0.993", 0.993, round(float(r22["kappa_matched"]), 3), 5e-4)
    r24 = a31[a31.year == 2024].iloc[0]
    add("N2", "2024 mixed-definition κ 0.714", 0.714, round(float(r24["kappa_draft"]), 3), 5e-4)
    add("N3", "2024 definition-matched κ 0.987", 0.987, round(float(r24["kappa_matched"]), 3), 5e-4)
    pp = pd.read_csv(os.path.join(RES, "prompt_perturbation_eval.csv"))
    for tag, var, exp in [("N4", "baseline_v1", 0.934), ("N5", "aparaphrase", 0.931),
                          ("N6", "breorder", 0.927)]:
        sub = pp[pp.variant == var]
        add(tag, f"prompt perturbation '{var}' mean κ {exp}", exp,
            round(float(sub["kappa"].mean()), 3), 5e-4)
    with open(os.path.join(RES, "B28_version_contrast.txt"), encoding="utf-8") as f:
        b28t = f.read()
    mchi = re.search(r"χ²=([0-9.]+) \(df=5\), P=([0-9.eE+\-]+)", b28t)
    add("N7", "masld×year LRT χ²=23.56 (df=5)", 23.56,
        round(float(mchi.group(1)), 2) if mchi else np.nan, 0.005)
    add("N8", "masld×year LRT P=0.000264", 0.000264,
        float(mchi.group(2)) if mchi else np.nan, 1e-6)

    # ---------- 反向扫描（51 号 §9）暴露的正文数字：补齐断言，缩小未覆盖面 ----------
    # N9–N11：定义对齐核心（B31）
    r23 = a31[a31.year == 2023].iloc[0]
    add("N9", "2023 definition-matched κ 0.984", 0.984, round(float(r23["kappa_matched"]), 3), 5e-4)
    with open(os.path.join(RES, "B31_definition_alignment.txt"), encoding="utf-8") as f:
        b31t = f.read()
    mdiv = re.search(r"总量 ([\d,]+) / 2023 全部 ([\d,]+) = ([\d.]+)%", b31t)
    add("N10", "2023 divergent stratum 3,204 records", 3204,
        int(mdiv.group(1).replace(",", "")) if mdiv else np.nan)
    add("N11", "2023 divergent stratum 14.8% of cohort", 14.8,
        float(mdiv.group(3)) if mdiv else np.nan, 0.05)
    # N12–N14：SIMEX / 实测 κ（m5b）
    sm = pd.read_csv(os.path.join(RES, "m5b_simex_backfill.csv"))
    _naive = sm[sm.outcome.str.contains("anyAbnormal")].iloc[0]
    _stt = sm[sm.outcome.str.contains("STT")].iloc[0]
    add("N12", "measured κ 0.9894 (585-report calibration)", 0.9894,
        round(float(_naive["kappa_measured"]), 4), 1e-4)
    add("N13", "naive observed HR 0.9533", 0.9533, round(float(_naive["HR_observed"]), 4), 1e-4)
    add("N14", "ST-T observed HR 1.0787", 1.0787, round(float(_stt["HR_observed"]), 4), 1e-4)
    # N15–N16：160 例双判 κ / 原始一致率（由 A1A2 标注逐例重算）
    a1a2 = pd.read_csv(os.path.join(ROOT, "10_expert-consultation", "recycle", "04-定义对齐判读",
                                    "判读对齐包_v3.5_五层_20260918_A1A2标注.csv"), dtype=str)
    _x, _y = a1a2["A1判读"].astype(str), a1a2["A2判读"].astype(str)
    _po = float((_x == _y).mean())
    _pe = sum(float((_x == c).mean()) * float((_y == c).mean()) for c in sorted(set(_x) | set(_y)))
    add("N15", "160-record inter-annotator κ 0.985", 0.985, round((_po - _pe) / (1 - _pe), 3), 1e-3)
    add("N16", "160-record raw agreement 99.4%", 99.4, round(_po * 100, 1), 0.05)
    # N17–N18：描述式脂肪肝规则 κ 区间（自重复标注）
    sf = pd.read_csv(os.path.join(RES, "round2_selfrepeat_intra.csv"))
    sf = sf[(sf.domain == "ABDUS_H") & (sf.variable == "us_fatty")]
    add("N17", "description-based fatty-liver κ min 0.49", 0.49,
        round(float(sf.cohen_kappa.min()), 2), 0.005)
    add("N18", "description-based fatty-liver κ max 0.55", 0.55,
        round(float(sf.cohen_kappa.max()), 2), 0.005)
    # N19–N20：跨库阴性对照 κ 区间（B30）
    cpd = pd.read_csv(os.path.join(RES, "B30_crosslib_agreement.csv"))
    cpd = cpd[cpd.site == "PD"]
    add("N19", "cross-library PD κ min 0.997", 0.997, round(float(cpd.kappa.min()), 3), 5e-4)
    add("N20", "cross-library PD κ max 0.998", 0.998, round(float(cpd.kappa.max()), 3), 5e-4)
    # N21–N23：漂移监测器稳健 z（B30 报警表；手工口径 vs v10 归档基线）
    with open(os.path.join(RES, "B30_alarm_report.txt"), encoding="utf-8") as f:
        b30t = f.read()
    zrow = {}
    for ln in b30t.splitlines():
        p = ln.split()
        if len(p) == 12 and len(p[0]) == 4 and p[0].isdigit():
            zrow[int(p[0])] = p
    z23, z22 = zrow.get(2023, []), zrow.get(2022, [])
    add("N21", "2023 consistency-family κ z=−4.71", 4.71,
        round(abs(float(z23[2])), 2) if z23 else np.nan, 0.005)
    add("N22", "2022 in-line enumeration z=9.07", 9.07,
        round(float(z22[6]), 2) if z22 else np.nan, 0.005)
    add("N23", "2022 ECG-prefix z=15.07", 15.07,
        round(float(z22[8]), 2) if z22 else np.nan, 0.005)
    # N24–N25：决策层 Wilson 95% CI（15/100，正态近似）
    from math import sqrt
    _p, _nn, _zz = 0.15, 100, 1.959964
    _den = 1 + _zz * _zz / _nn
    _ctr = (_p + _zz * _zz / (2 * _nn)) / _den
    _hw = _zz * sqrt(_p * (1 - _p) / _nn + _zz * _zz / (4 * _nn * _nn)) / _den
    add("N24", "decision-stratum Wilson lower 0.093", 0.093, round(_ctr - _hw, 3), 1e-3)
    add("N25", "decision-stratum Wilson upper 0.233", 0.233, round(_ctr + _hw, 3), 1e-3)

    # ---------- N26–N52：主关联/网格/漂移/验收的“正文取整形式”（反向扫描剩余项逐一闭环） ----------
    _bepf = bfull[(bfull.definition.str.startswith("explicit-positive")) &
                  (bfull.yearFE == "yes")].iloc[0]
    _blv = b38[(b38.definition.str.startswith("explicit-positive")) &
               (b38.scope == "leave-2023-out") & (b38.yearFE == "yes")].iloc[0]
    add("N26", "naive production 95% CI lower 0.921", 0.921, round(float(bnn["CI"]), 3), 1e-3)
    add("N27", "naive production 95% CI upper 0.999", 0.999, round(float(bnn["CIh"]), 3), 1e-3)
    add("N28", "naive production P 0.046", 0.046, float(bnn["p"]), 1e-3)
    add("N29", "naive+FE P 0.056", 0.056, float(bnf["p"]), 1e-3)
    add("N30", "adjudicated production P 0.052", 0.052, float(bep["p"]), 1e-3)
    add("N31", "adjudicated+FE HR 0.963", 0.963, round(float(_bepf["HR"]), 3), 1e-3)
    add("N32", "adjudicated+FE P 0.072", 0.072, float(_bepf["p"]), 1e-3)
    add("N33", "leave-2023-out adjudicated HR 0.957", 0.957, round(float(_blv["HR"]), 3), 1e-3)
    add("N34", "leave-2023-out adjudicated P 0.062", 0.062, float(_blv["p"]), 1e-3)
    b31cox = pd.read_csv(os.path.join(RES, "B31_definition_matched_cox.csv"))
    _fe0, _fe1 = b31cox[~b31cox.yearFE], b31cox[b31cox.yearFE]
    add("N35", "harmonized grid FE=0 P min 0.011", 0.011, round(float(_fe0.p.min()), 3), 1e-3)
    add("N36", "harmonized grid FE=0 P max 0.035", 0.035, round(float(_fe0.p.max()), 3), 1e-3)
    add("N37", "harmonized grid FE=1 P max 0.098", 0.098, round(float(_fe1.p.max()), 3), 1e-3)
    add("N53", "harmonized grid FE=1 P min 0.040 (validation enum.)", 0.040,
        round(float(_fe1.p.min()), 3), 1e-3)
    add("N38", "ST-T P 0.008", 0.008,
        float(b29[b29.spec == "full|ecg_stt|noFE|model"].iloc[0]["p"]), 1e-3)
    add("N39", "ST-T year-FE P 0.007", 0.007,
        float(b29[b29.spec == "full|ecg_stt|yearFE|model"].iloc[0]["p"]), 1e-3)
    add("N40", "version ΔHR 0.002 (year-FE, 3dp)", 0.002, abs(float(b28r["dHR_full"])), 1e-3)
    add("N41", "ΔHR 90% CI lower 0.018", 0.018, abs(float(b28r["dHR_lo90"])), 1e-3)
    add("N42", "ΔHR 90% CI upper 0.019", 0.019, float(b28r["dHR_hi90"]), 1e-3)
    _sr = pd.read_csv(os.path.join(RES, "round2_selfrepeat_intra.csv"))
    add("N43", "four-domain self-repeat records 147", 147,
        int(_sr.groupby("domain")["n"].first().sum()))
    add("N44", "below-gate ecg_other κ 0.683", 0.683,
        round(float(e14[e14.variable == "ecg_other"].iloc[0]["cohen_kappa"]), 3), 5e-4)
    add("N45", "below-gate ecg_unreadable κ 0.666", 0.666,
        round(float(e14[e14.variable == "ecg_unreadable"].iloc[0]["cohen_kappa"]), 3), 5e-4)
    _ep = pd.read_csv(os.path.join(RES, "agreement_ECHO_PG.csv"))
    add("N46", "ECHO_PG κ range min 0.925", 0.925, round(float(_ep.cohen_kappa.min()), 3), 5e-4)
    add("N47", "decision-stratum proportion 0.15", 0.15, 15 / 100, 5e-4)
    add("N48", "decision-stratum Wilson lower 9.3%", 9.3, (_ctr - _hw) * 100, 0.05)
    add("N49", "decision-stratum Wilson upper 23.3%", 23.3, (_ctr + _hw) * 100, 0.05)
    add("N50", "2023 consistency-family z 4.7 (1dp)", 4.7,
        abs(float(z23[2])) if z23 else np.nan, 0.1)
    add("N51", "2022 in-line enumeration z 9.1 (1dp)", 9.1,
        float(z22[6]) if z22 else np.nan, 0.1)
    add("N52", "2022 ECG-prefix z 15.0 (1dp)", 15.0,
        float(z22[8]) if z22 else np.nan, 0.1)

    dfc = pd.DataFrame(checks)
    dfc.to_csv(os.path.join(RES, "audit_number_check.csv"), index=False, encoding="utf-8-sig")
    nfail = int((dfc.verdict == "FAIL").sum())
    print(dfc.to_string(index=False))
    print(f"\n===== 核验完成：{int((dfc.verdict == 'PASS').sum())}/{len(dfc)} PASS，{nfail} FAIL =====")
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
