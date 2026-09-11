# -*- coding: utf-8 -*-
"""42_confirm_si_note3_exemplars.py —— 确认 SI Note 3 示例文本的溯源与标注终值
在终版工作簿 ECG_H 中定位 5 条预选示例的 sample_id，输出其标注终值（ecg_normal/other/unreadable），
用于 Supplementary Note 3 定稿与可追溯性声明。
"""
import os

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WB = os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx")
TARGETS = [
    "1.窦性心律\n2.完全性右束支阻滞\n3.左心室高电压",
    "1.窦性心律\n2.T波改变（TV1>TV5)",
    "心电图1、窦性心律 2、T波低平。",
    "1、窦性心律 2、T波低平倒置、完全性右束支传导阻滞。",
    "肝胆脾双肾声像图未见明显异常",
]

e = pd.read_excel(WB, sheet_name="ECG_H", dtype=str).set_index("sample_id")
arb = pd.read_csv(os.path.join(ROOT, "results", "arbitration_decisions.csv"), dtype=str)
arb_map = {(r["sample_id"], r["variable"]): r["final"]
           for _, r in arb.iterrows() if r["sheet"] == "ECG_H"}


def final_value(sid, var):
    a1, a2 = e.at[sid, f"A1_{var}"], e.at[sid, f"A2_{var}"]
    if pd.notna(a1) and a1 == a2:
        return f"consensus={a1}"
    got = arb_map.get((sid, var))
    return f"A1={a1}/A2={a2}; arb={got if got is not None else 'none'}"


found = []
for t in TARGETS:
    hit = [sid for sid in e.index if str(e.at[sid, "text"]).strip() == t.strip()]
    if not hit:
        print(f"[NOT FOUND] {t!r}")
        continue
    sid = hit[0]
    year = str(e.at[sid, "year"])[:4]
    labs = {v: final_value(sid, v) for v in ["ecg_normal", "ecg_other", "ecg_unreadable"]}
    # 脱敏检查：文本不得含长数字串（>5位）或字母数字混合 ID 形态
    import re
    pii = re.findall(r"\d{6,}|[A-Za-z]\d{5,}", t)
    found.append((sid, year, t, labs, pii))
    print(f"{sid} | {year} | PII-check={'CLEAN' if not pii else pii} | {t!r}")
    for k, v in labs.items():
        print(f"    {k}: {v}")
