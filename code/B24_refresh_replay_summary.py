# -*- coding: utf-8 -*-
"""B24_refresh_replay_summary.py — 刷新 replay_summary.csv 的 REAL_* 参照行

背景: 35_phantom_differential_replay.py 原将真实估计参照值（REAL_v1 / REAL_v3）
      硬编码在脚本内（0.9804 / 1.1196 等）。数据修正后这些常量已过期，导致
      replay_summary.csv 与权威表 phantom_specs_table.csv 内部不一致。
      脚本已改为从 phantom_specs_table.csv 读取；本脚本据同口径刷新既有汇总文件的
      REAL_* 两行（重放臂各行不动），使发布件与脚本行为一致。
"""
import os
import pandas as pd

P1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
RES = os.path.join(P1, "results")
rep = []

def rep_line(s=""):
    print(s, flush=True)
    rep.append(str(s))

ps = pd.read_csv(os.path.join(RES, "phantom_specs_table.csv"), encoding="utf-8-sig")
ps = ps.set_index("spec")["HR"].astype(float)
summ = pd.read_csv(os.path.join(RES, "replay_summary.csv"), encoding="utf-8-sig")

MAP = {"REAL_v1": ("harmonized_v1", "harmonized_v1+yearFE"),
       "REAL_v3": ("harmonized_v3", "harmonized_v3+yearFE")}
for i, r in summ.iterrows():
    if r["arm"] in MAP:
        no, fe = MAP[r["arm"]]
        old = (r["HR_noFE"], r["HR_yearFE"])
        summ.at[i, "HR_noFE"] = ps[no]
        summ.at[i, "HR_yearFE"] = ps[fe]
        rep_line(f"  {r['arm']}: HR_noFE {old[0]} → {ps[no]:.4f}；"
                 f"HR_yearFE {old[1]} → {ps[fe]:.4f}")

summ.to_csv(os.path.join(RES, "replay_summary.csv"), index=False, encoding="utf-8-sig")
rep_line("\n=== 刷新后 replay_summary.csv ===")
rep_line(summ.to_string(index=False))

with open(os.path.join(RES, "B24_replay_summary_refresh.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
print("\n===== B24 完成 =====")
