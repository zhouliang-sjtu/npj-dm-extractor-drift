# -*- coding: utf-8 -*-
"""08_llm_prerun_qc.py —— echo 600母体LLM预跑质量报告（2026-09-02）
统计：JSON解析率、ERROR率、字段完整度、LLM vs 词典法逐字段一致率（预览，非验收κ）
输出: results/llm_prerun_echo_qc.csv + 控制台摘要
用法: python code/08_llm_prerun_qc.py
"""
import json
import os
import sys

import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
RES = os.path.join(BASE, "results")
os.makedirs(RES, exist_ok=True)
sys.path.insert(0, os.path.join(BASE, "code"))
from main import extract_echo, norm  # noqa: E402

llm = pd.read_csv(os.path.join(BASE, "data", "llm_echo_PG_mother600.csv"),
                  encoding="utf-8-sig", dtype=str)
gold = pd.read_csv(os.path.join(BASE, "data", "gold_echo_PG.csv"),
                   encoding="utf-8-sig", dtype=str)
d = llm.merge(gold[["sample_id", "text"]], on="sample_id", how="left")
print(f"预跑记录: {len(d)} 条")


def parse_json(raw):
    """直接解析；失败则花括号截取重试（协议内置策略）"""
    if not isinstance(raw, str) or raw.startswith("ERROR"):
        return None, False
    try:
        return json.loads(raw), True
    except Exception:
        i, j = raw.find("{"), raw.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(raw[i:j + 1]), True
            except Exception:
                return None, False
    return None, False


parsed = d["llm_raw"].map(parse_json)
d["json_ok"] = [ok for _, ok in parsed]
d["obj"] = [o for o, _ in parsed]

n_err = int(d["llm_raw"].astype(str).str.startswith("ERROR").sum())
n_ok = int(d["json_ok"].sum())
print(f"ERROR条数: {n_err}；JSON可解析: {n_ok}/{len(d)} = {n_ok/len(d)*100:.1f}%")

FIELDS = ["label", "lvh", "la_dilate", "ef", "reflux_grade", "rhythm"]
ok = d[d["json_ok"]].copy()
for f in FIELDS:
    ok["llm_" + f] = ok["obj"].map(lambda o: str(o.get(f, "")).strip() if isinstance(o, dict) else "")

# 字段完整度
comp = {f: round(float((ok["llm_" + f] != "").mean()) * 100, 1) for f in FIELDS}
print("字段完整度(%):", comp)

# label分布
print("LLM label分布:", ok["llm_label"].value_counts().to_dict())

# 与词典法对比（仅json_ok子集；预览用，验收以金标准为准）
dict_res = gold.set_index("sample_id")["text"].map(
    lambda t: extract_echo(norm(t)) if isinstance(t, str) else None)
agree = {f: [] for f in ["label", "lvh", "la_dilate", "reflux_grade", "rhythm"]}
ef_abs = []
for _, r in ok.iterrows():
    dr = dict_res.get(r["sample_id"])
    if dr is None:
        continue
    for f in agree:
        lv = r["llm_" + f]
        dv = dr.get(f)
        if f == "label":
            pass
        agree[f].append(str(lv) == str(dv))
    # EF一致性：两者都抽出EF时比较（±1容差）
    le, de = r["llm_ef"], dr.get("ef")
    if le not in ("", None) and de is not None:
        try:
            ef_abs.append(abs(float(le) - float(de)) <= 1)
        except Exception:
            pass
row = {"n_total": len(d), "n_json_ok": n_ok, "n_error": n_err,
       "json_rate_pct": round(n_ok / len(d) * 100, 1),
       "agree_label_pct": round(sum(agree["label"]) / len(agree["label"]) * 100, 1),
       "agree_lvh_pct": round(sum(agree["lvh"]) / len(agree["lvh"]) * 100, 1),
       "agree_la_pct": round(sum(agree["la_dilate"]) / len(agree["la_dilate"]) * 100, 1),
       "agree_reflux_pct": round(sum(agree["reflux_grade"]) / len(agree["reflux_grade"]) * 100, 1),
       "agree_rhythm_pct": round(sum(agree["rhythm"]) / len(agree["rhythm"]) * 100, 1),
       "n_ef_both": len(ef_abs),
       "ef_match_within1_pct": round(sum(ef_abs) / len(ef_abs) * 100, 1) if ef_abs else None}
out = pd.DataFrame([row])
out.to_csv(RES + "/llm_prerun_echo_qc.csv", index=False, encoding="utf-8-sig")
print("\n=== LLM vs 词典法 一致率预览（json_ok子集，验收以金标准为准） ===")
print(out.T.to_string(header=False))
print(f"\n-> {RES}/llm_prerun_echo_qc.csv")
