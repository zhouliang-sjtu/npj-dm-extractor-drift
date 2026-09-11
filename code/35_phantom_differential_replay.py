# -*- coding: utf-8 -*-
"""35_phantom_differential_replay.py —— 审稿预演 M1/M10/M3/M4 补强（2026-09-10）

目的：把幻影机制从"排除法解释"升级为"定量重现"。
  M1 重放仿真：以 v3 结局为真值代理（v3 对金标准逐年 κ=1.000），
    在金样本上直接实测 dict v1 的逐年非对称错分参数 (Se_t, Sp_t)
    （金标准终值 vs v1 无否定窗口重放的逐年混淆矩阵，2022-23 以漏检为主导），
    对真值结局施加该年索引错分、完整重建"既往波无结局"风险集并拟合
    harmonized 离散时间 Cox——检验能否定量重现真实 v1 的估计（HR 0.9804 / +yearFE 0.9735）。
  对照臂：
    A  无错分（=v3 真值代理本身，须逐位复现 phantom_specs_table 的 v3 行——构建正确性校验）
    C1 固定错分（总体 (Se,Sp) 常数：同一误差总量、不随年份变化——非微分对照）
    C2 年份置换错分（把 (Se_t,Sp_t) 按年份倒序重排，破坏与暴露率趋势的对齐）
    C3 对称错分（逐年 κ_t 反解 Se=Sp=s_t——检验稿件网格的"对称假设"是否足以重现 v1）
  M10 时变 QBA 公式：Methods 给出显式年索引生成模型
    P(Y_obs=1 | Y*, t) = Se_t·1[Y*=1] + (1−Sp_t)·1[Y*=0]。
  M3 参考标准误差→抽取器实测 κ 衰减界：蒙特卡洛（金标准以错误率 r_ref 翻转标签）。
  M4 惩罚项敏感性：year-FE 规格 penalizer ∈ {0.001, 0.01, 0.1}。

输出：results/phantom_differential_replay.csv（逐次拟合）
      results/replay_summary.csv（各臂汇总）
      results/ref_error_attenuation.csv
      results/penalizer_sensitivity.csv
      figures/figS1_differential_replay.png/.pdf
用法：python code/35_phantom_differential_replay.py [R]   # R=重放次数，默认 30
"""
import os
import sys
import time

import numpy as np
import pandas as pd
from lifelines import CoxPHFitter, CoxTimeVaryingFitter

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
HARM_COVS = ["sii_q", "proteinuria", "bmi", "htn_screen", "dm_screen"]
FULL_COVS = ["sii_q", "proteinuria", "tyg", "bmi", "waist", "fpg", "egfr",
             "central_obese", "high_tg", "hyperuricemia", "dm_screen", "htn_screen"]
LAG_ALL = ["age", "sex_male", "masld"] + sorted(set(HARM_COVS + FULL_COVS))
SEED = 42

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


# ---------- 公共拟合器：协变量已在帧内预滞后（与 32 同口径：暴露/协变量均 prev 波） ----------
def fit_cox(g_all, outkey, covs, tag, year_fe=False, penalizer=0.01):
    """风险集=既往波该结局为 0 且当前波可判读、间隔≤2 年；结局错分重放时逐次重建。"""
    g = g_all.sort_values(["id", "year"]).copy()
    g["_prev_y"] = g.groupby("id")[outkey].shift()
    g["_prev_t"] = g.groupby("id")["year"].shift()
    keep = g["_prev_y"].notna() & g[outkey].notna() & ((g["year"] - g["_prev_t"]) <= 2)
    g = g[keep & (g["_prev_y"] == 0)].copy()
    if len(g) < 200:
        return None
    g["event"] = g[outkey].astype(int)
    covs_all = ["p_age", "p_male", "masld"] + list(covs)
    if year_fe:
        ydum = pd.get_dummies(g["year"].astype(int), prefix="y", drop_first=True).astype(float)
        g = pd.concat([g, ydum], axis=1)
        covs_all = covs_all + list(ydum.columns)
    g = g.dropna(subset=covs_all)
    if year_fe:
        g["T"] = 1.0
        cph = CoxPHFitter(penalizer=penalizer)
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
    coef, se = float(s["coef"]), float(s["se(coef)"])
    return dict(spec=tag, n_risk=len(g), n_events=int(g["event"].sum()),
                HR=round(float(np.exp(coef)), 4),
                CI_lo=round(float(np.exp(coef - 1.959964 * se)), 4),
                CI_hi=round(float(np.exp(coef + 1.959964 * se)), 4),
                p=float(s["p"]))


