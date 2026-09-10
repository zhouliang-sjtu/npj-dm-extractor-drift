# -*- coding: utf-8 -*-
"""29_ecg_acceptance.py —— ECG 域 M2d 正式验收：LLM vs 金标准终值（12 变量多标签）
gold 终值解析：A1==A2 → A1；否则 results/arbitration_decisions.csv per-variable 仲裁值
（修复 ECG_0374/0391 双仲裁行 per-row 列覆盖 bug——以仲裁 CSV 为权威）。
门槛（预注册）：κ≥0.80；F1_pos≥0.90；acc≥95%；分年份层 acc≥90%。
冻结策略（沿用 2026-09-09 拍板口径）：n_pass≥8/12 → 整域冻结+未过变量 below-gate 注记。
输出：results/m2d_acceptance_ecg.csv
用法：python code/29_ecg_acceptance.py [--no-freeze]
"""
import json
import os
import re
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ECG_VARS = ["ecg_normal", "ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock", "ecg_bbb",
            "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave_mi", "ecg_other",
            "ecg_unreadable"]
MODELS = {"qwen2.5:14b": "llm_ecg570_v1__qwen2.5_14b.csv",
          "qwen2.5:7b": "llm_ecg570_v1__qwen2.5_7b.csv",
          "glm4:9b": "llm_ecg570_v1__glm4_9b.csv"}
FIELD_RE = {v: re.compile(rf'"{v}"\s*:\s*([01])') for v in ECG_VARS}


def parse(raw):
    """按字段正则提取0/1（glm4 偶发 evidence 内未转义引号致 JSON 畸形，字段级提取不受影响）"""
    if not isinstance(raw, str) or not raw:
        return None
    out = {}
    for v, rex in FIELD_RE.items():
        m = rex.search(raw)
        if m:
            out[v] = m.group(1)
    return out if out else None


def kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in labels)
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0, po


def f1_pos(a, b):
    tp = sum(1 for x, y in zip(a, b) if x == "1" and y == "1")
    fp = sum(1 for x, y in zip(a, b) if x != "1" and y == "1")
    fn = sum(1 for x, y in zip(a, b) if x == "1" and y != "1")
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return (2 * p * r / (p + r) if p + r else 0.0)


def gold_finals():
    e = pd.read_excel(os.path.join(ROOT, "data", "金标准标注工作簿_终版.xlsx"),
                      sheet_name="ECG_H", dtype=str).set_index("sample_id")
    arb = pd.read_csv(os.path.join(ROOT, "results", "arbitration_decisions.csv"), dtype=str)
    arb_map = {(r["sample_id"], r["variable"]): r["final"]
               for _, r in arb.iterrows() if r["sheet"] == "ECG_H"}
    g = {}
    for sid in e.index:
        r = e.loc[sid]
        for var in ECG_VARS:
            a1, a2 = r["A1_" + var], r["A2_" + var]
            if pd.notna(a1) and a1 == a2:
                g[(sid, var)] = a1
            elif (sid, var) in arb_map:
                g[(sid, var)] = arb_map[(sid, var)]
            else:
                g[(sid, var)] = ""
    return e, g


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    no_freeze = "--no-freeze" in sys.argv
    e, g = gold_finals()
    all_rows = []
    for model, fn in MODELS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        parsed = {r.sample_id: parse(r.llm_raw) for r in d.itertuples(index=False)}
        print(f"\n===== {model} =====")
        n_pass = 0
        for var in ECG_VARS:
            a, b, yrs = [], [], []
            for sid in d.sample_id:
                gv = g.get((sid, var), "")
                p = parsed.get(sid)
                if gv == "" or p is None:
                    continue
                a.append(str(gv))
                b.append(str(p.get(var)))
                yrs.append(str(e.loc[sid, "year"])[:4])
            if len(a) < 30:
                print(f"  {var}: 有效配对不足（{len(a)}），跳过")
                continue
            k, po = kappa(a, b)
            f1 = f1_pos(a, b)
            row = dict(model=model, variable=var, n=len(a), raw_acc=round(po, 3),
                       cohen_kappa=round(k, 3), F1_pos=round(f1, 3))
            bad_layer = []
            for y in sorted(set(yrs)):
                idx = [i for i, yy in enumerate(yrs) if yy == y]
                if len(idx) >= 15:
                    acc_y = float(np.mean([a[i] == b[i] for i in idx]))
                    row[f"acc@{y}"] = round(acc_y, 3)
                    if acc_y < 0.90:
                        bad_layer.append(f"{y}={acc_y:.3f}")
            ok = (k >= 0.80) and (f1 >= 0.90) and (po >= 0.95) and not bad_layer
            row["verdict"] = "PASS" if ok else "FAIL"
            row["fail_note"] = ";".join(filter(None, [
                "" if k >= 0.80 else f"kappa={k:.3f}", "" if f1 >= 0.90 else f"F1={f1:.3f}",
                "" if po >= 0.95 else f"acc={po:.3f}",
                "layer:" + ",".join(bad_layer) if bad_layer else ""]))
            n_pass += ok
            all_rows.append(row)
            print(f"  {var}: κ={k:.3f} acc={po:.3f} F1_pos={f1:.3f} "
                  f"层FAIL[{','.join(bad_layer)}] → {row['verdict']}")
        print(f"  → {model}: {n_pass}/12 PASS")
        all_rows.append(dict(model=model, variable="_SUMMARY_", n=len(d), raw_acc="",
                             cohen_kappa="", F1_pos="", verdict=f"{n_pass}/12 PASS",
                             fail_note=""))
    acc = pd.DataFrame(all_rows)
    acc.to_csv(os.path.join(ROOT, "results", "m2d_acceptance_ecg.csv"), index=False,
               encoding="utf-8-sig")
    # 冻结判定（沿用拍板口径：整域冻结+below-gate 注记）
    m14 = acc[(acc.model == "qwen2.5:14b") & (acc.variable != "_SUMMARY_")]
    n_pass = int((m14.verdict == "PASS").sum())
    fail_vars = set(m14[m14.verdict == "FAIL"]["variable"])
    print(f"\nqwen2.5:14b: {n_pass}/12 变量 PASS；未过: {sorted(fail_vars) if fail_vars else '无'}")
    if n_pass >= 8 and not no_freeze:
        mp = os.path.join(ROOT, "extractor_manifest.json")
        man = json.load(open(mp, encoding="utf-8"))
        e_ = next(x for x in man["extractors"] if x["variable_domain"] == "ECG_H")
        e_["status"] = "frozen"
        e_["frozen_date"] = "2026-09-09"
        e_["accepted_model"] = "qwen2.5:14b (Ollama, 本地)"
        e_["acceptance"] = {
            "file": "results/m2d_acceptance_ecg.csv",
            "gold": "data/金标准标注工作簿_终版.xlsx (ECG_H, n=570, 双标注+仲裁终值)",
            "below_gate": {v: str(m14[m14.variable == v].iloc[0]["fail_note"])
                           for v in sorted(fail_vars)},
        }
        man["updated"] = "2026-09-09"
        json.dump(man, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        print("manifest 已冻结 ECG_H 抽取器：qwen2.5:14b + prompt v1（dbb1ebe717ad3497）")
    elif not no_freeze:
        print("n_pass<8，不冻结")
    return 0


if __name__ == "__main__":
    sys.exit(main())
