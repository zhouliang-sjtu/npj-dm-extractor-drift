# -*- coding: utf-8 -*-
"""09_update_manifest.py —— 更新extractor_manifest（prompt v2哈希登记 + 四域对齐，2026-09-02）
用法: python code/09_update_manifest.py
"""
import hashlib
import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
PROMPT = os.path.join(BASE, "docs", "prompts", "llm_echo_prompt_template_v2_1.md")
MANIFEST = os.path.join(BASE, "extractor_manifest.json")

with open(PROMPT, encoding="utf-8") as f:
    phash = hashlib.sha256(f.read().encode("utf-8")).hexdigest()[:16]
print("prompt v2 sha256_16 =", phash)

with open(MANIFEST, encoding="utf-8") as f:
    m = json.load(f)

m["protocol"] = "LLM文本抽取测量学协议 v1.1（样本量方案A：双标子集1,470份）"
m["updated"] = "2026-09-02"
by_dom = {e["variable_domain"]: e for e in m["extractors"]}

# ECG_H：主案例域全量570
e = by_dom["ECG_H"]
e["extractor_type"] = "dictionary_v1(主库现状) | dictionary_v3 | llm(待验收)"
e["gold_standard_file"] = "data/gold_ecg_H.csv (570, 全量)"
e["note"] = "幻影信号主案例域；v1×v3年份交互见 results/dict_v1_v3_agreement.csv"

# ECHO_PG：prompt v2登记
e = by_dom["ECHO_PG"]
e["extractor_type"] = "regex(EF,确定性) + llm(分类)"
e["model_name"] = "qwen2.5:14b (Ollama, 本地)"
e["model_version"] = "qwen2.5 14b instruct"
e["prompt_version"] = "v2"
e["prompt_hash_sha256_16"] = phash
e["prompt_file"] = "00-三线探索-多模态动态队列/docs/llm_echo_prompt_template.md"
e["temperature"] = 0.0
e["seed"] = 42
e["gold_standard_file"] = "data/gold_echo_PG_300.csv (300, 600母体嵌套子集)"
e["prerun"] = {
    "file": "data/llm_echo_PG_mother600.csv",
    "n": 600, "json_rate_pct": 99.7, "error": 0,
    "note": "v1 prompt预跑(无rhythm字段)；prompt v2修复后待金标准验收时重跑",
    "qc_report": "results/llm_prerun_echo_qc.csv",
}
e["comparators"] = ["qwen2.5:7b (本地)", "glm4:9b (本地)"]

# ABDUS_PG / ABDUS_H：文件名对齐300子集
e = by_dom["ABDUS_H_PG"]
e["variable_domain"] = "ABDUS_PG"
e["gold_standard_file"] = "data/gold_abdus_PG_300.csv (300, 600母体嵌套子集)"
m["extractors"].append({
    "variable_domain": "ABDUS_H",
    "extractor_type": "dictionary(描述式口径)",
    "gold_standard_file": "data/gold_abdus_H_300.csv (300, 600母体嵌套子集)",
    "status": "pending_validation",
    "frozen_date": None,
})

with open(MANIFEST, "w", encoding="utf-8") as f:
    json.dump(m, f, ensure_ascii=False, indent=2)
print("manifest 已更新:", [e["variable_domain"] for e in m["extractors"]])
