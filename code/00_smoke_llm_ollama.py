# -*- coding: utf-8 -*-
"""00_smoke_llm_ollama.py —— 本地LLM跑批冒烟测试（Ollama qwen2.5:14b × echo分类10份）
验证：连通性/JSON解析率/字段完整性/延迟；输出 data/smoke_echo_llm.csv
"""
import json
import os
import time
import requests
import pandas as pd

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root

ENDPOINT = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5:14b"
SEED = 42
N = 10

SYSTEM = """你是心脏超声报告结构化助手。将输入的中文心脏超声检查所见分类，只输出严格JSON：
{"label":"normal|normal_variant|abnormal","lvh":0,"la_dilate":0,"ef":null,"reflux_grade":"none|mild|moderate|severe","evidence":"原文关键句"}
判定规则：normal=无异常；normal_variant=仅少量/轻度返流；abnormal=室间隔或左室壁增厚(LVH)、左房增大(内径≥40mm或写明增大)、EF<50、中度及以上返流、节律异常(早搏/房颤/起搏/传导阻滞)。"未见返流"=none。不输出任何其他文字。"""

df = pd.read_csv(os.path.join(BASE, "data", "gold_echo_PG_300.csv"),
                 encoding="utf-8-sig", dtype=str).head(N)

rows = []
for i, r in enumerate(df.itertuples(index=False)):
    t0 = time.time()
    try:
        resp = requests.post(ENDPOINT, json={
            "model": MODEL, "stream": False,
            "messages": [{"role": "system", "content": SYSTEM},
                         {"role": "user", "content": str(r.text)}],
            "options": {"temperature": 0, "seed": SEED},
        }, timeout=300)
        raw = resp.json()["message"]["content"]
        s = raw[raw.find("{"): raw.rfind("}") + 1]
        try:
            j = json.loads(s)
            ok = j.get("label") in ("normal", "normal_variant", "abnormal")
        except Exception:
            j, ok = None, False
        rows.append({"i": i, "sample_id": r.sample_id, "latency_s": round(time.time() - t0, 1),
                     "json_ok": ok, "label": (j or {}).get("label", ""),
                     "lvh": (j or {}).get("lvh", ""), "la_dilate": (j or {}).get("la_dilate", ""),
                     "ef": (j or {}).get("ef", ""), "reflux": (j or {}).get("reflux_grade", ""),
                     "raw_head": raw[:80]})
    except Exception as e:
        rows.append({"i": i, "sample_id": r.sample_id, "latency_s": round(time.time() - t0, 1),
                     "json_ok": False, "label": f"ERROR:{e}", "raw_head": ""})
    print(f"[{i+1}/{N}] {rows[-1]['latency_s']}s json_ok={rows[-1]['json_ok']} label={rows[-1]['label']}")

out = pd.DataFrame(rows)
out.to_csv(os.path.join(BASE, "results", "smoke_echo_llm.csv"),
           index=False, encoding="utf-8-sig")
print("\n===== 冒烟汇总 =====")
print(f"JSON解析成功率: {out['json_ok'].mean()*100:.0f}%  平均延迟: {out['latency_s'].mean():.1f}s")
print(out[["sample_id", "label", "lvh", "la_dilate", "ef", "reflux"]].to_string(index=False))
