# -*- coding: utf-8 -*-
"""24_m3c_latency.py —— M3c Table2 延迟/GPU时实测
口径：与跑批完全同参（OpenAI兼容endpoint /v1/chat/completions、temperature=0、seed=42、max_tokens=400、
      prompt v2.1 adf66aecbb80e25b），seed=42 抽 20 份，串行逐份计时；每模型先 1 次 warm-up（不计时），
      末次请求 keep_alive=0 卸载模型避免互扰。
指标：每份墙钟延迟（s）、prompt/completion tokens、tokens/s；汇总 mean/median/P95 延迟与 推算 GPU时/千份。
输出：results/m3c_latency.csv（逐份）、results/m3c_latency_summary.csv（汇总）+ 控制台报告
用法：python code/24_m3c_latency.py [--n 20]
"""
import json
import os
import sys
import time

import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT = os.path.join(ROOT, "..", "00-三线探索-多模态动态队列", "docs",
                      "llm_echo_prompt_template_v2_1.md")
INPUT = os.path.join(ROOT, "data", "gold_echo_PG_300.csv")
ENDPOINT = "http://127.0.0.1:11434/v1/chat/completions"
MODELS = ["qwen2.5:14b", "qwen2.5:7b", "glm4:9b"]


def call(model, system, text, keep_alive=None):
    payload = {"model": model, "temperature": 0.0, "seed": 42, "max_tokens": 400,
               "messages": [{"role": "system", "content": system},
                            {"role": "user", "content": text}]}
    if keep_alive is not None:
        payload["keep_alive"] = keep_alive
    t0 = time.perf_counter()
    r = requests.post(ENDPOINT, json=payload, timeout=600)
    dt = time.perf_counter() - t0
    r.raise_for_status()
    j = r.json()
    u = j.get("usage", {})
    return dt, u.get("prompt_tokens"), u.get("completion_tokens")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    n = 20
    for a in sys.argv:
        if a.startswith("--n="):
            n = int(a.split("=", 1)[1])
    system = open(PROMPT, encoding="utf-8").read()
    df = pd.read_csv(INPUT, encoding="utf-8-sig", dtype=str).sample(n=n, random_state=42)
    texts = df["text"].fillna("").tolist()
    sids = df["sample_id"].tolist()
    rows = []
    for model in MODELS:
        print(f"{model}: warm-up ...", flush=True)
        call(model, system, texts[0])  # warm-up（含模型加载，不计时）
        for i, (sid, t) in enumerate(zip(sids, texts)):
            keep = 0 if i == n - 1 else None  # 末次卸载，避免跨模型互扰
            dt, pt, ct = call(model, system, t, keep_alive=keep)
            rows.append(dict(model=model, sample_id=sid, latency_s=round(dt, 3),
                             prompt_tokens=pt, completion_tokens=ct))
            print(f"  {i+1}/{n} {sid} {dt:.2f}s ({pt}→{ct} tok)", flush=True)
    lat = pd.DataFrame(rows)
    lat.to_csv(os.path.join(ROOT, "results", "m3c_latency.csv"), index=False,
               encoding="utf-8-sig")
    summ = []
    for model in MODELS:
        s = lat[lat.model == model]
        ms = s.latency_s
        tps = (s.completion_tokens / s.latency_s).mean()
        summ.append(dict(model=model, n=len(s),
                         mean_latency_s=round(ms.mean(), 2),
                         median_latency_s=round(ms.median(), 2),
                         p95_latency_s=round(ms.quantile(0.95), 2),
                         mean_completion_tokens=round(s.completion_tokens.mean(), 1),
                         tokens_per_s=round(tps, 1),
                         est_gpu_hours_per_1000=round(ms.mean() * 1000 / 3600, 2)))
    sm = pd.DataFrame(summ)
    sm.to_csv(os.path.join(ROOT, "results", "m3c_latency_summary.csv"), index=False,
              encoding="utf-8-sig")
    print("\n== 延迟汇总（单流，ROCm iGPU Radeon 8060S，prompt v2.1 adf66aecbb80e25b）==")
    print(sm.to_string(index=False))


if __name__ == "__main__":
    sys.exit(main())
