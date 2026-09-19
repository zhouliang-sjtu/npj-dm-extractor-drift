# -*- coding: utf-8 -*-
"""01c_sample_gold_abdus_H.py —— ④H社区腹超金标准抽样（需先运行01b）
设计：每年随机50（350）＋fatty=1额外补250 → 共600；seed=42
"""
import os
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
SRC = os.environ.get("H_US_TEXT", "")  # institution-side source table (not redistributed)
OUT = os.path.join(BASE, "data", "gold_abdus_H.csv")
SEED = 42

df = pd.read_csv(SRC, encoding="utf-8-sig", dtype={"id": str})
df["text"] = (df["us_text"].astype(str) + " " + df["main_text"].astype(str)).str.slice(0, 600)
df["fatty"] = df["text"].str.contains(r"脂肪肝|细密|远场回声衰减|回声衰减", regex=True).astype(int)

parts = []
for y, g in df.groupby("year"):
    parts.append(g.sample(min(50, len(g)), random_state=SEED))
year_pick = pd.concat(parts)
need = 600 - len(year_pick)
extra = df.loc[df["fatty"] == 1].sample(min(need, (df["fatty"] == 1).sum()), random_state=SEED)
gold = pd.concat([year_pick, extra]).drop_duplicates(subset=["id", "year"])
gold_out = gold[["year", "id", "text"]].copy()
gold_out["fatty_rule"] = gold["fatty"]
gold_out.insert(0, "sample_id", ["ABDH_{:04d}".format(i + 1) for i in range(len(gold_out))])
gold_out.to_csv(OUT, index=False, encoding="utf-8-sig")
print(f"④ H社区腹超金标准: {len(gold_out)} 份（年度 {gold_out['year'].value_counts().sort_index().to_dict()}；fatty_rule=1: {gold_out['fatty_rule'].sum()}）")
