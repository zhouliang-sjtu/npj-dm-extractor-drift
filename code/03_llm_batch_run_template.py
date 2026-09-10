# -*- coding: utf-8 -*-
"""03_llm_batch_run_template.py —— LLM跑批模板（OpenAI兼容endpoint，本地vLLM/任意后端）
要点：temperature=0、seed固定、prompt从模板文件读、输入输出sha256双hash留痕、断点续跑
用法：配置 ENDPOINT/MODEL 后 `python 03_llm_batch_run_template.py --input data/gold_echo_PG.csv --out data/llm_echo_PG_run1.csv`
"""
import argparse
import hashlib
import json
import os
import time

import pandas as pd
import requests

ENDPOINT = "http://127.0.0.1:8000/v1/chat/completions"   # 本地vLLM示例
MODEL = "Qwen2.5-72B-Instruct"
TEMPERATURE = 0.0
SEED = 42
PROMPT_FILE = os.path.join(os.path.dirname(__file__), "..", "..",
                           "00-三线探索-多模态动态队列", "docs",
                           "llm_echo_prompt_template_v2_1.md")
MAX_TOKENS = 400

def sha(s): return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]

def call_llm(text, system_prompt, session):
    payload = {"model": MODEL, "temperature": TEMPERATURE, "seed": SEED, "max_tokens": MAX_TOKENS,
               "messages": [{"role": "system", "content": system_prompt},
                            {"role": "user", "content": text}]}
    r = session.post(ENDPOINT, json=payload, timeout=120)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def main():
    global ENDPOINT, MODEL
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--endpoint", default=ENDPOINT,
                    help="OpenAI兼容端点；Ollama用 http://127.0.0.1:11434/v1/chat/completions")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--prompt-file", default=PROMPT_FILE,
                    help="prompt模板路径（默认 echo v2.1；ECG 用 llm_ecg_prompt_template_v1.md）")
    args = ap.parse_args()
    ENDPOINT, MODEL = args.endpoint, args.model

    with open(args.prompt_file, encoding="utf-8") as f:
        system_prompt = f.read()
    df = pd.read_csv(args.input, encoding="utf-8-sig", dtype=str)
    if args.limit: df = df.head(args.limit)

    out_path = args.out
    done = {}
    if os.path.exists(out_path):                     # 断点续跑
        prev = pd.read_csv(out_path, encoding="utf-8-sig", dtype=str)
        done = dict(zip(prev["input_hash"], prev["llm_raw"]))
        print(f"续跑：已有 {len(done)} 条")
    sess = requests.Session()
    rows = []
    for i, r in enumerate(df.itertuples(index=False)):
        text = str(getattr(r, "text", ""))
        ih = sha(text)
        if ih in done:
            rows.append({"sample_id": getattr(r, "sample_id", i), "input_hash": ih,
                         "llm_raw": done[ih], "output_hash": sha(done[ih])})
            continue
        for attempt in range(3):
            try:
                resp = call_llm(text, system_prompt, sess)
                rows.append({"sample_id": getattr(r, "sample_id", i), "input_hash": ih,
                             "llm_raw": resp, "output_hash": sha(resp)})
                break
            except Exception as e:
                print(f"  重试{i}: {e}"); time.sleep(2 ** attempt)
        else:
            rows.append({"sample_id": getattr(r, "sample_id", i), "input_hash": ih,
                         "llm_raw": "ERROR", "output_hash": ""})
        if (i + 1) % 50 == 0:
            pd.DataFrame(rows).to_csv(out_path, index=False, encoding="utf-8-sig")
            print(f"  {i+1}/{len(df)}")
    pd.DataFrame(rows).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"完成 -> {out_path}")

if __name__ == "__main__":
    main()
