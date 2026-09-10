# -*- coding: utf-8 -*-
"""05_downsample_gold_300.py —— 金标准减负：echo/abdus 600 -> 300（方案A，2026-09-02）
依据：Flack 1988 / Bujang & Baharum 2017（α=0.05, power=80%），κ≈0.80 时
      n=300 可同时支撑验收判定（CI半宽≈±0.06）与 7 层年份分层 κ 曲线；
      ECG_H 570 为幻影信号主案例域，全量保留。
方法：对 600 份母体做嵌套分层子抽样（seed=42，保留原 sample_id 可追溯）：
  - echo_PG:    规则预分类 150/75/75（abnormal/normal/normal_variant）
  - abdus_PG:   规则阳性/阴性 各150
  - abdus_H:    每年30（210）+ fatty_rule阳性补足90
输出：data/gold_echo_PG_300.csv、gold_abdus_PG_300.csv、gold_abdus_H_300.csv
用法：python code/05_downsample_gold_300.py
"""
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DATA = os.path.join(BASE, "data")
SEED = 42
sys.path.insert(0, os.path.join(BASE, "code"))
from main import extract_echo, extract_abd, norm  # noqa: E402


def load(name):
    p = os.path.join(DATA, name)
    d = pd.read_csv(p, encoding="utf-8-sig", dtype=str)
    print(f"[母体] {name}: {len(d)} 份")
    return d


# ---------- ① echo_PG 600 -> 300（150/75/75） ----------
d = load("gold_echo_PG.csv")
d["label_rule"] = d["text"].map(lambda t: extract_echo(norm(t))["label"])
print("  规则预分类分布:", d["label_rule"].value_counts().to_dict())
quota = {"abnormal": 150, "normal": 75, "normal_variant": 75}
parts = []
for lab, g in d.groupby("label_rule"):
    n = min(quota.get(lab, 0), len(g))
    if n:
        parts.append(g.sample(n, random_state=SEED))
sub = pd.concat(parts).drop_duplicates(subset=["sample_id"])
sub = sub.drop(columns=["label_rule"])
out = os.path.join(DATA, "gold_echo_PG_300.csv")
sub.to_csv(out, index=False, encoding="utf-8-sig")
print(f"-> gold_echo_PG_300.csv: {len(sub)} 份")

# ---------- ② abdus_PG 600 -> 300（阳性/阴性 各150） ----------
d = load("gold_abdus_PG.csv")
d["fatty_rule"] = d["text"].map(lambda t: int(extract_abd(norm(t))["us_fatty"]))
print("  规则预分类分布:", d["fatty_rule"].value_counts().to_dict())
parts = [g.sample(min(150, len(g)), random_state=SEED) for _, g in d.groupby("fatty_rule")]
sub = pd.concat(parts).drop_duplicates(subset=["sample_id"]).drop(columns=["fatty_rule"])
out = os.path.join(DATA, "gold_abdus_PG_300.csv")
sub.to_csv(out, index=False, encoding="utf-8-sig")
print(f"-> gold_abdus_PG_300.csv: {len(sub)} 份")

# ---------- ③ abdus_H 600 -> 300（每年30 + 阳性补足90） ----------
d = load("gold_abdus_H.csv")
d["fatty_rule"] = d["fatty_rule"].astype(int)
parts = [g.sample(min(30, len(g)), random_state=SEED) for _, g in d.groupby("year")]
year_pick = pd.concat(parts)
need = 300 - len(year_pick)
rest = d[~d["sample_id"].isin(year_pick["sample_id"])]
extra = rest.loc[rest["fatty_rule"] == 1].sample(min(max(need, 0), len(rest)), random_state=SEED)
sub = pd.concat([year_pick, extra]).drop_duplicates(subset=["sample_id"]).drop(columns=["fatty_rule"])
out = os.path.join(DATA, "gold_abdus_H_300.csv")
sub.to_csv(out, index=False, encoding="utf-8-sig")
print(f"-> gold_abdus_H_300.csv: {len(sub)} 份（年度 {sub['year'].value_counts().sort_index().to_dict()}）")

print("完成：三域 300 份子集已生成（600 份母体原样保留，嵌套可追溯）")
