# -*- coding: utf-8 -*-
"""B31_definition_alignment.py —— 定义对齐重算 + 分歧层抽样清单（第1步 + 第2步准备）

背景（B30 诊断）：生产 v1 的 any-abnormal 是**枚举式 OR**（十类异常位任一为 1），
现稿 v3 的是**"非显式正常"**（normal==0 且 unreadable==0）。两者口径不同，
2023 年约 43% 记录落在"非枚举异常、亦非显式正常"（典型为只有"窦性心律"的稀疏叙述）
→ 现稿 v1×v3 在 2023 的 κ=0.256 主要是**定义性伪差异**（同定义下 κ=0.968）。

本脚本：
 A) 逐年一致率（三组口径）：①现稿 [prod 列 vs v3-A] ②定义对齐 [prod-OR vs v3-OR] ③A′ [1-normal vs v3-A]
 B) 定义对下游的影响预览：harmonized 8 协变量下 {v1-A′, v1-OR, v3-A, v3-OR} × {noFE, yearFE} 的 HR
 C) 分歧层抽样清单（120 例，含人工判读空列），供第 2 步逐例核对

输入：H_analysis_long.csv（生产 v1 标志位 + ecg_text）
输出：results/B31_definition_matched_agreement.csv/.txt、B31_definition_matched_cox.csv
      data/B31_divergent_stratum_samples.csv/.xlsx
用法：python code/B31_definition_alignment.py
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
HARM = ["sii_q", "proteinuria", "bmi", "htn_screen", "dm_screen"]
# 共同可比的特征组（生产层缺 bbb/other/unreadable；block 以 anyBlock ⟷ avblock|bbb 对齐）
PAIRS = [("ecg_af", "ecg_af"), ("ecg_pacPvc", "ecg_pac_pvc"), ("ecg_stt", "ecg_stt"),
         ("ecg_rate", "ecg_rate"), ("ecg_srirr", "ecg_srirr"), ("ecg_axis", "ecg_axis"),
         ("ecg_qwave", "ecg_qwave_mi")]
rep = []


def rl(s=""):
    print(s, flush=True)
    rep.append(str(s))


def kap(a, b):
    po = float((a == b).mean())
    pe = sum(float((a == L).mean()) * float((b == L).mean()) for L in (0, 1))
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def agree(a, b):
    return float((a == b).mean()) * 100


t0 = time.time()
sys.path.insert(0, os.path.join(ROOT, "code"))
import main as M  # noqa: E402

CACHE = os.path.join(RES, "B31_v3_flags_cache.csv.gz")
d = pd.read_csv(os.path.join(H3, "data", "processed", "H_analysis_long.csv"),
                encoding="utf-8-sig", dtype={"id": str, "ecg_text": str}, low_memory=False)
d = d.sort_values(["id", "year"]).reset_index(drop=True)
m = d["ecg_text"].notna()
if os.path.exists(CACHE):
    c = pd.read_csv(CACHE, encoding="utf-8-sig")
    if len(c) == len(d):
        for col in c.columns:
            d[col] = c[col].to_numpy()
        rl("v3 12 位标志：自缓存载入")
    else:
        c = None
else:
    c = None
if c is None or len(c) != len(d):
    v3 = pd.DataFrame(d.loc[m, "ecg_text"].map(lambda t: M.extract_ecg(M.norm(t))).tolist())
    for col in v3.columns:
        d["v3_" + col] = np.nan
        d.loc[m, "v3_" + col] = v3[col].values
    pd.DataFrame({f"v3_{col}": d[f"v3_{col}"] for col in v3.columns}) \
        .to_csv(CACHE, index=False, encoding="utf-8-sig")
    rl(f"v3 12 位标志：现场重跑并写缓存（{time.time() - t0:.0f}s）")

# ---------- 定义 ----------
d["v3_A"] = np.where((d["v3_ecg_normal"] == 0) & (d["v3_ecg_unreadable"] == 0), 1.0, 0.0)
d.loc[~m, "v3_A"] = np.nan
d["v3_B"] = (((d[[f"v3_{v}" for _, v in PAIRS]].fillna(0).sum(axis=1) > 0) |
              (d["v3_ecg_avblock"].fillna(0) + d["v3_ecg_bbb"].fillna(0) > 0))).astype(float)
d.loc[~m, "v3_B"] = np.nan
num = lambda s: pd.to_numeric(d[s], errors="coerce")
d["v1_A2"] = np.where(num("ecg_normal") == 0, 1.0, 0.0)          # 1−显式正常（无 unreadable 列）
d["v1_B"] = ((d[[p for p, _ in PAIRS]].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) > 0) |
             (num("ecg_anyBlock").fillna(0) > 0)).astype(float)
d["v1_draft"] = num("ecg_abnormal")

rl("\n=== A) 逐年一致率：三种口径 ===")
rl(f"{'年':>6}{'n':>8}{'v1draft%':>10}{'v1_B%':>8}{'v1A2%':>8}{'v3A%':>8}{'v3B%':>8}"
   f"{'现稿κ':>9}{'对齐κB':>10}{'A2κ':>8}")
rows = []
s = d.dropna(subset=["v1_draft", "v3_A"])
for y, g in s.groupby("year"):
    if len(g) < 200:
        continue
    rows.append({"year": int(y), "n": len(g),
                 "v1_draft_pct": round(g["v1_draft"].mean() * 100, 2),
                 "v1_B_pct": round(g["v1_B"].mean() * 100, 2),
                 "v1_A2_pct": round(g["v1_A2"].mean() * 100, 2),
                 "v3_A_pct": round(g["v3_A"].mean() * 100, 2),
                 "v3_B_pct": round(g["v3_B"].mean() * 100, 2),
                 "kappa_draft": round(kap(g["v1_draft"].astype(int), g["v3_A"].astype(int)), 3),
                 "agree_draft": round(agree(g["v1_draft"], g["v3_A"]), 2),
                 "kappa_matched": round(kap(g["v1_B"].astype(int), g["v3_B"].astype(int)), 3),
                 "agree_matched": round(agree(g["v1_B"], g["v3_B"]), 2),
                 "kappa_A2": round(kap(g["v1_A2"].astype(int), g["v3_A"].astype(int)), 3),
                 "agree_A2": round(agree(g["v1_A2"], g["v3_A"]), 2)})
A = pd.DataFrame(rows)
for r in A.itertuples():
    rl(f"{r.year:>6}{r.n:>8}{r.v1_draft_pct:>10.1f}{r.v1_B_pct:>8.1f}{r.v1_A2_pct:>8.1f}"
       f"{r.v3_A_pct:>8.1f}{r.v3_B_pct:>8.1f}{r.kappa_draft:>9.3f}{r.kappa_matched:>10.3f}"
       f"{r.kappa_A2:>8.3f}")
A.to_csv(os.path.join(RES, "B31_definition_matched_agreement.csv"), index=False,
         encoding="utf-8-sig")
rl("\n判读：'现稿κ' 与 '对齐κB' 的差距 = 定义性伪差异；若 κB 各年平稳（≈0.87–0.97），"
   "则'v1×v3 逐年崩塌'应改写为'定义/手册覆盖差异在稀疏文本年份被放大'。")

# ---------- B) 定义对下游的影响预览（harmonized）----------
rl("\n=== B) 定义对下游 HR 的影响（harmonized 8 协变量）===")
FRAME = d
OUTs = {"v1_draft(现稿v1)": "v1_draft", "v1_B(枚举OR)": "v1_B", "v1_A2(非正常)": "v1_A2",
        "v3_A(现稿v3)": "v3_A", "v3_B(枚举OR)": "v3_B"}


def build(outkey, year_fe):
    g = FRAME.sort_values(["id", "year"]).copy()
    g["_prev_y"] = g.groupby("id")[outkey].shift()
    g["_prev_t"] = g.groupby("id")["year"].shift()
    for cc in ["age", "sex_male", "masld"] + HARM:
        g[cc] = g.groupby("id")[cc].shift()
    g = g.rename(columns={"age": "p_age", "sex_male": "p_male"})
    keep = g["_prev_y"].notna() & g[outkey].notna() & ((g["year"] - g["_prev_t"]) <= 2)
    g = g[keep & (g["_prev_y"] == 0)].copy()
    g["event"] = g[outkey].astype(int)
    covs = ["p_age", "p_male", "masld"] + HARM
    if year_fe:
        yd = pd.get_dummies(g["year"].astype(int), prefix="y", drop_first=True).astype(float)
        g = pd.concat([g, yd], axis=1)
        covs = covs + list(yd.columns)
    return g.dropna(subset=covs), covs


cox = []
for name, key in OUTs.items():
    for yfe in (False, True):
        g, covs = build(key, yfe)
        if len(g) < 200:
            continue
        if yfe:
            g["T"] = 1.0
            mm = CoxPHFitter(penalizer=0.01)
            mm.fit(g[["T", "event"] + covs + ["id"]], duration_col="T", event_col="event",
                   cluster_col="id", show_progress=False)
        else:
            g["stop"] = g.groupby("id").cumcount() + 1
            g["start"] = g["stop"] - 1
            mm = CoxTimeVaryingFitter()
            mm.fit(g[["id", "start", "stop", "event"] + covs], id_col="id", event_col="event",
                   start_col="start", stop_col="stop", show_progress=False)
        ss = mm.summary.loc["masld"]
        cox.append({"outcome_def": name, "yearFE": yfe, "n_risk": len(g),
                    "events": int(g["event"].sum()),
                    "HR": round(float(ss["exp(coef)"]), 4),
                    "lo": round(float(ss["exp(coef) lower 95%"]), 4),
                    "hi": round(float(ss["exp(coef) upper 95%"]), 4),
                    "p": float(ss["p"])})
        rl(f"  {name:20s} FE={int(yfe)} n={len(g):,} ev={int(g['event'].sum()):,} "
           f"HR={float(ss['exp(coef)']):.4f} ({float(ss['exp(coef) lower 95%']):.4f}–"
           f"{float(ss['exp(coef) upper 95%']):.4f}) P={float(ss['p']):.4g}")
pd.DataFrame(cox).to_csv(os.path.join(RES, "B31_definition_matched_cox.csv"), index=False,
                         encoding="utf-8-sig")

# ---------- C) 分歧层抽样清单 ----------
rl("\n=== C) 分歧层抽样清单（第 2 步核对用）===")
d["len"] = d["ecg_text"].fillna("").map(len)
d["n_seg"] = d["ecg_text"].fillna("").map(lambda t: len([x for x in t.replace("、", "。").split("。") if x.strip()]))
rng = np.random.default_rng(SEED)
picks = []


def take(df, k, stratum):
    df = df.copy()
    if len(df) > k:
        df = df.iloc[rng.choice(len(df), k, replace=False)]
    df["stratum"] = stratum
    return df


g23 = d[(d.year == 2023)]
g21 = d[(d.year == 2021)]
core = g23[(g23.v3_A == 1) & (g23.v3_B == 0)]
picks.append(take(core[core.n_seg <= 1], 40, "2023_A1B0_sparse(≤1段)"))
picks.append(take(core[core.n_seg >= 2], 20, "2023_A1B0_multi(≥2段)"))
picks.append(take(g23[(g23.v3_A == 1) & (g23.v3_B == 1)], 20, "2023_A1B1_agreed"))
picks.append(take(g21[(g21.v3_A == 1) & (g21.v3_B == 0)], 20, "2021_A1B0(cross-year ctrl)"))
picks.append(take(g23[(g23.v3_A == 0)], 20, "2023_A0_normal(neg ctrl)"))
S = pd.concat(picks, ignore_index=True)
S = S[["stratum", "id", "year", "len", "n_seg", "ecg_text", "v1_draft", "v1_A2",
       "v1_B", "v3_A", "v3_B"]].copy()
S.insert(0, "sample_no", [f"B31_{i+1:03d}" for i in range(len(S))])
for c2 in ["manual_any_abnormal", "manual_reason", "adjudicator_note"]:
    S[c2] = ""
os.makedirs(os.path.join(ROOT, "data"), exist_ok=True)
S.to_csv(os.path.join(ROOT, "data", "B31_divergent_stratum_samples.csv"), index=False,
         encoding="utf-8-sig")
S.to_excel(os.path.join(ROOT, "data", "B31_divergent_stratum_samples.xlsx"), index=False)
rl(f"  抽样 {len(S)} 例：" + "；".join(f"{k}={v}" for k, v in S.stratum.value_counts().items()))
rl(f"  2023 分歧核（v3_A=1 & v3_B=0）总量 {len(core):,} / 2023 全部 {len(g23):,} = {len(core)/len(g23)*100:.1f}%")
rl(f"  其中 ≤1 段（稀疏）占比 {100*len(core[core.n_seg<=1])/len(core):.1f}%；"
   f"分歧核长度中位 {core.len.median():.0f}、全体 2023 长度中位 {g23.len.median():.0f}")
rl("  -> data/B31_divergent_stratum_samples.csv/.xlsx（含人工判读空列）")

with open(os.path.join(RES, "B31_definition_alignment.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
rl(f"\n总耗时 {time.time() - t0:.0f}s；===== B31 完成 =====")
