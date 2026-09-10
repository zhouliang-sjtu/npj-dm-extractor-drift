# -*- coding: utf-8 -*-
"""17_make_relabel_workbook.py —— C方案：echo_lvh / echo_la_dilate 依手册v2重标工作簿
来源：data/金标准标注工作簿_终版.xlsx 的 ECHO_PG（仅取 sample_id/exam_date/text，盲法不带旧值）
输出：10_expert-consultation/07_重标工作簿_ECHO两变量.xlsx（说明sheet + 重标sheet，0/1下拉）
"""
import os
import sys

import pandas as pd
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.utils import get_column_letter

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "data", "金标准标注工作簿_终版.xlsx")
OUT = os.path.join(ROOT, "10_expert-consultation", "07_重标工作簿_ECHO两变量.xlsx")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    df = pd.read_excel(SRC, sheet_name="ECHO_PG", dtype=str)
    out = pd.DataFrame({
        "sample_id": df["sample_id"],
        "exam_date": df["exam_date"],
        "text": df["text"],
        "A1_echo_lvh": "", "A1_echo_la_dilate": "",
        "A2_echo_lvh": "", "A2_echo_la_dilate": "",
        "flag": "", "note": "",
    })

    wb = pd.ExcelWriter(OUT, engine="openpyxl")
    out.to_excel(wb, sheet_name="ECHO_PG重标", index=False)
    wb.close()

    import openpyxl
    book = openpyxl.load_workbook(OUT)
    ws = book["ECHO_PG重标"]

    ins = book.create_sheet("说明", 0)
    lines = [
        ["重标工作簿填写说明（v2.0）"],
        [""],
        ["范围：ECHO_PG 全 300 份，仅重标 echo_lvh（左室肥厚）与 echo_la_dilate（左房增大）两个变量。"],
        ["依据：首轮双标注分歧集中于边界值（=12mm/=40mm），经仲裁明确『阈值含等于』；本重标依《02_标注手册》v2.0 执行。"],
        [""],
        ["填写：A1 与 A2 各自独立填写自己的 4 列（0 或 1），不得互相参考、不得参考首轮结果（盲法）。"],
        ["  · 室间隔或左室后壁厚度 ≥12mm（含等于）或明确『增厚』 → echo_lvh=1"],
        ["  · 左房内径 ≥40mm（含等于，前后径/上下径任一达阈值）或明确『增大/扩大』 → echo_la_dilate=1"],
        ["  · 规则未覆盖 → flag=1 + note 一句话"],
        ["  · 勿改 sample_id / exam_date / text；勿增删行。"],
        [""],
        ["回收：本表与自重复标注记录同批交回（recycle/）。"],
    ]
    for r in lines:
        ins.append(r)
    ins["A1"].font = Font(bold=True, size=14)
    ins.column_dimensions["A"].width = 100
    for row in ins.iter_rows():
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")

    for c in ws[1]:
        c.font = Font(bold=True)
        c.fill = PatternFill("solid", fgColor="DDEBF7")
    ws.column_dimensions["C"].width = 70
    for col in ("D", "E", "F", "G"):
        ws.column_dimensions[col].width = 14
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical="top")
    ws.freeze_panes = "A2"
    dv = DataValidation(type="list", formula1='"0,1"', allow_blank=True, showErrorMessage=True)
    ws.add_data_validation(dv)
    dv.add(f"D2:E{len(out) + 1}")
    dv.add(f"F2:G{len(out) + 1}")
    book.save(OUT)
    print(f"重标工作簿 -> {OUT}（{len(out)} 行 × 4 个填写列）")
    chk = pd.ExcelFile(OUT)
    print("回读：", chk.sheet_names, chk.parse("ECHO_PG重标", nrows=2).columns.tolist())


if __name__ == "__main__":
    sys.exit(main())
