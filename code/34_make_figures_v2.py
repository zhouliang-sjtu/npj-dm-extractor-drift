# -*- coding: utf-8 -*-
"""34_make_figures_v2.py —— 方法学审计⑤：按期刊图表规范重制统计图（Figure2-5）
标准：Arial；语义色板（红#C0392B/蓝#2E86C1/橙#E67E22/灰#7F8C8D/深#2C3E50/绿#1E8449）；
加粗面板字母+斜体小标题；PNG 300dpi + PDF；bbox tight；所有数字与 results/*.csv 逐格对应。
数据源：dict_v1_v3_agreement / m3d_peryear / audit_ci_peryear / phantom_specs_table /
        simex_kappa_grid / m5b_simex_kappa / m5b_simex_backfill
输出：figures/Figure2.png|pdf、Figure3.png|pdf、Figure4.png|pdf、Figure5.png|pdf
      results/table1_phantom_specs.md
用法：python code/34_make_figures_v2.py
"""
import os
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402

matplotlib.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
os.makedirs(FIG, exist_ok=True)
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
# π 单一口径：与 code/06 网格同源，实测自 H_analysis_long（不硬编码）
PI = float(pd.read_csv(os.path.join(H3, "data", "processed", "H_analysis_long.csv"),
                       encoding="utf-8-sig", usecols=["masld"],
                       low_memory=False)["masld"].dropna().mean())

C_RED, C_BLU, C_ORG, C_GRY, C_DRK, C_GRN = ("#C0392B", "#2E86C1", "#E67E22",
                                            "#7F8C8D", "#2C3E50", "#1E8449")
SHIFT = (2022.5, 2023.5)  # 2023 模板转换期底纹


