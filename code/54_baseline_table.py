# -*- coding: utf-8 -*-
"""54_baseline_table.py —— Supplementary Table S8：基线特征（R12-F2，STROBE 14）
口径：每名参与者**首个纳入波**（2018–2024）的横截面特征；连续变量 median (IQR)（附非缺失 n），
分类变量 n (%)。仅输出聚合统计（Data availability "aggregate year-stratified statistics" 口径），
无个体级数据。来源列与 00_link/01_build 的 H_analysis_long 一致。
输出: results/tableS8_baseline.csv（列：Characteristic | n | Value）
用法: python code/54_baseline_table.py
"""
import os
import sys

import numpy as np
import pandas as pd

H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
RES = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")

CONT = [  # (列名, 展示名, 单位)
    ("age", "Age at baseline, years", "years"),
    ("bmi", "Body mass index, kg/m²", ""),
    ("waist", "Waist circumference, cm", ""),
    ("sbp", "Systolic blood pressure, mmHg", ""),
    ("dbp", "Diastolic blood pressure, mmHg", ""),
    ("fpg", "Fasting plasma glucose, mmol/L", ""),
    ("hba1c", "HbA1c, %", ""),
    ("tg", "Triglycerides, mmol/L", ""),
    ("hdl", "HDL cholesterol, mmol/L", ""),
    ("crea", "Creatinine, μmol/L", ""),
    ("egfr", "eGFR (CKD-EPI 2021), mL/min/1.73 m²", ""),
    ("ua", "Uric acid, μmol/L", ""),
    ("plt", "Platelet count, ×10⁹/L", ""),
    ("neut", "Neutrophil count, ×10⁹/L", ""),
    ("lymph", "Lymphocyte count, ×10⁹/L", ""),
    ("sii", "Systemic immune-inflammation index, ×10⁹/L", ""),
]
CAT = [  # (列名, 展示名, 阳性值)
    ("sex_male", "Women", 0),
    ("masld", "MASLD (ultrasound fatty liver + ≥1 cardiometabolic criterion)", 1),
    ("proteinuria", "Proteinuria (urine protein ≥1+)", 1),
    ("htn_screen", "Screening-defined hypertension (SBP ≥140 or DBP ≥90 mmHg)", 1),
    ("dm_screen", "Screening-defined diabetes (FPG ≥7.0 mmol/L or HbA1c ≥6.5%)", 1),
    ("central_obese", "Central obesity (waist ≥90 cm men / ≥85 cm women)", 1),
    ("hyperuricemia", "Hyperuricemia (uric acid >420 μmol/L men / >360 μmol/L women)", 1),
]


def med_iqr(s):
    s = s.dropna()
    if len(s) == 0:
        return None
    q1, q3 = s.quantile([0.25, 0.75])
    digits = 1 if s.abs().max() < 500 else 0
    return f"{s.median():.{digits}f} ({q1:.{digits}f}–{q3:.{digits}f})", int(len(s))


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    df = pd.read_csv(H3 + "/data/processed/H_analysis_long.csv", encoding="utf-8-sig",
                     dtype={"id": str}, low_memory=False)
    df = df.sort_values(["id", "year"]).reset_index(drop=True)
    base = df.groupby("id", as_index=False).first()  # 每人首个纳入波
    rows = [("Participants (persons)", str(len(base)), "—"),
            ("Visit-records", str(len(df)), "—"),
            ("Visits per person, median (IQR)",
             str(len(base)),
             f"{df.groupby('id').size().median():.0f} "
             f"({df.groupby('id').size().quantile(0.25):.0f}–{df.groupby('id').size().quantile(0.75):.0f})")]
    for col, name, _ in CONT:
        r = med_iqr(base[col])
        if r:
            rows.append((name, str(r[1]), r[0]))
    for col, name, pos in CAT:
        s = base[col].dropna()
        npos = int((s.astype(float) == pos).sum())
        pct = npos / len(s) * 100 if len(s) else 0
        rows.append((name, str(int(len(s))), f"{npos} ({pct:.1f}%)"))
    out = pd.DataFrame(rows, columns=["Characteristic", "n", "Value"])
    out.to_csv(os.path.join(RES, "tableS8_baseline.csv"), index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))
    print("-> results/tableS8_baseline.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
