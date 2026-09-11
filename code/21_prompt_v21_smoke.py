# -*- coding: utf-8 -*-
"""21_prompt_v21_smoke.py —— prompt v2.1 冒烟验证（关键边界个案 × 三模型）
用例（取自金标准终版 ECHO_PG，预期=冻结终值）：
  ECHO_0232  前后内径39+左右内径45（仅左右径超40）→ la_dilate=0（v2.1口径），lvh=1（后壁17mm）
  ECHO_0257  前后径40（含等于）+左右径41        → la_dilate=1
  ECHO_0279  12mm 阈值含等于仲裁例              → lvh=1
  ECHO_0006  上下径57 达阈值                    → la_dilate=1
  心包积液例（检索文本）                        → label=abnormal
  正常例（检索"未见明显"描述）                  → label=normal_variant|normal（按返流字段）
用法：python code/21_prompt_v21_smoke.py [--models qwen2.5:14b,qwen2.5:7b,glm4:9b]
"""
import json
import os
import sys
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT = os.path.join(ROOT, "..", "00-三线探索-多模态动态队列", "docs",
                      "llm_echo_prompt_template_v2_1.md")
FINAL = os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx")
API = "http://127.0.0.1:11434/api/chat"


def final_of(row, var):
    a1, a2, arb = row.get("A1_" + var), row.get("A2_" + var), row.get("arbitration")
    if pd.notna(a1) and a1 == a2:
        return a1
    if pd.notna(arb) and str(arb).strip():
        return str(arb).strip()
    return a1 if pd.notna(a1) else ""


def call(model, system, text):
    body = {"model": model, "stream": False, "format": "json",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": text}],
            "options": {"temperature": 0, "seed": 42, "num_predict": 400}}
    req = urllib.request.Request(API, data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]


def pick_cases(e):
    cases = []
    for sid in ["ECHO_0232", "ECHO_0257", "ECHO_0279", "ECHO_0006"]:
        cases.append((sid, e.set_index("sample_id").loc[sid]))
    cases.append(("ECHO_0181(双瓣膜返流)", e.set_index("sample_id").loc["ECHO_0181"]))
    pe = e[e["text"].fillna("").str.contains("心包积液|液性暗区")]
    if len(pe):
        cases.append((pe.iloc[0]["sample_id"] + "(心包积液)", pe.iloc[0]))
    nn = e[e["text"].fillna("").str.contains("未见明显异常|各房室腔大小形态正常")]
    if len(nn):
        cases.append((nn.iloc[0]["sample_id"] + "(正常)", nn.iloc[0]))
    return cases


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    models = ["qwen2.5:14b", "qwen2.5:7b", "glm4:9b"]
    for a in sys.argv:
        if a.startswith("--models="):
            models = a.split("=", 1)[1].split(",")
    system = open(PROMPT, encoding="utf-8").read()
    e = pd.read_excel(FINAL, sheet_name="ECHO_PG", dtype=str)
    cases = pick_cases(e)
    print(f"prompt v2.1 用例 {len(cases)} 个 × 模型 {models}\n")
    ok = tot = 0
    for model in models:
        print(f"===== {model} =====")
        for name, row in cases:
            try:
                out = call(model, system, row["text"])
                j = json.loads(out)
            except Exception as ex:
                print(f"  {name}: 调用/解析失败 {ex}")
                continue
            exp_lvh, exp_la = final_of(row, "echo_lvh"), final_of(row, "echo_la_dilate")
            exp_lab = final_of(row, "echo_normal")
            exp_lab = {"0": "abnormal", "1": "normal"}.get(exp_lab, "")
            exp_rg = final_of(row, "reflux_grade")
            checks = [("lvh", exp_lvh, str(j.get("lvh"))),
                      ("la_dilate", exp_la, str(j.get("la_dilate"))),
                      ("reflux", exp_rg, str(j.get("reflux_grade"))),
                      ("label", exp_lab, str(j.get("label")))]
            marks = []
            for f, exp, got in checks:
                if exp == "":
                    continue
                tot += 1
                good = exp == got
                ok += good
                marks.append(f"{f}{'√' if good else '×'}(期{exp}/得{got})")
            print(f"  {name}: {' '.join(marks) if marks else '(无对照项)'}")
        print()
    print(f"冒烟合计: {ok}/{tot} 项与冻结金标准一致")


if __name__ == "__main__":
    sys.exit(main())
