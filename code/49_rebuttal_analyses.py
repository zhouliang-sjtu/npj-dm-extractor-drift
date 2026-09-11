# -*- coding: utf-8 -*-
"""49_rebuttal_analyses.py —— 修回预案四件套中的三项预分析（2026-09-11）
（第四件 prompt 扰动实验见 50_prompt_perturbation.py，因需本地 LLM 长时间推理而独立成脚本）

Part A  E-value：对 phantom_specs_table 全部规格计算未测混杂/残余偏倚的 E-value
        （VanderWeele & Ding 2017 式 E = HR + sqrt(HR·(HR−1))，HR<1 取倒数），
        点估计与 95%CI 两端各一——幻影关联 (harmonized_v3) 需偏倚强度 ≥E 才能被完全解释。
Part B  Wilson 95% CI：对全部 gate 相关 F1（ECG 12 变量 × 3 模型、ECHO 7 变量 × 3 模型
        目标类，与 results/m2d_acceptance*.csv 同口径同数据）给出解析 Wilson score 区间
        （F1 = 2TP/(2TP+FP+FN) 的比例视角），并标注区间是否跨越预注册门槛 0.90。
        与 31_bootstrap_ci.py 的 κ bootstrap CI 互补（解析、逐条可复现、审稿人熟悉）。
Part C  重放代理敏感性：逐年实测错分参数 (Se_t, Sp_t) 仅在金样本精度（每年 n=71–94）下
        可复制，故按金样本有效规模做 Beta-二项后验重抽（均匀先验），R=20 次重放
        harmonized 离散时间 Cox，检验幻影重现不依赖参数点值。
        参数中心=全库实测（results/replay_year_params.csv），帧重建与拟合复用 35 的
        fit_cox/lag_frame 与 32 口径。

输出：results/evalue_table.csv
      results/wilson_ci_gates.csv
      results/proxy_sensitivity_replay.csv、results/proxy_sensitivity_summary.csv
用法：python code/49_rebuttal_analyses.py [--parts=A,B,C] [--R=20]
"""
import importlib.util
import json
import math
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
Z = 1.959963984540054
SEED = 42

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def load_mod(fname, name):
    spec = importlib.util.spec_from_file_location(name, os.path.join(ROOT, "code", fname))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------- Part A：E-value ----------------
def evalue(hr):
    if hr <= 1:
        return np.nan
    return hr + math.sqrt(hr * (hr - 1.0))


def part_a():
    t = pd.read_csv(os.path.join(RES, "phantom_specs_table.csv"))
    rows = []
    for r in t.itertuples(index=False):
        hr = float(r.HR)
        # E-value 须对不利方向定义：HR<1 时取倒数进公式（VanderWeele & Ding 2017 约定）
        e_pt = evalue(hr if hr > 1 else 1.0 / hr)
        crosses = bool(float(r.CI_lo) <= 1 <= float(r.CI_hi))
        if crosses:                      # CI 跨 1：CI 一致的偏倚强度下限无意义
            e_ci = np.nan
        elif float(r.CI_lo) > 1:         # HR>1 显著：不利端为 CI_lo
            e_ci = evalue(float(r.CI_lo))
        else:                            # HR<1 显著：不利端为 CI_hi 取倒数
            e_ci = evalue(1.0 / float(r.CI_hi))
        rows.append(dict(
            spec=r.spec, outcome=r.outcome, HR=hr, CI_lo=float(r.CI_lo), CI_hi=float(r.CI_hi),
            Evalue_point=round(e_pt, 3), Evalue_CI=round(e_ci, 3) if not np.isnan(e_ci) else "",
            Evalue_CI_crosses_1=crosses,
        ))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "evalue_table.csv"), index=False, encoding="utf-8-sig")
    key = out[out.spec == "harmonized_v3"].iloc[0]
    print("[A] E-value 表 -> results/evalue_table.csv")
    print(out.to_string(index=False))
    print(f"\n  关键行 harmonized_v3：HR={key.HR} → E={key.Evalue_point}；"
          f"CI 下限 {key.CI_lo} → E={key.Evalue_CI}")
    return out


