# -*- coding: utf-8 -*-
"""04_agreement_stats.py —— 标注一致性统计（Cohen's κ / Gwet AC1 / F1 / 分年份分层）
输入：标注完成的 xlsx（A1_*/A2_* 列已填）
用法：python 04_agreement_stats.py --file data/金标准标注工作簿.xlsx --sheet ECHO_PG
输出：results/agreement_<sheet>.csv + 控制台报告
"""
import argparse
import os

import numpy as np
import pandas as pd

def fleiss_cohen_kappa(a, b):
    """二/多分类 Cohen's κ（a,b为标签序列）"""
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = np.mean([x == y for x, y in zip(a, b)])
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in labels)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po

def gwet_ac1(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = np.mean([x == y for x, y in zip(a, b)])
    pi = [(sum(1 for x in a if x == L) + sum(1 for y in b if y == L)) / (2 * n) for L in labels]
    # Gwet (2008): pe(γ) = Σ_k π_k(1-π_k) / (q-1)，q=类别数
    pe = sum(p * (1 - p) for p in pi) / (len(labels) - 1) if len(labels) > 1 else 0
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po

def f1_per_class(a, b, cls):
    tp = sum(1 for x, y in zip(a, b) if x == cls and y == cls)
    fp = sum(1 for x, y in zip(a, b) if x != cls and y == cls)
    fn = sum(1 for x, y in zip(a, b) if x == cls and y != cls)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return prec, rec, f1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True)
    ap.add_argument("--sheet", required=True)
    ap.add_argument("--cols", required=True, help="逗号分隔的标签列名（不含A1_/A2_前缀），如 ecg_normal,ecg_af")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    df = pd.read_excel(args.file, sheet_name=args.sheet, dtype=str)
    rows = []
    for col in args.cols.split(","):
        # 空单元格 NaN→astype(str) 会变 "nan" 字符串，须一并置空，否则被当作标签计入 κ/F1
        a = (df["A1_" + col]).astype(str).str.strip().replace({"": np.nan, "nan": np.nan, "None": np.nan})
        b = (df["A2_" + col]).astype(str).str.strip().replace({"": np.nan, "nan": np.nan, "None": np.nan})
        d = pd.DataFrame({"a": a, "b": b}).dropna()
        if len(d) < 20:
            continue
        k, po = fleiss_cohen_kappa(d["a"].tolist(), d["b"].tolist())
        ac1, _ = gwet_ac1(d["a"].tolist(), d["b"].tolist())
        row = {"variable": col, "n": len(d), "raw_agreement": round(po, 3),
               "cohen_kappa": round(k, 3), "gwet_ac1": round(ac1, 3)}
        for cls in sorted(set(d["a"]) | set(d["b"])):
            p, r, f = f1_per_class(d["a"].tolist(), d["b"].tolist(), cls)
            row[f"prec_{cls}"] = round(p, 3); row[f"rec_{cls}"] = round(r, 3); row[f"F1_{cls}"] = round(f, 3)
        rows.append(row)
        # 年份分层（若存在year列）
        if "year" in df.columns:
            dd = pd.DataFrame({"a": a, "b": b, "y": df.loc[d.index, "year"].astype(str)})
            for y, g in dd.groupby("y"):
                if len(g) >= 15:
                    kk, _ = fleiss_cohen_kappa(g["a"].tolist(), g["b"].tolist())
                    rows.append({"variable": f"{col}@{y}", "n": len(g), "cohen_kappa": round(kk, 3)})
    out = pd.DataFrame(rows)
    p = args.out or os.path.join(os.path.dirname(args.file), f"agreement_{args.sheet}.csv")
    out.to_csv(p, index=False, encoding="utf-8-sig")
    gate_k = out[(out["variable"].str.contains("@") == False) & (out["cohen_kappa"] < 0.80)]
    print(out.to_string(index=False))
    print(f"\n验收门槛 κ≥0.80：{'【未通过】变量: ' + ', '.join(gate_k['variable']) if len(gate_k) else '【通过】全部变量达标'}")
    print(f"输出 -> {p}")

if __name__ == "__main__":
    main()
