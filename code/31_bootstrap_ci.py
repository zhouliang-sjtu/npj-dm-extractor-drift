# -*- coding: utf-8 -*-
"""31_bootstrap_ci.py —— 方法学审计②：κ 自助法95%CI + 两项敏感性分析
1) 抽取器κ CI：echo 7变量×3模型、ECG 12变量×3模型（B=1000, seed=42, percentile CI）
2) Fig4 分年份 any-abnormal κ CI（5抽取器×7年份层）
3) 敏感性① ecg_other：a)原口径 b)剔除27例高电压行 c)高电压按仲裁口径gold→0
4) 敏感性② 方案B：echo_normal/echo_variant 三种计分（label-only / field-only / hybrid=方案B）
输出：results/audit_ci_extractors.csv、audit_ci_peryear.csv、audit_sensitivity.csv
用法：python code/31_bootstrap_ci.py
"""
import importlib.util
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
WB = os.path.join(ROOT, "data", "金标准标注工作簿_终版.xlsx")
B = 1000
SEED = 42


def load_mod(fname, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "code", fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in labels)
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0


def boot_ci(a, b, B=B, seed=SEED):
    a = np.asarray(a)
    b = np.asarray(b)
    rng = np.random.default_rng(seed)
    n = len(a)
    ks = []
    for _ in range(B):
        idx = rng.integers(0, n, n)
        ks.append(kappa(a[idx].tolist(), b[idx].tolist()))
    return float(np.percentile(ks, 2.5)), float(np.percentile(ks, 97.5))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    m29 = load_mod("29_ecg_acceptance.py", "m29")
    m28 = load_mod("28_peryear_fig4.py", "m28")
    book = pd.read_excel(WB, sheet_name=None, dtype=str)
    rows = []

    # ---------- echo 7变量 × 3模型（与 23_m2d_acceptance 完全同口径：方案B推导 + round2 终值） ----------
    m23 = load_mod("23_m2d_acceptance.py", "m23")
    g23 = m23.gold_frame()
    ECHO_VARS = ["echo_lvh", "echo_la_dilate", "echo_normal", "echo_variant",
                 "ef_abnormal", "reflux_grade", "echo_unreadable"]
    acc = pd.read_csv(os.path.join(RES, "m2d_acceptance.csv"))
    for model, fn in m23.MODELS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        mf, _ = m23.model_fields(d)
        joined = g23.join(mf, how="inner", lsuffix="_x", rsuffix="_y")
        for var in ECHO_VARS:
            a_col, m_col = var + "_x", var + "_y"
            sub = joined[(joined[a_col].astype(str).str.strip() != "")
                         & (joined[m_col].astype(str).str.strip() != "")]
            if len(sub) < 20:
                continue
            a, b = sub[a_col].tolist(), sub[m_col].tolist()
            k = kappa(a, b)
            lo, hi = boot_ci(a, b)
            pt = acc[(acc.model == model) & (acc.variable == var)]
            rows.append(dict(domain="ECHO", variable=var, model=model, n=len(a),
                             kappa=round(k, 3), ci_lo=round(lo, 3), ci_hi=round(hi, 3),
                             gate_f1=pt.iloc[0]["verdict"] if len(pt) else ""))
    # ECG 12变量 × 3模型
    ecg_e, ecg_g = m29.gold_finals()
    ecacc = pd.read_csv(os.path.join(RES, "m2d_acceptance_ecg.csv"))
    for model, fn in m29.MODELS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        pr = {r.sample_id: m29.parse(r.llm_raw) for r in d.itertuples(index=False)}
        for var in m29.ECG_VARS:
            a, b = [], []
            for sid in d.sample_id:
                gv = ecg_g.get((sid, var), "")
                p = pr.get(sid)
                if str(gv) == "" or p is None:
                    continue
                a.append(str(gv))
                b.append(str(p.get(var)))
            k = kappa(a, b)
            lo, hi = boot_ci(a, b)
            pt = ecacc[(ecacc.model == model) & (ecacc.variable == var)]
            rows.append(dict(domain="ECG", variable=var, model=model, n=len(a),
                             kappa=round(k, 3), ci_lo=round(lo, 3), ci_hi=round(hi, 3),
                             gate_f1=pt.iloc[0]["verdict"] if len(pt) else ""))
    ci = pd.DataFrame(rows)
    ci.to_csv(os.path.join(RES, "audit_ci_extractors.csv"), index=False, encoding="utf-8-sig")
    print(ci.to_string(index=False))

    # ---------- Fig4 分年份 any-abnormal CI ----------
    pyrows = []
    g = m28.gold_ecg()
    g["dict v1"] = g.text.map(m28.v1_naive_ecg)
    g["dict v3"] = g.text.map(m28.v3_ecg_any_abnormal)
    for model, fn in m28.ECG_LLMS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        m = dict(zip(d.sample_id, d.llm_raw.map(m28.llm_ecg_any_abnormal)))
        g[model] = g.sample_id.map(m)
    for ext in ["dict v1", "dict v3", "qwen2.5:14b", "qwen2.5:7b", "glm4:9b"]:
        for scope, sub in [("overall", g)] + [(y, g[g.year == y]) for y in sorted(g.year.unique())]:
            pairs = [(x, y) for x, y in zip(sub.gold.astype(str), sub[ext].astype(str))
                     if x != "" and y != "" and x != "nan" and y != "nan"]
            if len(pairs) < 10:
                continue
            a = [x for x, _ in pairs]
            b = [y for _, y in pairs]
            lo, hi = boot_ci(a, b)
            pyrows.append(dict(extractor=ext, year=scope, n=len(pairs),
                               kappa=round(kappa(a, b), 3), ci_lo=round(lo, 3), ci_hi=round(hi, 3)))
    pyci = pd.DataFrame(pyrows)
    pyci.to_csv(os.path.join(RES, "audit_ci_peryear.csv"), index=False, encoding="utf-8-sig")
    print("\n" + pyci[pyci.extractor == "qwen2.5:14b"].to_string(index=False))

    # ---------- 敏感性① ecg_other 高电压 ----------
    e2 = book["ECG_H"].set_index("sample_id")
    d14 = pd.read_csv(os.path.join(ROOT, "data", "llm_ecg570_v1__qwen2.5_14b.csv"),
                      encoding="utf-8-sig", dtype=str)
    pr14 = {r.sample_id: m29.parse(r.llm_raw) for r in d14.itertuples(index=False)}
    sens = []
    pairs_all, hv_idx = [], []
    for i, sid in enumerate(d14.sample_id):
        gv = ecg_g.get((sid, "ecg_other"), "")
        p = pr14.get(sid)
        if str(gv) == "" or p is None:
            continue
        pairs_all.append((sid, str(gv), str(p.get("ecg_other"))))
    hv = set(e2.index[e2["text"].fillna("").str.contains("高电压")])
    for tag, keep, override in [
            ("as_annotated", None, False),
            ("exclude_HV_rows", [s for s, _, _ in pairs_all if s not in hv], False),
            ("HV_gold_to_0", None, True)]:
        pp = [(s, gg, mm) for s, gg, mm in pairs_all
              if keep is None or s in keep]
        if override:
            pp = [(s, ("0" if s in hv else gg), mm) for s, gg, mm in pp]
        k = kappa([x for _, x, _ in pp], [y for _, _, y in pp])
        lo, hi = boot_ci([x for _, x, _ in pp], [y for _, _, y in pp])
        sens.append(dict(analysis=f"ecg_other_{tag}", n=len(pp), kappa=round(k, 3),
                         ci_lo=round(lo, 3), ci_hi=round(hi, 3)))
    # ---------- 敏感性② 方案B三计分（精确复刻 23 的推导口径） ----------
    # 方案B(23)：abn_signal = lvh|la|ef<50|reflux∈{moderate,severe}|label=abnormal;
    #           normal = 0 if abn_signal or reflux==trace_mild else 1; variant = 1 if not abn and reflux==trace_mild
    ef = book["ECHO_PG"].set_index("sample_id")
    for model, fn in m28.ECHO_LLMS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        pr = {r.sample_id: m28.parse(r.llm_raw) for r in d.itertuples(index=False)}
        for scoring in ["label_only", "field_only", "hybrid_planB"]:
            an, av = [], []
            bn, bv = [], []
            for sid in d.sample_id:
                r = ef.loc[sid]
                g_n = r["A1_echo_normal"] if r["A1_echo_normal"] == r["A2_echo_normal"] else ""
                g_v = r["A1_echo_variant"] if r["A1_echo_variant"] == r["A2_echo_variant"] else ""
                p = pr.get(sid)
                if p is None or (str(g_n) == "" and str(g_v) == ""):
                    continue
                lab = str(p.get("label"))
                if lab == "unreadable":
                    continue  # 与 23 口径一致：模型判 unreadable 的行不计入 normal/variant 配对
                rg = str(p.get("reflux_grade"))
                abn_field = (str(p.get("lvh")) == "1" or str(p.get("la_dilate")) == "1"
                             or (p.get("ef") is not None and str(p.get("ef")) != "None"
                                 and float(p.get("ef")) < 50)
                             or rg in ("moderate", "severe"))
                if scoring == "label_only":
                    m_n, m_v = ("1" if lab == "normal" else "0"), ("1" if lab == "normal_variant" else "0")
                elif scoring == "field_only":
                    m_n = "0" if (abn_field or rg == "trace_mild") else "1"
                    m_v = "1" if (not abn_field and rg == "trace_mild") else "0"
                else:
                    abn = abn_field or lab == "abnormal"
                    m_n = "0" if (abn or rg == "trace_mild") else "1"
                    m_v = "1" if (not abn and rg == "trace_mild") else "0"
                if str(g_n) != "":
                    an.append(str(g_n))
                    bn.append(m_n)
                if str(g_v) != "":
                    av.append(str(g_v))
                    bv.append(m_v)
            sens.append(dict(analysis=f"echo_normal_{model}_{scoring}", n=len(an),
                             kappa=round(kappa(an, bn), 3), ci_lo="", ci_hi=""))
            sens.append(dict(analysis=f"echo_variant_{model}_{scoring}", n=len(av),
                             kappa=round(kappa(av, bv), 3), ci_lo="", ci_hi=""))
    sdf = pd.DataFrame(sens)
    sdf.to_csv(os.path.join(RES, "audit_sensitivity.csv"), index=False, encoding="utf-8-sig")
    print("\n" + sdf.to_string(index=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
