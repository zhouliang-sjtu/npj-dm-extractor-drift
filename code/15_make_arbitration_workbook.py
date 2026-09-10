# -*- coding: utf-8 -*-
"""15_make_arbitration_workbook.py —— M1e 仲裁工作簿生成（发仲裁人版）
输入：results/arbitration_queue.csv（code/14 产出）
输出：10_expert-consultation/06_仲裁裁定工作簿.xlsx
     说明sheet + 四域sheet（不一致/flag 两类行），仲裁裁定列按变量枚举加下拉约束
"""
import os
import sys

import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
QUEUE = os.path.join(ROOT, "results", "arbitration_queue.csv")
OUT = os.path.join(ROOT, "10_expert-consultation", "06_仲裁裁定工作簿.xlsx")

ENUM = {
    "us_fatty_degree": ["轻", "中", "重"],
    "reflux_grade": ["none", "trace_mild", "moderate", "severe"],
}
BINARY_HINT = "填 0 或 1（与该变量下发枚举一致）"

HEAD = ["kind", "variable", "sample_id", "time", "text", "A1判定", "A2判定",
        "flag", "note", "仲裁裁定", "裁定理由", "手册需修订(是/否)"]
ZH_HEAD = ["类型", "变量", "sample_id", "检查年份/日期", "原文text", "A1判定", "A2判定",
           "flag", "A1/A2备注note", "仲裁裁定（必填）", "裁定理由（一句话）", "手册需修订"]


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    q = pd.read_csv(QUEUE, dtype=str).fillna("")
    wb = Workbook()

    # ---- 说明 sheet ----
    ws = wb.active
    ws.title = "说明"
    lines = [
        ["仲裁裁定工作簿填写说明"],
        [""],
        ["来源：A1/A2 双标注回收核验与一致性验收（2026-09-03）后生成的仲裁队列。"],
        ["共四域：ECG_H（H社区心电图结论）/ ECHO_PG（PG心脏超声）/ ABDUS_PG（PG腹部超声）/ ABDUS_H（H社区腹部超声）。"],
        [""],
        ["行类型（类型列）："],
        ["  · 不一致 = A1与A2判定不同的个案：请依《02_标注手册》规则给出最终判定，填入『仲裁裁定』。"],
        ["  · flag = 标注时遇规则未覆盖情形（note 为原因）：请给出处理意见（维持/改判/需修订规则），"],
        ["    如涉及规则修订请在『手册需修订』列填 是，并在『裁定理由』写明建议规则表述。"],
        [""],
        ["填写约定："],
        ["  · 仲裁裁定 为必填：二值变量填 0/1；us_fatty_degree 填 轻/中/重；reflux_grade 填 none/trace_mild/moderate/severe。"],
        ["  · 裁定理由一句话即可；如个案无法裁决，填 无法裁决 并说明原因。"],
        ["  · 勿修改其余列；勿增删行。"],
        [""],
        ["判定时请参照《02_标注手册》全文（尤其：否定优先规则）；只需裁决本表所列个案。"],
        [""],
        ["背景（供了解）：本次验收四域总体 κ 均≥0.80 达标；仲裁仅针对少量个案与个别年份层："],
        ["  ecg_rate@2022 κ=0.793、ecg_other@2023 κ=0.661、main_discrepant@ABDUS_H 2022/2023 层、"],
        ["  echo_lvh 与 echo_la_dilate（F1<0.90）。"],
    ]
    for r in lines:
        ws.append(r)
    ws["A1"].font = Font(bold=True, size=14)
    ws.column_dimensions["A"].width = 110
    for row in ws.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    # ---- 各域 sheet ----
    for sheet in ["ECG_H", "ECHO_PG", "ABDUS_PG", "ABDUS_H"]:
        sub = q[q["sheet"] == sheet]
        ws = wb.create_sheet(sheet)
        ws.append(ZH_HEAD)
        for c in ws[1]:
            c.font = Font(bold=True)
            c.fill = PatternFill("solid", fgColor="DDEBF7")
        for _, r in sub.iterrows():
            ws.append([("不一致" if r["kind"] == "discordant" else "flag复核"),
                       r["variable"], r["sample_id"], r["time"], r["text"],
                       r["A1"], r["A2"], r["flag"], r["note"], "", "", ""])
        ws.column_dimensions["E"].width = 70
        for col, w in {"A": 9, "B": 16, "C": 12, "D": 12, "F": 8, "G": 8, "H": 6,
                       "I": 26, "J": 16, "K": 30, "L": 12}.items():
            ws.column_dimensions[col].width = w
        for row in ws.iter_rows(min_row=2):
            for c in row:
                c.alignment = Alignment(wrap_text=True, vertical="top")
        ws.freeze_panes = "A2"
        # 枚举下拉（按变量应用于对应行；flag行不加约束）
        for var, opts in ENUM.items():
            rows = [i + 2 for i, v in enumerate(sub["variable"]) if v == var]
            if rows:
                dv = DataValidation(type="list", formula1='"' + ",".join(opts) + '"',
                                    allow_blank=True, showErrorMessage=True)
                ws.add_data_validation(dv)
                for i in rows:
                    dv.add(ws.cell(row=i, column=10))
        bin_vars = [v for v in sub["variable"].unique() if v and v not in ENUM]
        if bin_vars:
            dv = DataValidation(type="list", formula1='"0,1"', allow_blank=True,
                                showErrorMessage=True)
            ws.add_data_validation(dv)
            for i, v in enumerate(sub["variable"]):
                if v in bin_vars:
                    dv.add(ws.cell(row=i + 2, column=10))
        dv_rev = DataValidation(type="list", formula1='"是,否"', allow_blank=True)
        ws.add_data_validation(dv_rev)
        dv_rev.add(f"L2:L{len(sub) + 1}")

    wb.save(OUT)
    n_disc = (q["kind"] == "discordant").sum()
    n_flag = (q["kind"] == "flag").sum()
    print(f"仲裁工作簿 -> {OUT}")
    print(f"不一致 {n_disc} 条 + flag复核 {n_flag} 条；sheet：说明 + 四域")
    # 回读验证
    chk = pd.ExcelFile(OUT)
    print("回读sheet：", chk.sheet_names,
          {s: chk.parse(s).shape for s in chk.sheet_names if s != "说明"})


if __name__ == "__main__":
    sys.exit(main())
