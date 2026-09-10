# -*- coding: utf-8 -*-
"""02_make_annotation_workbook.py —— 生成标注工作簿（xlsx；openpyxl缺失时退化为CSV）
每个域一个sheet：sample_id/源信息/文本/A1_列(按codebook)/A2_列/flag_note/仲裁列
"""
import os
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
DATA = os.path.join(BASE, "data")

ECG_COLS = ["ecg_normal", "ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock", "ecg_bbb",
            "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave_mi", "ecg_other", "ecg_unreadable"]
ECHO_COLS = ["echo_normal", "echo_variant", "echo_lvh", "echo_la_dilate", "ef_value",
             "ef_abnormal", "reflux_grade", "echo_rhythm", "echo_unreadable"]
ABD_COLS = ["us_fatty", "us_fatty_degree", "us_hepatic_other", "us_gallstone",
            "us_kidney_cyst", "us_unreadable", "main_discrepant"]

def build(df, cols, text_col="text", meta_cols=("sample_id",)):
    out = df[[c for c in meta_cols if c in df.columns] + [text_col]].copy()
    for who in ("A1", "A2"):
        for c in cols:
            out[f"{who}_{c}"] = ""
    out["flag"] = ""
    out["note"] = ""
    out["arbitration"] = ""
    return out

def load_gold(path, idcol="sample_id"):
    p = os.path.join(DATA, path)
    if not os.path.exists(p):
        print(f"[缺文件，跳过] {p}")
        return None
    d = pd.read_csv(p, encoding="utf-8-sig", dtype=str)
    d["sample_id"] = d[idcol]
    return d

sheets = {}
d1 = load_gold("gold_ecg_H.csv")
if d1 is not None: sheets["ECG_H"] = build(d1, ECG_COLS)
d2 = load_gold("gold_echo_PG_300.csv")
if d2 is not None: sheets["ECHO_PG"] = build(d2, ECHO_COLS)
d3 = load_gold("gold_abdus_PG_300.csv")
if d3 is not None: sheets["ABDUS_PG"] = build(d3, ABD_COLS)
d4 = load_gold("gold_abdus_H_300.csv")
if d4 is not None: sheets["ABDUS_H"] = build(d4, ABD_COLS)

xlsx = os.path.join(DATA, "金标准标注工作簿.xlsx")
try:
    with pd.ExcelWriter(xlsx, engine="openpyxl") as w:
        for name, d in sheets.items():
            d.to_excel(w, sheet_name=name, index=False)
    print(f"工作簿 -> {xlsx}（sheets: {list(sheets)}）")
except Exception as e:
    print(f"openpyxl不可用({e})，改写CSV：")
    for name, d in sheets.items():
        p = os.path.join(DATA, f"标注表_{name}.csv")
        d.to_csv(p, index=False, encoding="utf-8-sig")
        print(f"  {p}")
