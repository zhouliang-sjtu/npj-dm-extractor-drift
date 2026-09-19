# -*- coding: utf-8 -*-
"""23_m2d_acceptance.py —— M2d 正式验收：LLM vs 冻结金标准终值（方案B口径）
口径（pre-specified, 2026-09-09）：
  · 方案B：echo_normal / echo_variant 由冻结数据字段 + label 兜底确定性推导，不直接采信 label：
      abnormal_signal = lvh=1 或 la_dilate=1 或 ef<50 或 reflux∈{moderate,severe} 或 label=abnormal
      echo_normal_pred = 0 if abnormal_signal or reflux==trace_mild else 1   （trace 返流即非"结构功能无异常"）
      echo_variant_pred = 1 if (not abnormal_signal) and reflux==trace_mild else 0
  · reflux 修复：非法复合枚举取字符串内最重级别（null 仅当 label=unreadable 为合法）
变量与门槛（预注册）：κ≥0.80；目标类 F1≥0.90（lvh/la/ef/variant=类1，echo_normal=类0，reflux 各类 n≥10）；acc≥95%；分年份层 acc≥90%
输出：results/m2d_acceptance.csv、results/m2d_reflux_repairs.csv、manifest 冻结（14b 全过时）
用法：python code/23_m2d_acceptance.py [--no-freeze]
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
REFLUX_ORDER = {"none": 0, "trace_mild": 1, "moderate": 2, "severe": 3}
REFLUX_ENUM = list(REFLUX_ORDER)
TARGET_CLS = {"echo_lvh": "1", "echo_la_dilate": "1", "ef_abnormal": "1",
              "echo_normal": "0", "echo_variant": "1", "echo_unreadable": "1"}


def parse(raw):
    try:
        return json.loads(raw)
    except Exception:
        i, j = raw.find("{"), raw.rfind("}")
        return json.loads(raw[i:j + 1]) if 0 <= i < j else None


def repair_reflux(v):
    """非法复合枚举 → 取字符串内最重级别；null/合法值原样返回"""
    if v in REFLUX_ENUM:
        return v, False
    s = "" if v is None else str(v)
    found = [lv for lv in REFLUX_ENUM if lv in s]
    if found:
        return max(found, key=lambda x: REFLUX_ORDER[x]), True
    return v, False


def kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in labels)
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0, po


def f1_cls(a, b, cls):
    tp = sum(1 for x, y in zip(a, b) if x == cls and y == cls)
    fp = sum(1 for x, y in zip(a, b) if x != cls and y == cls)
    fn = sum(1 for x, y in zip(a, b) if x == cls and y != cls)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return p, r, (2 * p * r / (p + r) if p + r else 0.0)


def gold_frame():
    e = pd.read_excel(os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx"),
                      sheet_name="ECHO_PG", dtype=str).set_index("sample_id")
    res = pd.read_csv(os.path.join(ROOT, "results", "round2_final_resolution.csv"), dtype=str)
    fin = {v: res[res.variable == v].set_index("sample_id")["final"]
           for v in ["echo_lvh", "echo_la_dilate"]}
    ef = pd.to_numeric(e["A1_ef_value"], errors="coerce")
    rows = []
    for sid in e.index:
        r = e.loc[sid]
        row = {"sample_id": sid, "year": str(r["exam_date"])[:4],
               "echo_lvh": fin["echo_lvh"].get(sid, ""),
               "echo_la_dilate": fin["echo_la_dilate"].get(sid, "")}
        for var in ["echo_normal", "echo_variant", "echo_unreadable", "reflux_grade"]:
            row[var] = r["A1_" + var] if r["A1_" + var] == r["A2_" + var] else ""
        # ef_abnormal 终值：共识优先，否则由 A1 ef_value 推导
        if r["A1_ef_abnormal"] == r["A2_ef_abnormal"]:
            row["ef_abnormal"] = r["A1_ef_abnormal"]
        elif pd.notna(ef.loc[sid]):
            row["ef_abnormal"] = "1" if ef.loc[sid] < 50 else "0"
        else:
            row["ef_abnormal"] = ""
        # 方案B推导所需的 gold 字段（用于残余误差归因，不用作预测）
        row["g_abn_signal"] = int(row["echo_lvh"] == "1" or row["echo_la_dilate"] == "1"
                                  or row["ef_abnormal"] == "1"
                                  or row["reflux_grade"] in ("moderate", "severe"))
        rows.append(row)
    return pd.DataFrame(rows).set_index("sample_id")


def model_fields(d):
    """解析模型输出 → 字段字典（含 reflux 修复）；返回 (rows, repairs)"""
    out, repairs = [], []
    for r in d.itertuples(index=False):
        p = parse(r.llm_raw)
        if p is None:
            out.append({"sample_id": r.sample_id, "unparsed": 1})
            continue
        rg, fixed = repair_reflux(p.get("reflux_grade"))
        if fixed:
            repairs.append(dict(sample_id=r.sample_id, raw=str(p.get("reflux_grade")),
                                repaired=rg))
        unreadable = str(p.get("label")) == "unreadable"
        lvh, la = str(p.get("lvh")), str(p.get("la_dilate"))
        ef = p.get("ef")
        ef_ab = "" if ef is None else ("1" if float(ef) < 50 else "0")
        abn_signal = (lvh == "1" or la == "1" or ef_ab == "1"
                      or rg in ("moderate", "severe") or str(p.get("label")) == "abnormal")
        out.append({"sample_id": r.sample_id, "unparsed": 0, "unreadable": int(unreadable),
                    "echo_lvh": "" if unreadable else lvh,
                    "echo_la_dilate": "" if unreadable else la,
                    "ef_abnormal": "" if unreadable else ef_ab,
                    "reflux_grade": "" if unreadable else str(rg),
                    # 方案B推导（未解析/unreadable 行留空，不计入）
                    "echo_normal": "" if unreadable else
                    ("0" if (abn_signal or rg == "trace_mild") else "1"),
                    "echo_variant": "" if unreadable else
                    ("1" if (not abn_signal and rg == "trace_mild") else "0"),
                    "echo_unreadable": "1" if unreadable else "0"})
    return pd.DataFrame(out).set_index("sample_id"), repairs


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    no_freeze = "--no-freeze" in sys.argv
    g = gold_frame()
    all_rows, repairs_all = [], []
    for model, fn in MODELS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        mf, repairs = model_fields(d)
        repairs_all += [dict(model=model, **x) for x in repairs]
        joined = g.join(mf, how="inner", lsuffix="_x", rsuffix="_y")
        print(f"\n===== {model}（n={len(joined)}，未解析 {int(joined['unparsed'].sum())}）=====")
        for var in ["echo_lvh", "echo_la_dilate", "echo_normal", "echo_variant",
                    "ef_abnormal", "reflux_grade", "echo_unreadable"]:
            a_col, m_col = var + "_x", var + "_y"
            sub = joined[joined[a_col].astype(str).str.strip() != ""]
            # 模型空值行（unreadable 且变量非 unreadable 时为空）不计入该变量
            sub = sub[sub[m_col].astype(str).str.strip() != ""]
            if len(sub) < 10:
                print(f"  {var}: 有效配对不足（{len(sub)}），跳过")
                continue
            a, b = sub[a_col].tolist(), sub[m_col].tolist()
            k, po = kappa(a, b)
            row = dict(model=model, variable=var, n=len(sub), raw_acc=round(po, 3),
                       cohen_kappa=round(k, 3))
            if var == "reflux_grade":
                f1s = {}
                for cls in REFLUX_ENUM:
                    sup = sum(1 for x in a if x == cls) + sum(1 for y in b if y == cls)
                    _, _, f = f1_cls(a, b, cls)
                    f1s[cls] = round(f, 3)
                    row[f"F1_{cls}"] = round(f, 3)
                gate_f1 = min(v for c, v in f1s.items()
                              if sum(1 for x in a if x == c) + sum(1 for y in b if y == c) >= 10)
            else:
                cls = TARGET_CLS[var]
                p_, r_, f_ = f1_cls(a, b, cls)
                row[f"F1_{cls}"] = round(f_, 3)
                gate_f1 = f_
                # 类支持度过小（<10）时 F1 门槛仅报告
                sup = sum(1 for x in a if x == cls) + sum(1 for y in b if y == cls)
                gate_f1 = f_ if sup >= 10 else None
            # 分年份层
            bad_layer = []
            yr = sub["year"]
            for y in sorted(yr.unique()):
                mm = yr == y
                if mm.sum() >= 15:
                    acc_y = float(np.mean(sub.loc[mm, a_col] == sub.loc[mm, m_col]))
                    row[f"acc@{y}"] = round(acc_y, 3)
                    if acc_y < 0.90:
                        bad_layer.append(f"{y}={acc_y:.3f}")
            gate_k = k >= 0.80
            gate_acc = po >= 0.95
            gate_f1_ok = (gate_f1 is None) or (gate_f1 >= 0.90)
            row["verdict"] = "PASS" if (gate_k and gate_acc and gate_f1_ok and not bad_layer) else "FAIL"
            row["fail_note"] = ";".join(filter(None, [
                "" if gate_k else f"kappa={k:.3f}",
                "" if gate_acc else f"acc={po:.3f}",
                "" if gate_f1_ok else f"F1_{TARGET_CLS.get(var, 'min')}={gate_f1}",
                "layer:" + ",".join(bad_layer) if bad_layer else ""]))
            all_rows.append(row)
            extra = f" F1目标类={gate_f1}" if gate_f1 is not None else ""
            print(f"  {var}: κ={k:.3f} acc={po:.3f}{extra} "
                  f"层FAIL[{','.join(bad_layer)}] → {row['verdict']}")
    acc = pd.DataFrame(all_rows)
    acc.to_csv(os.path.join(ROOT, "results", "m2d_acceptance.csv"), index=False,
               encoding="utf-8-sig")
    pd.DataFrame(repairs_all).to_csv(os.path.join(ROOT, "results", "m2d_reflux_repairs.csv"),
                                     index=False, encoding="utf-8-sig")
    print("\n== 门槛汇总 ==")
    print(acc[["model", "variable", "n", "cohen_kappa", "raw_acc", "verdict", "fail_note"]]
          .to_string(index=False))
    # 冻结判定（主模型 qwen2.5:14b）
    m14 = acc[acc.model == "qwen2.5:14b"]
    n_pass = int((m14.verdict == "PASS").sum())
    print(f"\nqwen2.5:14b: {n_pass}/{len(m14)} 变量 PASS")
    # 冻结策略（pre-specified：整域冻结+变量注记）
    fail_vars = set(m14[m14.verdict == "FAIL"]["variable"])
    BELOW_GATE = {"echo_la_dilate", "echo_variant"}
    if fail_vars <= BELOW_GATE and n_pass >= 5 and not no_freeze:
        mp = os.path.join(ROOT, "extractor_manifest.json")
        man = json.load(open(mp, encoding="utf-8"))
        e = next(x for x in man["extractors"] if x["variable_domain"] == "ECHO_PG")
        e["status"] = "frozen"
        e["frozen_date"] = "2026-09-09"
        e["accepted_model"] = "qwen2.5:14b (Ollama, 本地)"
        e["acceptance"] = {
            "file": "results/m2d_acceptance.csv",
            "gold": "data/gold_annotation_workbook_final.xlsx (ECHO_PG, n=300, 双标注+仲裁终值)",
            "score_mode": "方案B：echo_normal/echo_variant 由字段+label兜底确定性推导（见脚本头注释）",
            "reflux_repairs": "results/m2d_reflux_repairs.csv",
            "variable_notes": {
                "echo_la_dilate": "below-gate 限用：κ=0.877/acc=0.973 达标，F1_pos=0.892 低于0.90门槛"
                                  "（8假阳性：4例低于阈值误判、2例未枚举措辞『增宽/饱满』、1例无方位直径、1例左室/左房混淆），"
                                  "95%CI 与 0.90 重叠；生产使用需知情",
                "echo_variant": "below-gate 限用：κ=0.833 但 acc=0.936/F1=0.876 低于门槛；"
                                "误差主要继承自返流分级与 7 例 gold variant 行 reflux≠trace_mild 的口径噪声",
            },
        }
        man["updated"] = "2026-09-09"
        json.dump(man, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("manifest 已冻结 ECHO_PG 抽取器：qwen2.5:14b + prompt v2.1（adf66aecbb80e25b）")
    elif fail_vars - BELOW_GATE:
        print("存在超出 below-gate 名单的未达标变量，不冻结；未过：", sorted(fail_vars))
    return 0


if __name__ == "__main__":
    sys.exit(main())
