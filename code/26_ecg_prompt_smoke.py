# -*- coding: utf-8 -*-
"""26_ecg_prompt_smoke.py —— ECG prompt v1 冒烟（仲裁边界例 + 正常例，对照金标准终值）
用法：python code/26_ecg_prompt_smoke.py [--models qwen2.5:14b]
"""
import json
import os
import sys
import urllib.request

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PROMPT = os.path.join(ROOT, "..", "00-三线探索-多模态动态队列", "docs",
                      "llm_ecg_prompt_template_v1.md")
FINAL = os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx")
ECG_VARS = ["ecg_normal", "ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock", "ecg_bbb",
            "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave_mi", "ecg_other", "ecg_unreadable"]
# 仲裁边界例（来自 results/arbitration_decisions.csv）+ 正常例
FOCUS = {
    "ECG_0054": ["ecg_other"],        # 早期复极 → other=0
    "ECG_0175": ["ecg_other"],        # 左室高电压 → other=0
    "ECG_0341": ["ecg_other"],        # 窦房阻滞 → other=1
    "ECG_0374": ["ecg_other", "ecg_rate"],  # 交界区心动过速 → other=1, rate=0
    "ECG_0221": ["ecg_rate", "ecg_af"],     # 房颤伴快速心室率 → rate=1, af=1
    "ECG_0442": ["ecg_rate"],         # 房颤伴快速心室率 → rate=1
}
N_NORMAL = 2


def final_of(row, var):
    a1, a2, arb = row.get("A1_" + var), row.get("A2_" + var), row.get("arbitration")
    if pd.notna(a1) and a1 == a2:
        return a1
    if pd.notna(arb) and str(arb).strip():
        return str(arb).strip()
    return ""


def call(model, system, text):
    body = {"model": model, "stream": False, "format": "json",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": text}],
            "options": {"temperature": 0, "seed": 42, "num_predict": 400}}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    models = ["qwen2.5:14b"]
    for a in sys.argv:
        if a.startswith("--models="):
            models = a.split("=", 1)[1].split(",")
    system = open(PROMPT, encoding="utf-8").read()
    e = pd.read_excel(FINAL, sheet_name="ECG_H", dtype=str).set_index("sample_id")
    cases = [(sid, e.loc[sid]) for sid in FOCUS]
    nn = 0
    for sid in e.index:
        row = e.loc[sid]
        if final_of(row, "ecg_normal") == "1" and final_of(row, "ecg_unreadable") == "0":
            cases.append((sid + "(正常)", row))
            nn += 1
        if nn >= N_NORMAL:
            break
    print(f"ECG prompt v1 冒烟：{len(cases)} 例 × {models}")
    for model in models:
        print(f"===== {model} =====")
        ok = tot = 0
        for name, row in cases:
            try:
                j = json.loads(call(model, system, row["text"]))
            except Exception as ex:
                print(f"  {name}: 失败 {ex}")
                continue
            checks = []
            for var in ECG_VARS:
                exp = final_of(row, var)
                if exp == "":
                    continue
                got = str(j.get(var))
                # 正常例只查 normal/unreadable 两项，其余字段金标准空
                if name.endswith("(正常)") and var not in ("ecg_normal", "ecg_unreadable"):
                    continue
                if var in FOCUS.get(name.split("(")[0], []) or name.endswith("(正常)") or \
                        exp != "" and var in ("ecg_normal", "ecg_unreadable"):
                    checks.append((var, exp, got))
            marks = []
            for var, exp, got in checks:
                tot += 1
                good = exp == got
                ok += good
                marks.append(f"{var}{'√' if good else '×'}(期{exp}/得{got})")
            print(f"  {name}: {' '.join(marks) if marks else '(无对照项)'}")
        print(f"  → {model}: {ok}/{tot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
