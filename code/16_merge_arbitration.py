# -*- coding: utf-8 -*-
"""16_merge_arbitration.py —— M1e 仲裁终值回填与验收
步骤：
  1) 校验仲裁结果工作簿（裁定必填/枚举合法/A1A2与原工作簿一致）
  2) 不一致34条：终值回填 gold 工作簿 arbitration 列 -> data/gold_annotation_workbook_final.xlsx
     flag行：裁定列不写入终版，处理意见导出 results/arbitration_flag_decisions.csv
  3) 验收统计：A1/A2 各自 vs 仲裁终版 F1 与准确率（总体+分年份），对照门槛 F1>=0.90、acc>=95%、层acc>=90%
用法：python code/16_merge_arbitration.py [--apply]
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARB = os.path.join(ROOT, "10_expert-consultation", "recycle", "仲裁结果工作簿_20260903.xlsx")
GOLD = os.path.join(ROOT, "10_expert-consultation", "recycle", "金标准标注工作簿.xlsx")
GOLD_FINAL = os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx")
RES = os.path.join(ROOT, "results")

ENUM = {"us_fatty_degree": ["轻", "中", "重"],
        "reflux_grade": ["none", "trace_mild", "moderate", "severe"]}
SHEETS = ["ECG_H", "ECHO_PG", "ABDUS_PG", "ABDUS_H"]


def blank(s):
    return s.isna() | (s.astype(str).str.strip() == "")


def f1_acc(a, b, cls=None):
    a, b = list(a), list(b)
    if cls is None:
        acc = np.mean([x == y for x, y in zip(a, b)])
        return acc, acc, acc  # 二值总体：prec=rec=f1=acc 的近似不适用，仅返回acc
    tp = sum(1 for x, y in zip(a, b) if x == cls and y == cls)
    fp = sum(1 for x, y in zip(a, b) if x != cls and y == cls)
    fn = sum(1 for x, y in zip(a, b) if x == cls and y != cls)
    prec = tp / (tp + fp) if tp + fp else 0
    rec = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0
    return prec, rec, f1


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    apply_mode = "--apply" in sys.argv
    xl = pd.ExcelFile(ARB)
    print("sheet：", xl.sheet_names)

    # ---- 汇总 sheet 原样展示 ----
    if "汇总" in xl.sheet_names:
        print("\n===== 仲裁人汇总 sheet =====")
        print(xl.parse("汇总", header=None).fillna("").to_string(index=False, header=False))

    gold = pd.ExcelFile(GOLD)
    decisions, flag_rows, errs = [], [], []
    arb_map = {}  # (sheet, variable, sample_id) -> (裁定值, 理由, 手册需修订)
    for sheet in SHEETS:
        a = xl.parse(sheet, dtype=str)
        a.columns = [c.strip() for c in a.columns]
        g = gold.parse(sheet, dtype=str)
        tcol = "year" if "year" in g.columns else "exam_date"
        for i in a.index:
            kind = str(a.at[i, "类型"]).strip()
            var = str(a.at[i, "变量"]).strip()
            sid = str(a.at[i, "sample_id"]).strip()
            val = a.at[i, "仲裁裁定（必填）"]
            reason = "" if pd.isna(a.at[i, "裁定理由（一句话）"]) else str(a.at[i, "裁定理由（一句话）"])
            rev = "" if pd.isna(a.at[i, "手册需修订"]) else str(a.at[i, "手册需修订"]).strip() \
                if "手册需修订" in a.columns else ""
            if pd.isna(val) or not str(val).strip():
                errs.append(f"{sheet}/{sid}/{var}: 裁定为空")
                continue
            val = str(val).strip()
            if kind == "不一致":
                if var in ENUM and val not in ENUM[var]:
                    errs.append(f"{sheet}/{sid}/{var}: 裁定值'{val}'不在枚举{ENUM[var]}")
                    continue
                if var not in ENUM and val not in ("0", "1"):
                    errs.append(f"{sheet}/{sid}/{var}: 二值变量裁定值'{val}'非法")
                    continue
                # 与原工作簿核对 A1/A2
                gi = g.index[g["sample_id"].astype(str).str.strip() == sid]
                if len(gi) != 1:
                    errs.append(f"{sheet}/{sid}: 原工作簿定位失败")
                    continue
                gi = gi[0]
                a1o, a2o = g.at[gi, "A1_" + var], g.at[gi, "A2_" + var]
                if (str(a1o).strip() != str(a.at[i, "A1判定"]).strip()
                        or str(a2o).strip() != str(a.at[i, "A2判定"]).strip()):
                    errs.append(f"{sheet}/{sid}/{var}: A1/A2 与原工作簿不一致")
                    continue
                arb_map[(sheet, var, sid)] = (val, reason, rev)
                decisions.append(dict(sheet=sheet, variable=var, sample_id=sid, time=g.at[gi, tcol],
                                      A1=str(a1o).strip(), A2=str(a2o).strip(), final=val,
                                      reason=reason, manual_rev=rev))
            else:  # flag复核
                flag_rows.append(dict(sheet=sheet, sample_id=sid, variable=var, decision=val,
                                      reason=reason, manual_rev=rev, note=a.at[i, "A1/A2备注note"]))

    print(f"\n不一致裁定 {len(decisions)} 条，flag处理 {len(flag_rows)} 条")
    if errs:
        print("校验未过：")
        [print("  -", e) for e in errs]
        return 1
    print("校验通过：裁定无空缺、枚举合法、A1/A2与原工作簿一致")

    dq = pd.DataFrame(decisions)
    print("\n裁定倾向（vs A1）：")
    print((dq["final"] == dq["A1"]).value_counts().rename(
        {True: "维持A1", False: "非A1"}).to_string())
    print("\n手册需修订分布：", dq["manual_rev"].value_counts().to_dict(),
          "| flag行手册需修订：", pd.Series([r["manual_rev"] for r in flag_rows]).value_counts().to_dict())
    print("\n--- 裁定明细 ---")
    print(dq[["sheet", "variable", "sample_id", "A1", "A2", "final"]].to_string(index=False))

    print("\n--- flag 处理明细 ---")
    for r in flag_rows:
        print(f"  {r['sheet']}/{r['sample_id']} var={r['variable'] or '-'} "
              f"处理={r['decision']} 修订={r['manual_rev']} note={r['note']}")

    if not apply_mode:
        print("\n[dry-run] 未写入任何文件；加 --apply 执行回填与验收统计")
        return 0

    # ---- 回填终版 ----
    final_book = pd.ExcelFile(GOLD)
    n_hit = 0
    with pd.ExcelWriter(GOLD_FINAL, engine="openpyxl") as w:
        for sheet in SHEETS:
            g = final_book.parse(sheet, dtype=str)
            for (sh, var, sid), (val, _, _) in arb_map.items():
                if sh == sheet:
                    gi = g.index[g["sample_id"].astype(str).str.strip() == sid][0]
                    g.at[gi, "arbitration"] = val
                    n_hit += 1
            g.to_excel(w, sheet_name=sheet, index=False)
    print(f"\n终版工作簿 -> {GOLD_FINAL}（回填 {n_hit} 条 arbitration）")

    dq.to_csv(os.path.join(RES, "arbitration_decisions.csv"), index=False, encoding="utf-8-sig")
    pd.DataFrame(flag_rows).to_csv(os.path.join(RES, "arbitration_flag_decisions.csv"),
                                   index=False, encoding="utf-8-sig")

    # ---- 验收统计：A1/A2 vs 参考标准（全量口径：仲裁行用终值，其余用A1/A2共识）----
    final_book = pd.ExcelFile(GOLD_FINAL)
    rows = []
    for sheet in SHEETS:
        g = final_book.parse(sheet, dtype=str)
        tcol = "year" if "year" in g.columns else "exam_date"
        yr = g[tcol].astype(str).str[:4] if tcol in g.columns else None  # exam_date取年份
        vars_done = sorted({v for (sh, v, _) in arb_map if sh == sheet})
        for var in vars_done:
            arbcol = g["arbitration"].astype(str).str.strip()
            has_arb = g["arbitration"].notna() & (arbcol != "")
            final = g["A1_" + var].astype(str).str.strip().where(~has_arb, arbcol)
            for rater in ("A1", "A2"):
                r = g[f"{rater}_{var}"].astype(str).str.strip()
                m = ~blank(g[f"{rater}_{var}"]) & final.ne("") & final.notna()
                acc = np.mean(r[m] == final[m])
                _, _, f1p = f1_acc(r[m], final[m], "1")
                rows.append(dict(sheet=sheet, variable=var, comparison=f"{rater}_vs_final",
                                 n=int(m.sum()), accuracy=round(acc, 3), F1_pos=round(f1p, 3)))
                # 分年份层准确率（门槛>=0.90）
                if yr is not None:
                    for y in sorted(yr[m].unique()):
                        mm = m & (yr == y)
                        rows.append(dict(sheet=sheet, variable=var,
                                         comparison=f"{rater}_vs_final@{y}",
                                         n=int(mm.sum()),
                                         accuracy=round(np.mean(r[mm] == final[mm]), 3),
                                         F1_pos=""))
    acc_df = pd.DataFrame(rows)
    acc_df.to_csv(os.path.join(RES, "post_arbitration_acceptance.csv"), index=False,
                  encoding="utf-8-sig")
    print("\n===== 仲裁后验收（门槛：F1_pos>=0.90、accuracy>=0.95、层accuracy>=0.90）=====")
    print(acc_df.to_string(index=False))
    bad = acc_df[(acc_df["accuracy"] < 0.95)
                 | (acc_df["F1_pos"].apply(lambda x: x != "" and x < 0.90))]
    bad_layer = acc_df[acc_df["comparison"].str.contains("@") & (acc_df["accuracy"] < 0.90)]
    print("\n【未达标】" if len(bad) or len(bad_layer) else "【通过】仲裁后验收全部达标",
          ("; 总体:" + ",".join(bad["comparison"] + "/" + bad["variable"]) if len(bad) else ""),
          ("; 层:" + ",".join(bad_layer["comparison"] + "/" + bad_layer["variable"]) if len(bad_layer) else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