def solve_s(kappa, pi, lo=0.5, hi=1.0, tol=1e-10):
    """对称 Se=Sp=s 反解（完美参考标准，与稿件网格同式）：
    阳性边际 p1*=πs+(1−π)(1−s)=1−π+s(2π−1)；期望一致率 po=s；
    pe=p1*²+(1−p1*)²；κ=(po−pe)/(1−pe)=(s−pe)/(1−pe)。"""
    def k_of_s(s):
        p1 = 1.0 - pi + s * (2.0 * pi - 1.0)
        pe = p1 * p1 + (1.0 - p1) ** 2
        return (s - pe) / (1.0 - pe)
    if k_of_s(lo) >= kappa:
        return lo
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if k_of_s(mid) < kappa:
            lo = mid
        else:
            hi = mid
        if hi - lo < tol:
            break
    return 0.5 * (lo + hi)


def lag_frame(frame, covs):
    """32 口径：暴露与协变量在帧内按 id 取 prev 波；age/sex 改名 p_age/p_male。"""
    g = frame.copy()
    for c in ["age", "sex_male", "masld"] + list(covs):
        g[c] = g.groupby("id")[c].shift()
    return g.rename(columns={"age": "p_age", "sex_male": "p_male"})


def main():
    R = int(sys.argv[1]) if len(sys.argv) > 1 else 30
    t0 = time.time()
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

    # 与 32 完全同帧：v1|v3 可判读（=文本非空 122,059 行），滞后协变量一次性预计算
    ecgdf = lag_frame(df[df["v1_abnormal"].notna() | df["v3_abnormal"].notna()],
                      sorted(set(HARM_COVS + FULL_COVS)))
    print(f"build done {time.time()-t0:.0f}s | frame rows={len(ecgdf)}", flush=True)

    # ---- 实测逐年非对称错分参数：全库口径 dict v1 vs 真值代理（v3）的逐年混淆矩阵 ----
    # （在 v1 可判读行上直接取 (Se_t, Sp_t)，无抽样富集偏差；金样本按关键词层富集会
    #   高估 v1 的 Se——2022 年金样本 Se=0.54 vs 全库口径 Se≈0.34，见 replay_year_params.csv）
    ok = ecgdf[ecgdf["v3_abnormal"].notna() & ecgdf["v1_abnormal"].notna()].copy()
    pi_corpus = ok.groupby("year")["v3_abnormal"].mean().to_dict()
    years = sorted({int(y) for y in ok.year})
    params, years_meas = {}, []
    print("\n== M10 年索引错分参数（全库实测：dict v1 vs 真值代理 v3） ==")
    print("  year     n  pi_true  Se_t    Sp_t    p_obs_pos")
    for y in years:
        sub = ok[ok.year.astype(int) == y]
        gt = sub.v3_abnormal == 1
        et = sub.v1_abnormal == 1
        tp = float((gt & et).sum())
        fn = float((gt & ~et).sum())
        tn = float((~gt & ~et).sum())
        fp = float((~gt & et).sum())
        se_t = tp / (tp + fn)
        sp_t = tn / (tn + fp)
        params[y] = (se_t, sp_t)
        years_meas.append(dict(year=y, n=len(sub), pi_true=round(float(gt.mean()), 3),
                               Se=round(se_t, 3), Sp=round(sp_t, 3),
                               p_obs_pos=round(float(et.mean()), 3)))
        print(f"  {y}  {len(sub):6d}   {gt.mean():.3f}   {se_t:.3f}   {sp_t:.3f}   "
              f"{et.mean():.3f}")
    pd.DataFrame(years_meas).to_csv(os.path.join(RES, "replay_year_params.csv"),
                                    index=False, encoding="utf-8-sig")
    gt_all = ok.v3_abnormal == 1
    et_all = ok.v1_abnormal == 1
    se_all = float((gt_all & et_all).sum() / gt_all.sum())
    sp_all = float((~gt_all & ~et_all).sum() / (~gt_all).sum())
    print(f"  overall: Se={se_all:.3f} Sp={sp_all:.3f}（固定错分对照臂 C1 用同一误差总量）")
    # 对称对照臂 C3：由实测逐年 κ_t 反解 s_t（与稿件网格同式）——检验"对称假设"是否足够
    py = pd.read_csv(os.path.join(RES, "m3d_peryear.csv"))
    kp = py[(py["domain"] == "ECG") & (py["outcome"] == "any_abnormal")
            & (py["extractor"] == "dict v1") & (py["year"] != "overall")].copy()
    kp["year"] = kp["year"].astype(int)
    kappa_t = dict(zip(kp["year"], kp["cohen_kappa"]))
    sym_map = {y: (solve_s(kappa_t[y], pi_corpus.get(y, 0.5)),) * 2 for y in years}
    perm_map = {y: params[years[len(years) - 1 - i]] for i, y in enumerate(years)}  # 年份倒序置换

    YSTAR = "v3_abnormal"
    rng_master = np.random.default_rng(SEED)
    rows = []

    def run_arm(tag, reps, mode, rng):
        """mode: 'truth'（无错分）| dict（逐年参数映射）"""
        for r in range(reps):
            t1 = time.time()
            g = ecgdf.copy()
            if mode == "truth":
                g["y_obs"] = g[YSTAR]
                stag = tag
            else:
                yt = g[YSTAR].to_numpy()
                yr = g["year"].to_numpy()
                se = np.array([mode[yy][0] for yy in yr])
                sp = np.array([mode[yy][1] for yy in yr])
                p_obs = np.where(yt == 1, se, 1.0 - sp)
                g["y_obs"] = (rng.random(len(g)) < p_obs).astype(float)
                stag = f"{tag}_r{r:02d}"
            a = fit_cox(g, "y_obs", HARM_COVS, stag, year_fe=False)
            b = fit_cox(g, "y_obs", HARM_COVS, stag + "+yearFE", year_fe=True)
            for x in (a, b):
                if x:
                    x["arm"] = tag
                    rows.append(x)
            print(f"  [{stag}] noFE HR={a['HR'] if a else None} "
                  f"(n={a['n_risk'] if a else 0},ev={a['n_events'] if a else 0}) "
                  f"FE HR={b['HR'] if b else None}  {time.time()-t1:.0f}s", flush=True)

    # ---- 臂A：真值代理（构建正确性校验，应复现 phantom_specs_table v3 行）----
    print("\n== Arm A: truth proxy (v3, no error) ==", flush=True)
    run_arm("A_truth", 1, "truth", rng_master)

    # ---- 臂B：实测逐年微分错分重放 ----
    print(f"\n== Arm B: replay with measured year-varying (Se_t,Sp_t), R={R} ==", flush=True)
    run_arm("B_yearvarying", R, params, rng_master)

    # ---- 臂C1：固定错分（同一误差总量、不随年份变化的非微分对照）----
    print(f"\n== Arm C1: fixed non-differential error (Se={se_all:.3f}, Sp={sp_all:.3f}), R={R} ==",
          flush=True)
    run_arm("C1_fixed", R, {y: (se_all, sp_all) for y in years}, rng_master)

    # ---- 臂C2：年份置换（破坏与暴露趋势对齐）----
    print("\n== Arm C2: year-permuted error ==", flush=True)
    run_arm("C2_permuted", min(R, 10), perm_map, rng_master)

    # ---- 臂C3：对称错分（Se=Sp，逐年 κ_t 反解——检验网格的对称假设是否足以重现 v1）----
    print("\n== Arm C3: symmetric year-varying error (Se=Sp from measured kappa_t) ==", flush=True)
    run_arm("C3_symmetric", min(R, 10), sym_map, rng_master)

    rep = pd.DataFrame(rows)
    rep.to_csv(os.path.join(RES, "phantom_differential_replay.csv"), index=False, encoding="utf-8-sig")

    # ---- 汇总（真值行直接取，重放臂给均值与 2.5/97.5 分位）----
    def summarize(sub):
        nofe = sub[~sub["spec"].str.contains("yearFE")]
        fe = sub[sub["spec"].str.contains("yearFE")]
        out = {}
        for name, s in (("noFE", nofe), ("yearFE", fe)):
            out[f"HR_{name}"] = round(float(s["HR"].mean()), 4)
            out[f"HR_{name}_lo"] = round(float(s["HR"].quantile(0.025)), 4)
            out[f"HR_{name}_hi"] = round(float(s["HR"].quantile(0.975)), 4)
            out[f"n_risk_{name}"] = int(s["n_risk"].mean())
            out[f"events_{name}"] = int(s["n_events"].mean())
        out["R"] = len(nofe)
        return out

    summ = []
    for tag, grp in rep.groupby("arm"):
        d = {"arm": tag}
        d.update(summarize(grp))
        summ.append(d)
    summ = pd.DataFrame(summ)
    for name, hr, hrfe in [("REAL_v1", 0.9804, 0.9735), ("REAL_v3", 1.1196, 0.9797)]:
        summ.loc[len(summ)] = {"arm": name, "HR_noFE": hr, "HR_noFE_lo": np.nan,
                               "HR_noFE_hi": np.nan, "HR_yearFE": hrfe, "HR_yearFE_lo": np.nan,
                               "HR_yearFE_hi": np.nan, "R": 1}
    summ.to_csv(os.path.join(RES, "replay_summary.csv"), index=False, encoding="utf-8-sig")
    print("\n== 重放汇总 ==\n", summ.to_string(index=False), flush=True)

    # ---- M4：惩罚项敏感性（真实结局 year-FE 规格 × penalizer；帧内重新滞后，与 32 同口径）----
    print("\n== M4: year-FE penalizer sensitivity ==", flush=True)
    pen_rows = []
    harm_frame = lag_frame(df[df["v1_abnormal"].notna() | df["v3_abnormal"].notna()], HARM_COVS)
    full_frame = lag_frame(df[df["ecg_abnormal"].notna()], FULL_COVS)
    for frame, key, covs, tag in [
            (harm_frame, "v1_abnormal", HARM_COVS, "harm_v1+FE"),
            (harm_frame, "v3_abnormal", HARM_COVS, "harm_v3+FE"),
            (full_frame, "ecg_stt", FULL_COVS, "fullcov_STT+FE")]:
        for pen in (0.001, 0.01, 0.1):
            r = fit_cox(frame, key, covs, f"{tag}@pen{pen}", year_fe=True, penalizer=pen)
            if r:
                r["penalizer"] = pen
                r["spec"] = tag
                pen_rows.append(r)
                print(f"  {tag} pen={pen}: HR={r['HR']} p={r['p']:.3g}", flush=True)
    pd.DataFrame(pen_rows).to_csv(os.path.join(RES, "penalizer_sensitivity.csv"),
                                  index=False, encoding="utf-8-sig")

    # ---- M3：参考标准误差 → 实测 κ 衰减（蒙特卡洛）----
    print("\n== M3: reference-error attenuation of measured kappa ==", flush=True)
    rng = np.random.default_rng(SEED + 1)
    n = 400_000
    att = []
    for k_true in (0.85, 0.90, 0.95, 0.99):
        s = solve_s(k_true, 0.5)
        for r_ref in (0.005, 0.01, 0.023, 0.05):
            truth = (rng.random(n) < 0.5).astype(float)
            ext = np.where(truth == 1, (rng.random(n) < s).astype(float),
                           (rng.random(n) >= s).astype(float))
            ref = np.where(truth == 1, (rng.random(n) >= r_ref).astype(float),
                           (rng.random(n) < r_ref).astype(float))
            po = float((ext == ref).mean())
            k_meas = (po - 0.5) / 0.5
            att.append({"kappa_true": k_true, "ref_error": r_ref,
                        "kappa_measured": round(k_meas, 4),
                        "attenuation": round(k_true - k_meas, 4)})
    att = pd.DataFrame(att)
    att.to_csv(os.path.join(RES, "ref_error_attenuation.csv"), index=False, encoding="utf-8-sig")
    print(att.to_string(index=False), flush=True)

    # ---- figS1：逐年参数 + 重放森林 ----
    plt.rcParams.update({"font.family": "Arial", "font.size": 8, "savefig.dpi": 300,
                         "pdf.fonttype": 42})
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(7.05, 3.1),
                                   gridspec_kw={"width_ratios": [1, 1.35]})
    xs = np.arange(len(years))
    se_line = [params[y][0] for y in years]
    sp_line = [params[y][1] for y in years]
    ax1.plot(xs, se_line, "o-", color="#D55E00", lw=1.2, ms=4, label="Se(t)  (under-detection)")
    ax1.plot(xs, sp_line, "s--", color="#0072B2", lw=1.2, ms=4, label="Sp(t)  (over-detection)")
    ax1.set_xticks(xs)
    ax1.set_xticklabels([str(y) for y in years], rotation=45, fontsize=6)
    ax1.set_ylim(0.28, 1.05)
    ax1.set_ylabel("measured error of dict v1 vs truth proxy")
    ax1.set_title("a  Year-indexed error, measured on the full corpus", fontsize=7.5,
                  fontweight="bold", loc="left")
    ax1.legend(fontsize=6, frameon=False, loc="lower left")
    ax1.spines[["top", "right"]].set_visible(False)
    order = [("REAL_v3", "v3 (truth proxy), real", "#0072B2"),
             ("REAL_v1", "v1 (legacy), real", "#7f7f7f"),
             ("B_yearvarying", "replay: measured year-varying error", "#D55E00"),
             ("C1_fixed", "replay: fixed error (same total)", "#009E73"),
             ("C2_permuted", "replay: year-permuted error", "#CC79A7"),
             ("C3_symmetric", "replay: symmetric (Se=Sp) error", "#56B4E9")]
    ys = np.arange(len(order))[::-1]
    sm = summ.set_index("arm")
    for y, (arm, lab, col) in zip(ys, order):
        row = sm.loc[arm]
        hr, lo, hi = row["HR_noFE"], row.get("HR_noFE_lo"), row.get("HR_noFE_hi")
        fe = row["HR_yearFE"]
        has_ci = bool(np.isfinite(lo)) if lo is not None else False
        if has_ci:
            ax2.plot([lo, hi], [y, y], color=col, lw=1.1, alpha=0.55)
        ax2.scatter([hr], [y], s=30, color=col, zorder=3,
                    label="no year-FE" if y == ys[0] else None)
        ax2.scatter([fe], [y], s=30, facecolor="white", edgecolor=col, zorder=3,
                    label="+ year-FE" if y == ys[0] else None)
        ax2.annotate(f"{hr:.3f}", xy=(hr, y), xytext=(0, 5), textcoords="offset points",
                     ha="center", fontsize=5.6, color=col)
    ax2.axvline(1, color="black", lw=0.8)
    ax2.set_yticks(ys)
    ax2.set_yticklabels([o[1] for o in order], fontsize=6.4)
    ax2.set_xlabel("HR for MASLD → incident any-ECG-abnormality (harmonized)")
    ax2.set_xlim(0.90, 1.22)
    ax2.set_title("b  Differential replay reproduces the legacy estimate", fontsize=7.5,
                  fontweight="bold", loc="left")
    ax2.legend(fontsize=6, frameon=False, loc="upper left")
    ax2.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(os.path.join(FIG, "figS1_differential_replay.png"), dpi=300, facecolor="white",
                bbox_inches="tight")
    fig.savefig(os.path.join(FIG, "figS1_differential_replay.pdf"), facecolor="white",
                bbox_inches="tight")
    print(f"\n-> figures/figS1_differential_replay.png/.pdf | total {time.time()-t0:.0f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