# ---------------- Part B：Wilson CI ----------------
def wilson_ci(tp, fp, fn):
    """F1 的 Wilson score 区间：F1 = 2TP/(2TP+FP+FN)，比例 p̂=2TP/n_eff。"""
    k, n = 2.0 * tp, 2.0 * tp + fp + fn
    if n == 0:
        return np.nan, np.nan, np.nan
    p = k / n
    denom = 1.0 + Z * Z / n
    center = (p + Z * Z / (2.0 * n)) / denom
    half = Z * math.sqrt(p * (1.0 - p) / n + Z * Z / (4.0 * n * n)) / denom
    return p, max(0.0, center - half), min(1.0, center + half)


def part_b():
    m29 = load_mod("29_ecg_acceptance.py", "m29")
    m23 = load_mod("23_m2d_acceptance.py", "m23")
    rows = []

    # ---- ECG（29 口径：A1==A2 → A1，否则仲裁终值；字段正则解析）----
    e, g = m29.gold_finals()
    for model, fn in m29.MODELS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        parsed = {r.sample_id: m29.parse(r.llm_raw) for r in d.itertuples(index=False)}
        for var in m29.ECG_VARS:
            a, b = [], []
            for sid in d.sample_id:
                gv, p = g.get((sid, var), ""), parsed.get(sid)
                if gv == "" or p is None:
                    continue
                a.append(str(gv))
                b.append(str(p.get(var)))
            tp = sum(1 for x, y in zip(a, b) if x == "1" and y == "1")
            fp = sum(1 for x, y in zip(a, b) if x != "1" and y == "1")
            fn = sum(1 for x, y in zip(a, b) if x == "1" and y != "1")
            f1, lo, hi = wilson_ci(tp, fp, fn)
            rows.append(dict(domain="ECG", model=model, variable=var, target_class="1",
                             n=len(a), TP=tp, FP=fp, FN=fn,
                             F1=round(f1, 4), Wilson_lo=round(lo, 4), Wilson_hi=round(hi, 4),
                             gate=0.90, CI_contains_gate=bool(lo <= 0.90 <= hi),
                             CI_excludes_gate_below=bool(hi < 0.90),
                             CI_excludes_gate_above=bool(lo > 0.90)))

    # ---- ECHO（23 口径：方案B推导 + reflux 修复）----
    g23 = m23.gold_frame()
    for model, fn in m23.MODELS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        mf, _ = m23.model_fields(d)
        joined = g23.join(mf, how="inner", lsuffix="_x", rsuffix="_y")
        for var in ["echo_lvh", "echo_la_dilate", "echo_normal", "echo_variant",
                    "ef_abnormal", "reflux_grade", "echo_unreadable"]:
            a_col, m_col = var + "_x", var + "_y"
            sub = joined[(joined[a_col].astype(str).str.strip() != "")
                         & (joined[m_col].astype(str).str.strip() != "")]
            if len(sub) < 10:
                continue
            a, b = sub[a_col].tolist(), sub[m_col].tolist()
            classes = (list(m23.REFLUX_ENUM) if var == "reflux_grade"
                       else [m23.TARGET_CLS[var]])
            for cls in classes:
                tp = sum(1 for x, y in zip(a, b) if x == cls and y == cls)
                fp = sum(1 for x, y in zip(a, b) if x != cls and y == cls)
                fn = sum(1 for x, y in zip(a, b) if x == cls and y != cls)
                sup = sum(1 for x in a if x == cls) + sum(1 for y in b if y == cls)
                if var == "reflux_grade" and sup < 10:
                    continue
                f1, lo, hi = wilson_ci(tp, fp, fn)
                rows.append(dict(domain="ECHO", model=model, variable=var, target_class=cls,
                                 n=len(a), TP=tp, FP=fp, FN=fn,
                                 F1=round(f1, 4), Wilson_lo=round(lo, 4), Wilson_hi=round(hi, 4),
                                 gate=0.90, CI_contains_gate=bool(lo <= 0.90 <= hi),
                                 CI_excludes_gate_below=bool(hi < 0.90),
                                 CI_excludes_gate_above=bool(lo > 0.90)))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "wilson_ci_gates.csv"), index=False, encoding="utf-8-sig")
    # SI 展示版（Table S5）：精简列 + 门槛关系一句话
    def vs_gate(r):
        if r.CI_excludes_gate_above:
            return "excludes 0.90 (above)"
        if r.CI_excludes_gate_below:
            return "excludes 0.90 (below)"
        if r.CI_contains_gate:
            return "contains 0.90"
        return ""
    s5 = out.copy()
    s5["vs_gate"] = s5.apply(vs_gate, axis=1)
    s5[["domain", "model", "variable", "target_class", "n", "TP", "FP", "FN",
        "F1", "Wilson_lo", "Wilson_hi", "vs_gate"]].to_csv(
        os.path.join(RES, "tableS5_wilson_gates.csv"), index=False, encoding="utf-8-sig")
    print("\n[B] Wilson CI 表 -> results/wilson_ci_gates.csv（%d 行）+ tableS5_wilson_gates.csv" % len(out))
    borderline = out[out.CI_contains_gate & (out.F1 < 0.95)]
    print("贴线（CI 含 0.90 门槛且 F1<0.95）：")
    print(borderline[["domain", "model", "variable", "target_class", "n", "F1",
                      "Wilson_lo", "Wilson_hi"]].to_string(index=False))
    return out


