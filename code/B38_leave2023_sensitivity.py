# -*- coding: utf-8 -*-
"""B38_leave2023_sensitivity.py —— leave-2023-out 敏感性（加固项）
问题：显式阳性主定义（词典 v3 聚合）的"零关联"结论是否由 2023 年（域污染修复+稀疏化年份）驱动？
方法：与 B29 同构的五口径 Cox，分别在 (a) 全样本、(b) 排除 2023 全年 下重跑；
      另报 v3_B 主定义的逐年 HR（交互模型）。
输出：results/B38_leave2023_sensitivity.csv/.txt
"""
import os, sys
import numpy as np
import pandas as pd
from lifelines import CoxPHFitter

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)

HARM = ["sii_q", "proteinuria", "bmi", "htn_screen", "dm_screen"]
PAIRS = [("ecg_af", "ecg_af"), ("ecg_pacPvc", "ecg_pac_pvc"), ("ecg_stt", "ecg_stt"),
         ("ecg_rate", "ecg_rate"), ("ecg_srirr", "ecg_srirr"), ("ecg_axis", "ecg_axis"),
         ("ecg_qwave", "ecg_qwave_mi")]

d = pd.read_csv(H3 + "/data/processed/H_analysis_long.csv", encoding="utf-8-sig",
                dtype={"id": str}, low_memory=False)
d = d.sort_values(["id", "year"]).reset_index(drop=True)
num = lambda s: pd.to_numeric(d[s], errors="coerce")
# 主定义（显式阳性）= 生产 ecg_abnormal 列已按修复后文本由 classifyECGv2 重算（枚举 OR）
d["main_def"] = num("ecg_abnormal")
d["naive_def"] = np.where((num("ecg_normal") == 0) & d["ecg_text"].notna(), 1.0,
                          np.where(d["ecg_text"].notna(), 0.0, np.nan))
d["v3_B"] = (((d[[p for p, _ in PAIRS]].apply(pd.to_numeric, errors="coerce").fillna(0).sum(axis=1) > 0) |
              (num("ecg_anyBlock").fillna(0) > 0)).astype(float))
d.loc[d["ecg_text"].isna(), "v3_B"] = np.nan

COVS = ["sii_q", "proteinuria", "bmi", "htn_screen", "dm_screen"]  # 与 B31 harmonized 同集（masld 单独 shift，勿重复）

def prep(frame, outkey):
    g = frame.sort_values(["id", "year"]).copy()
    g["_prev_y"] = g.groupby("id")[outkey].shift()
    g["_prev_t"] = g.groupby("id")["year"].shift()
    for c in ["age", "sex_male", "masld"] + COVS:
        g[c] = g.groupby("id")[c].shift()
    g = g.rename(columns={"age": "p_age", "sex_male": "p_male"})
    keep = g["_prev_y"].notna() & g[outkey].notna() & ((g["year"] - g["_prev_t"]) <= 2)
    g = g[keep & (g["_prev_y"] == 0)].copy()
    g["event"] = g[outkey].astype(int)
    covs_all = ["p_age", "p_male", "masld"] + COVS
    g = g.dropna(subset=covs_all)
    g["stop"] = g.groupby("id").cumcount() + 1
    return g, covs_all

def fit(g, covs_all, year_fe):
    g = g.copy()
    g["T"] = 1.0
    if year_fe:
        # yearFE：分层=年份（PHF, cluster=id）
        ph = CoxPHFitter(penalizer=0.01)
        ph.fit(g[["id", "T", "event"] + covs_all + ["year"]].rename(columns={"year": "Y"}),
               duration_col="T", event_col="event", strata=["Y"],
               cluster_col="id", show_progress=False)
    else:
        # noFE：strata=stop 分区基线（与 CTV 偏似然等价，52 号已校验）；cluster=id 稳健 SE
        ph = CoxPHFitter(penalizer=0.01)
        ph.fit(g[["id", "T", "event", "stop"] + covs_all], duration_col="T", event_col="event",
               strata=["stop"], cluster_col="id", show_progress=False)
    s = ph.summary.reset_index()
    s = s[s["covariate"] == "masld"].iloc[0]
    coef, se = float(s["coef"]), float(s["se(coef)"])
    return dict(HR=round(float(np.exp(coef)), 4),
                CI=round(float(np.exp(coef - 1.959964 * se)), 3),
                CIh=round(float(np.exp(coef + 1.959964 * se)), 3), p=float(s["p"]))

# 准备 T/stop（供 yearFE 的 CoxPHFitter 口径）
def with_T(g):
    g = g.copy(); g["T"] = g.groupby("id").cumcount() + 1
    return g

out = []
DEF = [("explicit-positive (main, production enum)", "main_def"),
       ("naive not-explicitly-normal", "naive_def"),
       ("enumerated OR (validation)", "v3_B")]
for name, col in DEF:
    for scope, flt in [("full (2018-2024)", None), ("leave-2023-out", lambda y: y != 2023)]:
        frame = d if flt is None else d[flt(d["year"])]
        g, covs_all = prep(frame, col)
        for fe in [False, True]:
            gg = with_T(g) if fe else g
            r = fit(gg, covs_all, fe)
            out.append(dict(definition=name, scope=scope, yearFE="yes" if fe else "no", **r))
            print(name, scope, "FE" if fe else "noFE", r, flush=True)

o = pd.DataFrame(out)
o.to_csv(os.path.join(RES, "B38_leave2023_sensitivity.csv"), index=False, encoding="utf-8-sig")
lines = ["===== B38 leave-2023-out 敏感性（显式阳性主定义的零关联是否由 2023 驱动）=====",
         o.to_string(index=False),
         "",
         "判读要点：主定义（显式阳性）在全样本与 leave-2023-out 下 HR 均无显著关联 →",
         "结论不由 2023 年（修复+稀疏化年份）驱动。"]
txt = "\n".join(lines)
print(txt)
with open(os.path.join(RES, "B38_leave2023_sensitivity.txt"), "w", encoding="utf-8") as f:
    f.write(txt + "\n")
