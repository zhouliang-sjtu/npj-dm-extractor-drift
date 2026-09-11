# -*- coding: utf-8 -*-
"""22_m2c_qc.py —— M2c 跑批收尾 QC + 对冻结金标准的一致性预览
输入：data/llm_echo300_v21__{model}.csv ×3；data/gold_annotation_workbook_final.xlsx（ECHO_PG）；
      results/round2_final_resolution.csv（lvh/la_dilate 终值解析）
QC：JSON 解析率、ERROR 数、枚举合法性（label/reflux_grade/二值列/ef数值）
预览：consensus 终值（分歧行剔除）上各模型的 raw agreement 与 Cohen's κ（lvh/la_dilate/echo_normal/ef_abnormal/reflux_grade）
输出：results/m2c_qc.csv + 控制台报告
用法：python code/22_m2c_qc.py
"""
import json
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS = {"qwen2.5:14b": "llm_echo300_v21__qwen2.5_14b.csv",
          "qwen2.5:7b": "llm_echo300_v21__qwen2.5_7b.csv",
          "glm4:9b": "llm_echo300_v21__glm4_9b.csv"}
LABEL_ENUM = {"normal", "normal_variant", "abnormal", "unreadable"}
REFLUX_ENUM = {"none", "trace_mild", "moderate", "severe"}


def kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in labels)
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0, po


def parse_llm(raw):
    """解析 llm_raw：严格 json → 花括号恢复 → 失败返回 None"""
    try:
        return json.loads(raw)
    except Exception:
        if "{" in raw and "}" in raw:
            try:
                return json.loads(raw[raw.index("{"): raw.rindex("}") + 1])
            except Exception:
                return None
        return None


def gold_finals():
    e = pd.read_excel(os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx"),
                      sheet_name="ECHO_PG", dtype=str)
    res = pd.read_csv(os.path.join(ROOT, "results", "round2_final_resolution.csv"), dtype=str)
    fin = {v: res[res.variable == v].set_index("sample_id")["final"]
           for v in ["echo_lvh", "echo_la_dilate"]}
    g = {}
    for i in e.index:
        sid = e.at[i, "sample_id"]
        row = {"echo_lvh": fin["echo_lvh"].get(sid, ""),
               "echo_la_dilate": fin["echo_la_dilate"].get(sid, "")}
        for var in ["echo_normal", "echo_variant", "reflux_grade", "ef_abnormal"]:
            a1, a2, arb = e.at[i, "A1_" + var], e.at[i, "A2_" + var], e.at[i, "arbitration"]
            row[var] = a1 if (pd.notna(a1) and a1 == a2) else \
                (str(arb).strip() if pd.notna(arb) and str(arb).strip() and var != "echo_normal" else "")
        ef = pd.to_numeric(pd.Series([e.at[i, "A1_ef_value"]]), errors="coerce").iloc[0]
        if pd.isna(row["ef_abnormal"]) and pd.notna(ef):
            row["ef_abnormal"] = "1" if ef < 50 else "0"
        g[sid] = row
    return g


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    g = gold_finals()
    rows, agree_rows = [], []
    for model, fn in MODELS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        n_err = int((d["llm_raw"] == "ERROR").sum())
        parsed = [None if r == "ERROR" else parse_llm(r) for r in d["llm_raw"]]
        n_json = sum(p is not None for p in parsed)
        bad_label = sum(p is not None and str(p.get("label")) not in LABEL_ENUM for p in parsed)
        bad_reflux = sum(p is not None and str(p.get("reflux_grade")) not in REFLUX_ENUM for p in parsed)
        bad_bin = sum(p is not None and any(str(p.get(k)) not in {"0", "1", "None"}
                                            for k in ["lvh", "la_dilate", "rhythm"]) for p in parsed)
        bad_ef = sum(p is not None and p.get("ef") is not None
                     and not isinstance(p.get("ef"), (int, float)) for p in parsed)
        rows.append(dict(model=model, n=len(d), json_ok=n_json, json_rate=round(n_json / len(d), 4),
                         error=n_err, bad_label=bad_label, bad_reflux=bad_reflux,
                         bad_binary=bad_bin, bad_ef=bad_ef))
        # 一致性预览（consensus 终值，分歧/待定行剔除）
        # 标签映射（依手册口径）：normal→echo_normal=1/echo_variant=0；normal_variant→echo_normal=0/echo_variant=1；
        # abnormal→两者皆0；unreadable→echo_unreadable=1（不入本预览）
        for var, get in [("echo_lvh", lambda p: str(p.get("lvh"))),
                         ("echo_la_dilate", lambda p: str(p.get("la_dilate"))),
                         ("echo_normal", lambda p: "1" if str(p.get("label")) == "normal" else "0"),
                         ("echo_variant", lambda p: "1" if str(p.get("label")) == "normal_variant" else "0"),
                         ("ef_abnormal", lambda p: (lambda v: "" if v is None else
                                                    ("1" if float(v) < 50 else "0"))(p.get("ef"))),
                         ("reflux_grade", lambda p: str(p.get("reflux_grade")))]:
            pairs = [(str(g[r.sample_id][var]), get(p))
                     for r, p in zip(d.itertuples(index=False), parsed)
                     if p is not None and g.get(r.sample_id, {}).get(var) not in ("", None, np.nan)
                     and str(g[r.sample_id][var]) != ""]
            if len(pairs) < 30:
                continue
            a = [x for x, _ in pairs]
            b = [y for _, y in pairs if y != ""]
            a = [x for x, y in pairs if y != ""]
            k, po = kappa(a, b)
            agree_rows.append(dict(model=model, variable=var, n=len(a),
                                   raw_agreement=round(po, 3), cohen_kappa=round(k, 3)))
    qc = pd.DataFrame(rows)
    ag = pd.DataFrame(agree_rows)
    qc.to_csv(os.path.join(ROOT, "results", "m2c_qc.csv"), index=False, encoding="utf-8-sig")
    ag.to_csv(os.path.join(ROOT, "results", "m2c_agreement_preview.csv"), index=False,
              encoding="utf-8-sig")
    print("== QC ==")
    print(qc.to_string(index=False))
    print("\n== 一致性预览（consensus 终值）==")
    print(ag.to_string(index=False))
    gate = ag[(ag.variable.isin(["echo_lvh", "echo_la_dilate"])) & (ag.cohen_kappa < 0.80)]
    print("\n【M2d 门槛预览】lvh/la_dilate κ<0.80 的模型：",
          gate["model"].tolist() if len(gate) else "无——全部达标")


if __name__ == "__main__":
    sys.exit(main())
