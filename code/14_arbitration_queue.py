# -*- coding: utf-8 -*-
"""14_arbitration_queue.py —— M1e 仲裁队列生成
规则：总体 κ<0.80 或 分年份层 κ<0.80 或 任一类别 F1<0.90（A1-vs-A2 代理口径）的变量，
     导出全部 A1≠A2 不一致个案；另附 flag=1 待复核个案。
用法：python code/14_arbitration_queue.py
输出：results/arbitration_queue.csv（kind=discordant|flag）
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "10_expert-consultation", "recycle", "金标准标注工作簿.xlsx")
RES = os.path.join(ROOT, "results")

SHEET_COLS = {
    "ECG_H": ["ecg_normal", "ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock", "ecg_bbb",
              "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave_mi", "ecg_other", "ecg_unreadable"],
    "ECHO_PG": ["echo_normal", "echo_variant", "echo_lvh", "echo_la_dilate", "ef_abnormal",
                "echo_rhythm", "echo_unreadable", "reflux_grade"],
    "ABDUS_PG": ["us_fatty", "us_fatty_degree", "us_hepatic_other", "us_gallstone",
                 "us_kidney_cyst", "us_unreadable", "main_discrepant"],
    "ABDUS_H": ["us_fatty", "us_fatty_degree", "us_hepatic_other", "us_gallstone",
                "us_kidney_cyst", "us_unreadable", "main_discrepant"],
}


def blank(s):
    return s.isna() | (s.astype(str).str.strip() == "")


def collect_fail_vars():
    """从 agreement_*.csv 找未达标变量 -> {sheet: set(variable)}"""
    fails = {}
    for sheet in SHEET_COLS:
        p = os.path.join(RES, f"agreement_{sheet}.csv")
        if not os.path.exists(p):
            continue
        a = pd.read_csv(p)
        bad = set()
        for r in a.itertuples():
            if "@" in r.variable:
                if r.cohen_kappa < 0.80:
                    bad.add(r.variable.split("@")[0])
            else:
                if r.cohen_kappa < 0.80:
                    bad.add(r.variable)
                f1s = [(c, v) for c, v in a.columns.to_series().items()]
        # F1 检查（仅总体行）
        for r in a[~a["variable"].str.contains("@")].itertuples():
            for c in a.columns:
                if c.startswith("F1_") and pd.notna(getattr(r, c)) and getattr(r, c) < 0.90:
                    bad.add(r.variable)
        if bad:
            fails[sheet] = bad
    return fails


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    fails = collect_fail_vars()
    print("仲裁触发变量：", fails or "无")
    xl = pd.ExcelFile(BOOK)
    rows = []
    for sheet, bad in fails.items():
        df = xl.parse(sheet, dtype=str)
        tcol = "year" if "year" in df.columns else "exam_date"
        for var in sorted(bad & set(SHEET_COLS[sheet])):
            a = df["A1_" + var].astype(str).str.strip()
            b = df["A2_" + var].astype(str).str.strip()
            dis = (a != b) & ~blank(df["A1_" + var]) & ~blank(df["A2_" + var])
            for i in df.index[dis]:
                rows.append(dict(kind="discordant", sheet=sheet, variable=var,
                                 sample_id=df.at[i, "sample_id"], time=df.at[i, tcol],
                                 A1=a[i], A2=b[i], flag=df.at[i, "flag"], note=df.at[i, "note"],
                                 text=df.at[i, "text"]))
    # flag=1 待复核
    for sheet in SHEET_COLS:
        df = xl.parse(sheet, dtype=str)
        tcol = "year" if "year" in df.columns else "exam_date"
        fl = df["flag"].astype(str).str.strip() == "1"
        for i in df.index[fl]:
            rows.append(dict(kind="flag", sheet=sheet, variable="", sample_id=df.at[i, "sample_id"],
                             time=df.at[i, tcol], A1="", A2="", flag="1", note=df.at[i, "note"],
                             text=df.at[i, "text"]))
    out = pd.DataFrame(rows, columns=["kind", "sheet", "variable", "sample_id", "time",
                                      "A1", "A2", "flag", "note", "text"])
    p = os.path.join(RES, "arbitration_queue.csv")
    out.to_csv(p, index=False, encoding="utf-8-sig")
    dis = out[out["kind"] == "discordant"]
    print(dis.groupby(["sheet", "variable"]).size().to_string())
    print(f"不一致个案 {len(dis)} 条 + flag待复核 {len(out) - len(dis)} 条 -> {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