def save(fig, name):
    fig.savefig(os.path.join(FIG, name + ".png"), dpi=300, bbox_inches="tight",
                facecolor="white")
    fig.savefig(os.path.join(FIG, name + ".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print("saved:", name)


def panel(ax, letter, title):
    ax.text(-0.09, 1.06, letter, transform=ax.transAxes, fontsize=15, weight="bold",
            color=C_DRK)
    ax.text(-0.02, 1.06, title, transform=ax.transAxes, fontsize=9.5, style="italic",
            color=C_GRY)


def shift_band(ax, ymax=None):
    ax.axvspan(*SHIFT, color=C_ORG, alpha=0.10, lw=0)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    agr = pd.read_csv(os.path.join(RES, "dict_v1_v3_agreement.csv"))
    py = pd.read_csv(os.path.join(RES, "m3d_peryear.csv"))
    pyci = pd.read_csv(os.path.join(RES, "audit_ci_peryear.csv"))
    spec = pd.read_csv(os.path.join(RES, "phantom_specs_table.csv"))
    grid = pd.read_csv(os.path.join(RES, "simex_kappa_grid.csv"))
    m5k = pd.read_csv(os.path.join(RES, "m5b_simex_kappa.csv"))
    m5b = pd.read_csv(os.path.join(RES, "m5b_simex_backfill.csv"))

    # ================= Figure 2 =================
    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.0))
    axa, axb, axc = axes
    # a) v1 vs v3 κ by year
    by = agr[agr.scope == "by_year"].copy()
    by["year"] = by["year"].astype(int)
    years = sorted(by.year)
    axa.plot(years, by.cohen_kappa, color=C_BLU, marker="o", lw=2, ms=6, label="Cohen's κ (v1 vs v3)")
    shift_band(axa)
    axa.annotate("κ=0.263", (2022, 0.263), xytext=(2022.1, 0.40), fontsize=8.5, color=C_DRK)
    axa.annotate("κ=0.256", (2023, 0.256), xytext=(2022.9, 0.14), fontsize=8.5, color=C_DRK)
    axa.set_ylim(0, 1.05)
    axa.set_ylabel("Cohen's κ")
    axa.set_xlabel("Calendar year")
    axa.legend(loc="lower left", fontsize=8, frameon=False)
    panel(axa, "A", "Dictionary v1 vs v3 agreement (whole corpus)")
    # b) LLM vs gold by year (+dict v1 reference)
    ecg = py[(py.domain == "ECG") & (py.year != "overall")]
    styles = {"qwen2.5:14b": (C_RED, "o", "Qwen2.5-14B (frozen)"),
              "qwen2.5:7b": (C_ORG, "^", "Qwen2.5-7B"),
              "glm4:9b": (C_GRN, "v", "GLM-4-9B"),
              "dict v1": (C_GRY, "s", "Dictionary v1")}
    for ext, (c, mk, lab) in styles.items():
        s = ecg[ecg.extractor == ext].set_index("year").loc[[str(y) for y in years]]
        ci = pyci[(pyci.extractor == ext) & (pyci.year != "overall")].set_index("year").loc[[str(y) for y in years]]
        axb.errorbar(years, s.cohen_kappa.astype(float),
                     yerr=[s.cohen_kappa.astype(float) - ci.ci_lo.astype(float),
                           ci.ci_hi.astype(float) - s.cohen_kappa.astype(float)],
                     color=c, marker=mk, lw=1.8, ms=5, capsize=2.5, label=lab)
    axb.axhline(0.80, color="black", ls=":", lw=1)
    shift_band(axb)
    axb.set_ylim(0, 1.08)
    axb.set_xlabel("Calendar year")
    axb.legend(loc="lower left", fontsize=7.2, frameon=False)
    panel(axb, "B", "LLM extractors vs adjudicated gold (n=71–94/yr)")
    # c) positive-call rates
    axc.plot(years, by.pct_v1_abn, color=C_GRY, marker="s", lw=2, ms=6, label="Dictionary v1")
    axc.plot(years, by.pct_v3_abn, color=C_BLU, marker="D", lw=2, ms=6, label="Dictionary v3")
    shift_band(axc)
    axc.set_ylim(0, 80)
    axc.set_xlabel("Calendar year")
    axc.set_ylabel("Positive calls for any ECG abnormality (%)")
    axc.legend(loc="upper left", fontsize=8, frameon=False)
    panel(axc, "C", "Per-year positive-call rates (v1 vs v3)")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(w_pad=2.4)
    save(fig, "Figure2")

    # ================= Figure 3 (forest with CI) =================
    fig, ax = plt.subplots(figsize=(8.6, 5.6))
    order = ["harmonized_v1", "harmonized_v1+yearFE", "harmonized_v3", "harmonized_v3+yearFE",
             "fullcov_anyAbnormal", "fullcov_anyAbnormal+yearFE", "fullcov_STT",
             "fullcov_STT+yearFE", "fullcov_AF", "fullcov_AF+yearFE",
             "fullcov_anyBlock", "fullcov_anyBlock+yearFE"]
    labels = ["Dict v1, harmonized", "+ year fixed effects", "Dict v3, harmonized",
              "+ year fixed effects", "v1 full-covariate: any abnormality",
              "+ year fixed effects", "v1 full-covariate: ST-T",
              "+ year fixed effects", "v1 full-covariate: AF",
              "+ year fixed effects", "v1 full-covariate: conduction block",
              "+ year fixed effects"]
    sp = spec.set_index("spec").loc[order]
    ys = list(range(len(order)))[::-1]
    for y, (spec_name, r) in zip(ys, sp.iterrows()):
        c = C_RED if spec_name.startswith("harmonized_v3") else C_BLU
        if spec_name.startswith("fullcov"):
            c = C_DRK
        ax.plot([r.CI_lo, r.CI_hi], [y, y], color=c, lw=2.2, solid_capstyle="round")
        ax.scatter([r.HR], [y], s=52, color=c, zorder=3)
        ax.annotate(f"{r.HR:.2f} ({r.CI_lo:.2f}–{r.CI_hi:.2f})",
                    xy=(r.CI_hi, y), xytext=(6, 0), textcoords="offset points",
                    va="center", fontsize=8, color=C_DRK)
    ax.axvline(1, color="black", lw=1)
    ax.set_yticks(ys)
    ax.set_yticklabels(labels, fontsize=8.6)
    ax.set_xlabel("Hazard ratio for MASLD (previous wave) → incident ECG abnormality (95% CI)")
    ax.set_xscale("log")
    ax.set_xticks([0.8, 0.9, 1.0, 1.1, 1.2, 1.4])
    ax.set_xticklabels(["0.8", "0.9", "1.0", "1.1", "1.2", "1.4"])
    ax.set_xlim(0.62, 1.75)
    ax.spines[["top", "right"]].set_visible(False)
    handles = [Line2D([], [], color=C_BLU, lw=2.2, label="Harmonized spec (v1/v3 × year-FE)"),
               Line2D([], [], color=C_RED, lw=2.2, label="Dict v3 (phantom)"),
               Line2D([], [], color=C_DRK, lw=2.2, label="Full-covariate production spec")]
    ax.legend(handles=handles, loc="lower right", fontsize=8, frameon=False)
    fig.tight_layout()
    save(fig, "Figure3")

    # ================= Figure 4 (transportability) =================
    fig, ax = plt.subplots(figsize=(8.2, 4.8))
    styles4 = {"dict v1": (C_GRY, "s", "--", "Dictionary v1 (production)"),
               "dict v3": (C_DRK, "D", "-", "Dictionary v3 (negation-window)"),
               "qwen2.5:14b": (C_RED, "o", "-", "Qwen2.5-14B (frozen)"),
               "qwen2.5:7b": (C_ORG, "^", "-", "Qwen2.5-7B"),
               "glm4:9b": (C_GRN, "v", "-", "GLM-4-9B")}
    yrs = [str(y) for y in years]
    for ext, (c, mk, ls, lab) in styles4.items():
        s = ecg[ecg.extractor == ext].set_index("year").loc[yrs]
        # 2026-09-13 终审：词典两列同样画 bootstrap 95% CI（audit_ci_peryear.csv 本就含
        # dict v1/v3 行）——与图例 "bootstrap 95% CI for all extractors" 及 Fig2b 处理一致；
        # v3 的 CI 退化为零宽（κ=1.000 全年份），视觉上不可见属预期
        ci = pyci[(pyci.extractor == ext) & (pyci.year != "overall")].set_index("year").loc[yrs]
        ms = 6 if ext in ("dict v1", "dict v3") else 5
        ax.errorbar(range(len(yrs)), s.cohen_kappa.astype(float),
                    yerr=[s.cohen_kappa.astype(float) - ci.ci_lo.astype(float),
                          ci.ci_hi.astype(float) - s.cohen_kappa.astype(float)],
                    color=c, marker=mk, ls=ls, lw=1.8, ms=ms, capsize=2.5, label=lab)
    ax.axhline(0.80, color="black", ls=":", lw=1)
    ax.text(len(yrs) - 0.98, 0.812, "acceptance gate κ=0.80", fontsize=8, va="bottom")
    ax.axvspan(4.5, 5.5, color=C_ORG, alpha=0.10, lw=0)  # 2023 模板切换（索引轴 5；图注说明，图内不再加注释以避免与图例重叠）
    ax.set_xticks(range(len(yrs)))
    ax.set_xticklabels(yrs)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("Cohen's κ vs adjudicated gold\n(any ECG abnormality)")
    ax.set_xlabel("Calendar year (gold-standard stratum)")
    ax.legend(fontsize=8, frameon=False, ncol=2, loc="lower left")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    save(fig, "Figure4")

    # ================= Figure 5 (grid + measured κ) =================
    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.6))
    axa, axb = axes
    cmap = plt.get_cmap("viridis")
    kmeas = float(m5k[m5k.domain == "POOLED"].iloc[0]["cohen_kappa"])
    band = round(kmeas * 20) / 20
    for i, (kg, gg) in enumerate(grid.groupby("kappa")):
        gg = gg.sort_values("HR_true")
        hit = abs(kg - band) < 0.026
        axa.plot(gg.HR_true, gg.HR_obs, color=cmap(i / 7), lw=2.0 if hit else 1.2,
                 alpha=1.0 if hit else 0.45,
                 label=f"κ={kg:.2f}" + (" (measured band)" if hit else ""))
    axa.plot([1, 1.8], [1, 1.8], "k--", lw=1)
    axa.set_xlabel("True effect HR_true")
    axa.set_ylabel("Observed HR_obs")
    axa.legend(loc="upper left", fontsize=7, frameon=False)
    panel(axa, "A", f"Analytic attenuation grid (π={PI:.3f})")
    hr_t = np.linspace(1.0, 1.5, 50)
    from scipy.optimize import brentq  # noqa: E402

    def hr_obs(hr, s, pi=PI):
        p1 = pi * s + (1 - pi) * (1 - s)
        p0 = 1 - p1
        return ((pi * s * hr + (1 - pi) * (1 - s)) / p1) / \
               ((pi * (1 - s) * hr + (1 - pi) * s) / p0)

    def solve_s(kappa, pi=PI):
        def f(sv):
            p1 = pi * sv + (1 - pi) * (1 - sv)
            pe = p1 * p1 + (1 - p1) ** 2
            return (sv - pe) / (1 - pe) - kappa
        return brentq(f, 0.5, 0.99999)

    s_c = solve_s(kmeas)
    axb.plot(hr_t, [hr_obs(h, s_c) for h in hr_t], color=C_RED, lw=2.6,
             label=f"Measured κ={kmeas:.2f} (dict v1 vs gold, n=585)")
    colors = [C_BLU, C_GRN]
    for (name, r), c in zip(m5b.iterrows(), colors):
        axb.scatter([r.HR_corrected], [r.HR_observed], s=70, color=c, zorder=5)
        axb.annotate(f"{r.HR_observed:.4f}→{r.HR_corrected:.4f}",
                     xy=(r.HR_corrected, r.HR_observed), xytext=(8, -12),
                     textcoords="offset points", fontsize=8, color=c)
    axb.plot([1, 1.5], [1, 1.5], "k--", lw=1)
    axb.set_xlabel("True effect HR_true")
    axb.set_ylabel("Observed HR_obs")
    axb.legend(loc="upper left", fontsize=7.5, frameon=False)
    panel(axb, "B", "SIMEX-corrected estimates at the measured κ")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout(w_pad=2.4)
    save(fig, "Figure5")

    # ================= Table 1 (phantom specs) =================
    t1 = spec.copy()
    t1["HR (95% CI)"] = [f"{r.HR:.3f} ({r.CI_lo:.3f}–{r.CI_hi:.3f})" for _, r in t1.iterrows()]
    t1["P"] = [f"{r.p:.2g}" for _, r in t1.iterrows()]
    lines = ["# Table 1（草表）— MASLD → incident ECG abnormality: discrete-time Cox specifications",
             "",
             "| Specification | Outcome | n at risk | Events | HR (95% CI) | P |",
             "|---|---|---|---|---|---|"]
    for _, r in t1.iterrows():
        lines.append(f"| {r['spec']} | {r['outcome']} | {int(r.n_risk):,} | {int(r.n_events):,} "
                     f"| {r['HR (95% CI)']} | {r['P']} |")
    lines += ["", "注：harmonized=8协变量（07口径）；fullcov=13协变量（10_explore口径）；"
              "暴露与协变量均取 prev 波；yearFE=CoxPHFitter(T=1, penalizer=0.01, cluster=id)。"
              "2026-09-10 审计重估（code/32），取代早期数据构建下的 ecg_newonset_cox*.csv。"]
    open(os.path.join(RES, "table1_phantom_specs.md"), "w", encoding="utf-8").write("\n".join(lines))
    print("-> results/table1_phantom_specs.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