# ---------------- Part C：重放代理敏感性 ----------------
def build_frame(m35):
    """35 main() 帧重建段（同一口径：v1|v3 可判读行，协变量 prev 波滞后）。"""
    df = pd.read_csv(m35.H3 + "/data/processed/H_analysis_long.csv", encoding="utf-8-sig",
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
    ecgdf = m35.lag_frame(df[df["v1_abnormal"].notna() | df["v3_abnormal"].notna()],
                          sorted(set(m35.HARM_COVS + m35.FULL_COVS)))
    return ecgdf


def part_c(R=20):
    t0 = time.time()
    m35 = load_mod("35_phantom_differential_replay.py", "m35")
    yp = pd.read_csv(os.path.join(RES, "replay_year_params.csv"))
    params = {int(r.year): (float(r.Se), float(r.Sp)) for r in yp.itertuples(index=False)}
    pi_t = {int(r.year): float(r.pi_true) for r in yp.itertuples(index=False)}
    # 金样本逐年有效规模（m3d_peryear 的分层 n）→ Beta-二项后验的 n_pos/n_neg
    py = pd.read_csv(os.path.join(RES, "m3d_peryear.csv"))
    py = py[(py.domain == "ECG") & (py.outcome == "any_abnormal")
            & (py.extractor == "dict v1") & (py.year != "overall")]
    n_t = {int(r.year): int(r.n) for r in py.itertuples(index=False)}
    npos_t = {y: max(1, round(n_t[y] * pi_t[y])) for y in n_t}
    nneg_t = {y: max(1, n_t[y] - npos_t[y]) for y in n_t}

    print(f"[C] 重建全库帧 …", flush=True)
    ecgdf = build_frame(m35)
    print(f"    frame rows={len(ecgdf)}  {time.time()-t0:.0f}s", flush=True)

    years = sorted(params)
    rng = np.random.default_rng(SEED)
    rows = []
    for r in range(R):
        t1 = time.time()
        pmap = {}
        for y in years:
            se, sp = params[y]
            a = 1.0 + se * npos_t[y]
            b = 1.0 + (1.0 - se) * npos_t[y]
            se_d = float(rng.beta(a, b))
            a = 1.0 + sp * nneg_t[y]
            b = 1.0 + (1.0 - sp) * nneg_t[y]
            sp_d = float(rng.beta(a, b))
            pmap[y] = (se_d, sp_d)
        g = ecgdf.copy()
        yt = g["v3_abnormal"].to_numpy()
        yr = np.array([int(x) for x in g["year"].to_numpy()])
        se = np.array([pmap[yy][0] for yy in yr])
        sp = np.array([pmap[yy][1] for yy in yr])
        p_obs = np.where(yt == 1, se, 1.0 - sp)
        g["y_obs"] = (rng.random(len(g)) < p_obs).astype(float)
        res_r = {}
        for key, fe in (("noFE", False), ("yearFE", True)):
            x = m35.fit_cox(g, "y_obs", m35.HARM_COVS, f"S_r{r:02d}{'+yearFE' if fe else ''}",
                            year_fe=fe)
            if x:
                res_r[key] = x
        rows.append(dict(rep=r,
                         **{f"HR_{k}": v["HR"] for k, v in res_r.items()},
                         **{f"CI_lo_{k}": v["CI_lo"] for k, v in res_r.items()},
                         **{f"CI_hi_{k}": v["CI_hi"] for k, v in res_r.items()},
                         **{f"p_{k}": v["p"] for k, v in res_r.items()},
                         draw=json.dumps({str(y): [round(pmap[y][0], 4), round(pmap[y][1], 4)]
                                          for y in years})))
        print(f"    rep {r+1}/{R}: noFE HR={res_r['noFE']['HR']} FE HR={res_r['yearFE']['HR']} "
              f"({time.time()-t1:.0f}s)", flush=True)
        pd.DataFrame(rows).to_csv(os.path.join(RES, "proxy_sensitivity_replay.csv"),
                                  index=False, encoding="utf-8-sig")
    rep = pd.DataFrame(rows)
    summ = dict(R=R, seed=SEED,
                HR_noFE_mean=round(float(rep.HR_noFE.mean()), 4),
                HR_noFE_lo=round(float(rep.HR_noFE.quantile(0.025)), 4),
                HR_noFE_hi=round(float(rep.HR_noFE.quantile(0.975)), 4),
                HR_FE_mean=round(float(rep.HR_yearFE.mean()), 4),
                HR_FE_lo=round(float(rep.HR_yearFE.quantile(0.025)), 4),
                HR_FE_hi=round(float(rep.HR_yearFE.quantile(0.975)), 4),
                frac_noFE_significant=round(float((rep.p_noFE < 0.05).mean()), 3),
                frac_FE_p_above_005=round(float((rep.p_yearFE > 0.05).mean()), 3))
    # 对照：点值代理臂（35 原重放）与真实估计
    rs = pd.read_csv(os.path.join(RES, "replay_summary.csv")).set_index("arm")
    ref = {"point_proxy_B_yearvarying": dict(HR_noFE=rs.loc["B_yearvarying", "HR_noFE"],
                                             HR_FE=rs.loc["B_yearvarying", "HR_yearFE"]),
           "REAL_v1": dict(HR_noFE=rs.loc["REAL_v1", "HR_noFE"],
                           HR_FE=rs.loc["REAL_v1", "HR_yearFE"]),
           "REAL_v3": dict(HR_noFE=rs.loc["REAL_v3", "HR_noFE"],
                           HR_FE=rs.loc["REAL_v3", "HR_yearFE"])}
    out = pd.DataFrame([summ])
    out.to_csv(os.path.join(RES, "proxy_sensitivity_summary.csv"),
               index=False, encoding="utf-8-sig")
    print("\n[C] 汇总 -> results/proxy_sensitivity_summary.csv")
    print(f"  Beta 重抽（金样本精度, R={R}）: noFE HR={summ['HR_noFE_mean']} "
          f"[{summ['HR_noFE_lo']},{summ['HR_noFE_hi']}]，{int(summ['frac_noFE_significant']*100)}% "
          f"次重复 p<0.05；FE HR={summ['HR_FE_mean']} [{summ['HR_FE_lo']},{summ['HR_FE_hi']}]，"
          f"{int(summ['frac_FE_p_above_005']*100)}% 次重复 p>0.05")
    for k, v in ref.items():
        print(f"  对照 {k}: noFE HR={v['HR_noFE']} FE HR={v['HR_FE']}")
    print(f"  total {time.time()-t0:.0f}s")
    return rep


def main():
    parts = "A,B,C"
    R = 20
    for a in sys.argv[1:]:
        if a.startswith("--parts="):
            parts = a.split("=", 1)[1]
        if a.startswith("--R="):
            R = int(a.split("=", 1)[1])
    P = {p.strip().upper() for p in parts.split(",")}
    if "A" in P:
        part_a()
    if "B" in P:
        part_b()
    if "C" in P:
        part_c(R)
    return 0


if __name__ == "__main__":
    sys.exit(main())
