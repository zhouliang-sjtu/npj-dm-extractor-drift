# -*- coding: utf-8 -*-
"""25_make_table2.py —— 组装 Table2 草表（多抽取器 × 变量 κ/F1 + 延迟/GPU时）
输入：results/m2d_acceptance.csv（M2d 验收）、results/m3c_latency_summary.csv（M3c 延迟）
输出：results/table2_draft.md（草表，投稿时按期刊格式重排）
用法：python code/25_make_table2.py
"""
import os
import sys

import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VARS = ["echo_lvh", "echo_la_dilate", "echo_normal", "echo_variant",
        "ef_abnormal", "reflux_grade", "echo_unreadable"]
VN = {"echo_lvh": "LVH", "echo_la_dilate": "LA dilation", "echo_normal": "Normal flag",
      "echo_variant": "Normal variant", "ef_abnormal": "EF<50", "reflux_grade": "Reflux grade",
      "echo_unreadable": "Unreadable"}


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    acc = pd.read_csv(os.path.join(ROOT, "results", "m2d_acceptance.csv"))
    lat = pd.read_csv(os.path.join(ROOT, "results", "m3c_latency_summary.csv"))
    lat_i = lat.set_index("model")
    FROZEN = "qwen2.5:14b"  # manifest 冻结抽取器；usage 列按其 verdict 标注

    def cell(r):
        k, f = r["cohen_kappa"], r.get("F1_1") or r.get("F1_min") or ""
        mark = "" if r["verdict"] == "PASS" else "†"
        if var == "reflux_grade":
            return f"{k:.2f}{mark}"
        return f"{k:.2f}/{f if f == '' else format(float(f), '.2f')}{mark}"

    def usage(var):
        r = acc[(acc.model == FROZEN) & (acc.variable == var)]
        if len(r) == 0:
            return "—"
        return "primary" if r.iloc[0]["verdict"] == "PASS" else "sensitivity-only"

    lines = [
        "# Table 2（草表）— Extractor performance on the cardiac-ultrasound validation set (n=300)",
        "",
        "跑批参数：prompt v2.1（SHA-256 adf66aecbb80e25b），temperature=0，seed=42，本地 Ollama，",
        "AMD Radeon 8060S iGPU（ROCm）。延迟=单流每报告墙钟秒（seed=42 抽 20 份实测，warm-up 不计）。",
        "† = 未达预注册门槛（κ≥0.80、目标类 F1≥0.90、acc≥95%、年份层 acc≥90%）。",
        "",
        "| Variable | " + " | ".join(acc.model.unique()) + " | Recommended usage (frozen " + FROZEN + ") |",
        "|---" * (len(acc.model.unique()) + 2) + "|",
    ]
    for var in VARS:
        row = [VN[var]]
        for model in acc.model.unique():
            r = acc[(acc.model == model) & (acc.variable == var)]
            if len(r) == 0:
                row.append("—")
                continue
            r = r.iloc[0]
            if var == "reflux_grade":
                # F1 取支持度≥10 的类（none/trace_mild/moderate）的最小值；
                # severe 类 gold 仅 3 例，低于支持度阈值，门槛与表中均不含（见脚注）
                f1cols = ["F1_none", "F1_trace_mild", "F1_moderate"]
                fmin = min(float(r[c]) for c in f1cols if pd.notna(r[c]))
                row.append(f"{r['cohen_kappa']:.2f}{'†' if r['verdict'] != 'PASS' else ''} "
                           f"(min F1 {fmin:.2f})")
            else:
                fcol = "F1_1" if var != "echo_normal" else "F1_0"
                fv = r.get(fcol)
                fv = f"{float(fv):.2f}" if pd.notna(fv) and fv != "" else "—"
                row.append(f"{r['cohen_kappa']:.2f}/{fv}{'†' if r['verdict'] != 'PASS' else ''}")
        row.append(usage(var))
        lines.append("| " + " | ".join(row) + " |")
    lines += ["", "注：Reflux grade 的 F1 为支持度≥10 类（none/trace_mild/moderate）的最小值；"
                  "severe 类 gold 仅 3 例，低于支持度阈值，不入门槛。"
              "echo_normal/echo_variant 按方案B由冻结字段+label兜底确定性推导（见 code/23 头注释）。",
              "Recommended usage：primary=该变量通过全部预注册门槛、可进入主分析；"
              "sensitivity-only=未达门槛（manifest 已 below_gate 注记），仅限敏感性分析。"
              "其余模型的 † 变量在同一规则下同样仅限敏感性分析。", "",
              "**Engineering metrics**", "",
              "| Model | JSON rate | Latency median (s) | Latency P95 (s) | Tokens/s | GPU-hours / 1,000 reports |",
              "|---|---|---|---|---|---|"]
    for model in acc.model.unique():
        s = lat_i.loc[model]
        jr = pd.read_csv(os.path.join(ROOT, "results", "m2c_qc.csv"))
        jr = jr[jr.model == model].iloc[0]["json_rate"]
        lines.append(f"| {model} | {jr:.3f} | {s.median_latency_s:.2f} | {s.p95_latency_s:.2f} "
                     f"| {s.tokens_per_s:.1f} | {s.est_gpu_hours_per_1000:.2f} |")
    out = os.path.join(ROOT, "results", "table2_draft.md")
    open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    print("\n".join(lines))
    print("\n-> " + out)


if __name__ == "__main__":
    sys.exit(main())
