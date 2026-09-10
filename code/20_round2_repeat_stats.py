# -*- coding: utf-8 -*-
"""20_round2_repeat_stats.py —— 第二轮重复盲标（重标 + 自重复）核验、统计与终版合并
输入：
  回收  10_expert-consultation/recycle/03-第二轮2人重复盲标结果/
        - 重标工作簿_ECHO两变量_A1A2标注完成.xlsx（ECHO_PG重标 300 行，A1/A2 × lvh/la_dilate，依手册 v2.0）
        - 自重复标注任务包_A1A2标注完成.xlsx（4 域 sheet，A1/A2 全变量，依手册 v2.0）
  首轮  10_expert-consultation/recycle/01-第一轮2人盲标结果/金标准标注工作簿.xlsx（A1/A2 首轮本人值）
  任务包 10_expert-consultation/dataset/03-第二轮2人重复盲标/自重复标注任务包.xlsx（原样核验源）
  终版  data/金标准标注工作簿_终版.xlsx
功能：
  A 核验（第二轮登记表清单的自动项）：行数 / sample_id·text 原样 / 取值合法 / 逻辑 / flag 配套 / 填写完整率
  B 重标一致性（v2.0）：A1 vs A2 κ / Gwet AC1 / F1_pos（echo_lvh、echo_la_dilate），对照首轮基线；残余分歧清单
  C 自重复一致性：各域各变量各标注员 第2轮 vs 首轮本人值 κ/AC1；变化计数（标注 v2.0 规则修订涉及变量）
  D ECHO 嵌套 30 份：lvh / la_dilate 两次 v2.0 判定（重标 vs 自重复，间隔≥3 天）组内 κ
  E --apply：重标值合并进终版 ECHO_PG（替换 4 列），重算 per-variable 终值，输出终值解析表与仲裁队列
输出（results/）：
  round2_relabel_agreement.csv / round2_relabel_disagreements.csv / round2_selfrepeat_intra.csv
  round2_changed_cases.csv / round2_echo_nested_intra.csv
  round2_final_resolution.csv / round2_arbitration_queue.csv（--apply 时）
用法：python code/20_round2_repeat_stats.py [--apply]
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R2 = os.path.join(ROOT, "10_expert-consultation", "recycle", "03-第二轮2人重复盲标结果")
RELABEL = os.path.join(R2, "重标工作簿_ECHO两变量_A1A2标注完成.xlsx")
SELFREP = os.path.join(R2, "自重复标注任务包_A1A2标注完成.xlsx")
TASKPKG = os.path.join(ROOT, "10_expert-consultation", "dataset", "03-第二轮2人重复盲标",
                       "自重复标注任务包.xlsx")
ROUND1 = os.path.join(ROOT, "10_expert-consultation", "recycle", "01-第一轮2人盲标结果",
                      "金标准标注工作簿.xlsx")
FINAL = os.path.join(ROOT, "data", "金标准标注工作簿_终版.xlsx")
RES = os.path.join(ROOT, "results")

BINARY = {  # 各域二值变量（ef_value 为数值列、reflux_grade/us_fatty_degree 为多分类，另行处理）
    "ECG_H": ["ecg_normal", "ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock", "ecg_bbb",
              "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave_mi", "ecg_other", "ecg_unreadable"],
    "ECHO_PG": ["echo_normal", "echo_variant", "echo_lvh", "echo_la_dilate", "ef_abnormal",
                "echo_rhythm", "echo_unreadable"],
    "ABDUS_PG": ["us_fatty", "us_hepatic_other", "us_gallstone", "us_kidney_cyst",
                 "us_unreadable", "main_discrepant"],
    "ABDUS_H": ["us_fatty", "us_hepatic_other", "us_gallstone", "us_kidney_cyst",
                "us_unreadable", "main_discrepant"],
}
MULTI = {"ECHO_PG": {"ef_value": "numeric",
                     "reflux_grade": ["none", "trace_mild", "moderate", "severe"]},
         "ABDUS_PG": {"us_fatty_degree": ["轻", "中", "重"]},
         "ABDUS_H": {"us_fatty_degree": ["轻", "中", "重"]}}
# 手册 v2.0 修订涉及的变量（自重复 vs 首轮对比时，其变化可能为规则修订驱动的合理变化）
V2_AFFECTED = {"ecg_rate", "ecg_other", "echo_normal", "echo_lvh", "echo_la_dilate",
               "us_hepatic_other", "main_discrepant"}
# 首轮已仲裁的 ECHO 变量（仲裁规则=阈值含等于，与 v2.0 一致，可作残余分歧的既有裁决）
ARB1_VARS = {"ECHO_PG": {"echo_lvh", "echo_la_dilate"}}


def blank(s):
    return s.isna() | (s.astype(str).str.strip() == "")


def norm_col(s):
    return (s.astype(str).str.strip()
            .replace({"": np.nan, "nan": np.nan, "None": np.nan, "NaN": np.nan}))


def norm_text(s):
    """Excel 往返会把 \r 转义为字面 _x000D_，统一反转义 + 换行归一后比对"""
    s = "" if pd.isna(s) else str(s).replace("_x000D_", "\r")
    return s.replace("\r\n", "\n").replace("\r", "\n").strip()


def kappa(a, b):
    """Cohen's κ（a,b 已对齐且非空）"""
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in labels)
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0, po


def gwet_ac1(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pi = [(sum(1 for x in a if x == L) + sum(1 for y in b if y == L)) / (2 * n) for L in labels]
    pe = sum(p * (1 - p) for p in pi) / (len(labels) - 1) if len(labels) > 1 else 0.0
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0, po


def f1_pos(a, b, cls="1"):
    tp = sum(1 for x, y in zip(a, b) if x == cls and y == cls)
    fp = sum(1 for x, y in zip(a, b) if x != cls and y == cls)
    fn = sum(1 for x, y in zip(a, b) if x == cls and y != cls)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return 2 * prec * rec / (prec + rec) if prec + rec else 0.0


def sec(t):
    print("\n" + "=" * 96 + f"\n{t}\n" + "=" * 96)


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    apply_mode = "--apply" in sys.argv
    os.makedirs(RES, exist_ok=True)

    # ============================== A 核验 ==============================
    sec("A. 第二轮回收数据核验（行数/原样/取值/逻辑/flag配套/完整率）")
    problems = []

    # A1 重标工作簿 vs 终版 ECHO_PG 源
    rl = pd.read_excel(RELABEL, sheet_name="ECHO_PG重标", dtype=str)
    fin = pd.read_excel(FINAL, sheet_name="ECHO_PG", dtype=str)
    if len(rl) != 300:
        problems.append(f"重标行数 {len(rl)} ≠ 300")
    m = rl.merge(fin[["sample_id", "exam_date", "text"]], on="sample_id", how="left",
                 suffixes=("", "_src"), indicator=True)
    if (m["_merge"] != "both").any():
        problems.append(f"重标 sample_id 与终版不匹配 {(m['_merge'] != 'both').sum()} 条")
    bad_text = sum(norm_text(x) != norm_text(y) for x, y in zip(m["text"], m["text_src"]))
    bad_date = (m["exam_date"].fillna("") != m["exam_date_src"].fillna("")).sum()
    if bad_text or bad_date:
        problems.append(f"重标 text 原样不符 {bad_text} 条 / exam_date 不符 {bad_date} 条")
    for c in ["A1_echo_lvh", "A1_echo_la_dilate", "A2_echo_lvh", "A2_echo_la_dilate"]:
        bad = int((~blank(rl[c]) & ~rl[c].isin(["0", "1"])).sum())
        n_bl = int(blank(rl[c]).sum())
        if bad:
            problems.append(f"重标 {c} 非法取值 {bad} 条")
        if n_bl:
            problems.append(f"重标 {c} 空缺 {n_bl} 条")
    flg = rl["flag"].astype(str).str.strip()
    bad_flag = int(((flg == "1") & blank(rl["note"])).sum())
    if bad_flag:
        problems.append(f"重标 flag=1 但 note 空 {bad_flag} 条")
    print(f"重标：{len(rl)} 行，text 原样不符 {bad_text}（0=反转义归一后一致），exam_date 不符 {bad_date}，"
          f"四填写列空缺 "
          f"{[int(blank(rl[c]).sum()) for c in ['A1_echo_lvh','A1_echo_la_dilate','A2_echo_lvh','A2_echo_la_dilate']]}，"
          f"flag=1 共 {(flg == '1').sum()} 条（note 配套缺失 {bad_flag}）")

    # A2 自重复各 sheet vs 任务包源
    sr = pd.read_excel(SELFREP, sheet_name=None, dtype=str)
    tp = pd.read_excel(TASKPKG, sheet_name=None, dtype=str)
    sr_sheets = ["ECG_H自重复", "ECHO_PG自重复", "ABDUS_PG自重复", "ABDUS_H自重复"]
    expect_n = {"ECG_H自重复": 57, "ECHO_PG自重复": 30, "ABDUS_PG自重复": 30, "ABDUS_H自重复": 30}
    for sh in sr_sheets:
        d, t = sr[sh], tp[sh]
        dom = sh.replace("自重复", "")
        if len(d) != expect_n[sh]:
            problems.append(f"{sh} 行数 {len(d)} ≠ {expect_n[sh]}")
        keycols = [c for c in ["year", "exam_date", "pseudo_id", "text"] if c in t.columns]
        j = d.merge(t[["sample_id"] + keycols], on="sample_id", how="left",
                    suffixes=("", "_src"), indicator=True)
        if (j["_merge"] != "both").any():
            problems.append(f"{sh} sample_id 与任务包不匹配 {(j['_merge'] != 'both').sum()} 条")
        for c in keycols:
            if c == "text":
                nb = sum(norm_text(x) != norm_text(y) for x, y in zip(j[c], j[c + "_src"]))
            else:
                nb = int((j[c].fillna("") != j[c + "_src"].fillna("")).sum())
            if nb:
                problems.append(f"{sh} {c} 原样不符 {nb} 条")
        # 完整性观察：us_fatty=1 但 degree 留空（表单说明允许留空，仅登记不判失败）
        if "us_fatty_degree" in d.columns:
            for r in ("A1", "A2"):
                obs = int(((d[f"{r}_us_fatty"] == "1") & blank(d[f"{r}_us_fatty_degree"])).sum())
                if obs:
                    print(f"  [观察] {sh} {r}: us_fatty=1 但 us_fatty_degree 留空 {obs} 条"
                          f"（表单说明允许，第二轮系统性留空）")
        cols = [c for c in d.columns if c.startswith(("A1_", "A2_"))]
        for c in cols:
            var = c.split("_", 1)[1]
            if var in BINARY[dom]:
                bad = int((~blank(d[c]) & ~d[c].isin(["0", "1"])).sum())
            elif var == "reflux_grade":
                bad = int((~blank(d[c]) & ~d[c].isin(MULTI["ECHO_PG"]["reflux_grade"])).sum())
            elif var == "us_fatty_degree":
                bad = int((~blank(d[c]) & ~d[c].isin(MULTI["ABDUS_PG"]["us_fatty_degree"])).sum())
            elif var == "ef_value":
                bad = int((~blank(d[c]) & pd.to_numeric(norm_col(d[c]), errors="coerce").isna()).sum())
            else:
                bad = 0
            if bad:
                problems.append(f"{sh} {c} 非法取值 {bad} 条")
        bad_flag = int(((d["flag"].astype(str).str.strip() == "1") & blank(d["note"])).sum())
        if bad_flag:
            problems.append(f"{sh} flag=1 但 note 空 {bad_flag} 条")
        lo = min(int((~blank(d[c])).sum()) for c in cols)
        print(f"{sh}: {len(d)} 行原样一致；A1/A2 列填写最少 {lo}/{len(d)}；flag=1 共 "
              f"{(d['flag'].astype(str).str.strip() == '1').sum()} 条（note 缺失 {bad_flag}）")

    # A3 逻辑一致性：ef_abnormal=1 当且仅当 ef_value<50（ef_value 可解析时）
    de = sr["ECHO_PG自重复"]
    for r in ("A1", "A2"):
        ef = pd.to_numeric(norm_col(de[f"{r}_ef_value"]), errors="coerce")
        ab = de[f"{r}_ef_abnormal"]
        ok = ef.notna() & (~blank(ab))
        mism = int((ab[ok] != (ef[ok] < 50).astype(int).astype(str)).sum())
        if mism:
            problems.append(f"ECHO自重复 {r}: ef_abnormal 与 ef_value<50 不一致 {mism} 条")
        print(f"ECHO自重复 {r}: ef_value 可解析 {int(ok.sum())} 条，逻辑不一致 {mism} 条")

    if problems:
        print("\n【核验未过】")
        for p in problems:
            print("  -", p)
    else:
        print("\n【核验通过】行数、原样、取值合法、逻辑、flag 配套全部通过")

    # ============================== B 重标一致性 ==============================
    sec("B. 重标一致性（v2.0，A1 vs A2，n=300）—— 对照首轮基线")
    base = {"echo_lvh": (0.832, 0.977, 0.842), "echo_la_dilate": (0.814, 0.964, 0.830)}
    rows, disagree_rows = [], []
    for var in ["echo_lvh", "echo_la_dilate"]:
        a, b = norm_col(rl["A1_" + var]), norm_col(rl["A2_" + var])
        d = pd.DataFrame({"a": a, "b": b}).dropna()
        k, po = kappa(d["a"].tolist(), d["b"].tolist())
        ac1, _ = gwet_ac1(d["a"].tolist(), d["b"].tolist())
        f1 = f1_pos(d["a"].tolist(), d["b"].tolist())
        dis = rl[(a != b) & a.notna() & b.notna()]
        n1a, n1b = int((d["a"] == "1").sum()), int((d["b"] == "1").sum())
        rows.append(dict(variable=var, n=len(d), raw_agreement=round(po, 3),
                         cohen_kappa=round(k, 3), gwet_ac1=round(ac1, 3), F1_pos=round(f1, 3),
                         A1_pos=n1a, A2_pos=n1b, disagree=len(dis),
                         kappa_round1=base[var][0], ac1_round1=base[var][1],
                         F1pos_round1=base[var][2]))
        for _, r in dis.iterrows():
            disagree_rows.append(dict(variable=var, sample_id=r["sample_id"],
                                      A1=r["A1_" + var], A2=r["A2_" + var],
                                      flag=r["flag"], note=r["note"]))
        print(f"{var}: κ={k:.3f}（首轮 {base[var][0]}）  AC1={ac1:.3f}（首轮 {base[var][1]}）  "
              f"F1_pos={f1:.3f}（首轮 {base[var][2]}）  A1阳性 {n1a} / A2阳性 {n1b} / 分歧 {len(dis)}")
    pd.DataFrame(rows).to_csv(os.path.join(RES, "round2_relabel_agreement.csv"),
                              index=False, encoding="utf-8-sig")
    if disagree_rows:
        dis_df = pd.DataFrame(disagree_rows)
        print("\n残余分歧清单：")
        print(dis_df.to_string(index=False))
        dis_df.to_csv(os.path.join(RES, "round2_relabel_disagreements.csv"), index=False,
                      encoding="utf-8-sig")

    # ============================== C 自重复一致性 ==============================
    sec("C. 自重复一致性（第2轮 vs 首轮本人值；间隔≥3天）")
    r1 = pd.ExcelFile(ROUND1)
    intra_rows, changed_cases = [], []
    for sh in sr_sheets:
        dom = sh.replace("自重复", "")
        d, g = sr[sh], r1.parse(dom, dtype=str)
        vars_all = BINARY[dom] + list(MULTI.get(dom, {}))
        gidx = g.set_index("sample_id")
        for var in vars_all:
            for rater in ("A1", "A2"):
                new = norm_col(d[f"{rater}_{var}"])
                old = gidx.loc[d["sample_id"], f"{rater}_{var}"].reset_index(drop=True)
                old = norm_col(old)
                dd = pd.DataFrame({"new": new, "old": old}).dropna()
                if len(dd) < 5:
                    continue
                k, po = kappa(dd["new"].tolist(), dd["old"].tolist())
                ac1, _ = gwet_ac1(dd["new"].tolist(), dd["old"].tolist())
                chg = int((dd["new"] != dd["old"]).sum())
                intra_rows.append(dict(domain=dom, variable=var, rater=rater, n=len(dd),
                                       raw_agreement=round(po, 3), cohen_kappa=round(k, 3),
                                       gwet_ac1=round(ac1, 3), changed=chg,
                                       v2_affected=var in V2_AFFECTED))
                ch = dd[dd["new"] != dd["old"]]
                for i in ch.index:
                    changed_cases.append(dict(domain=dom, variable=var, rater=rater,
                                              sample_id=d.at[i, "sample_id"],
                                              round1=dd.at[i, "old"], round2=dd.at[i, "new"],
                                              v2_affected=var in V2_AFFECTED,
                                              flag=d.at[i, "flag"], note=d.at[i, "note"]))
    intra = pd.DataFrame(intra_rows)
    intra.to_csv(os.path.join(RES, "round2_selfrepeat_intra.csv"), index=False, encoding="utf-8-sig")
    chg = pd.DataFrame(changed_cases)
    chg.to_csv(os.path.join(RES, "round2_changed_cases.csv"), index=False, encoding="utf-8-sig")
    print(intra.to_string(index=False))
    ks = intra["cohen_kappa"].dropna()
    print(f"\nκ 汇总：变量×标注员共 {len(ks)} 组；κ≥0.85 {(ks >= 0.85).sum()} 组（{(ks >= 0.85).mean():.0%}），"
          f"最低 {ks.min():.3f}，中位 {ks.median():.3f}；raw_agreement≥0.90 "
          f"{(intra['raw_agreement'] >= 0.90).sum()}/{len(intra)} 组")
    low = intra[intra["cohen_kappa"] < 0.85]
    if len(low):
        print("\nκ<0.85 的组（变化集中于 v2.0 修订涉及变量与稀有阳性变量，见 v2_affected 列）：")
        print(low.to_string(index=False))
    if len(chg):
        nv2 = int(chg["v2_affected"].sum())
        print(f"\n变化个案共 {len(chg)} 条 → results/round2_changed_cases.csv；"
              f"其中 v2.0 修订涉及变量 {nv2} 条、非修订变量 {len(chg) - nv2} 条")

    # ============================== D ECHO 嵌套 30 份 ==============================
    sec("D. ECHO 嵌套 30 份：lvh / la_dilate 两次 v2.0 判定（重标 vs 自重复）组内一致性")
    rows = []
    for var in ["echo_lvh", "echo_la_dilate"]:
        for rater in ("A1", "A2"):
            a = norm_col(rl.set_index("sample_id").loc[sr["ECHO_PG自重复"]["sample_id"],
                                                       f"{rater}_{var}"]).reset_index(drop=True)
            b = norm_col(sr["ECHO_PG自重复"][f"{rater}_{var}"])
            dd = pd.DataFrame({"a": a, "b": b}).dropna()
            k, po = kappa(dd["a"].tolist(), dd["b"].tolist())
            rows.append(dict(variable=var, rater=rater, n=len(dd), raw_agreement=round(po, 3),
                             cohen_kappa=round(k, 3),
                             changed=int((dd["a"] != dd["b"]).sum())))
    nest = pd.DataFrame(rows)
    nest.to_csv(os.path.join(RES, "round2_echo_nested_intra.csv"), index=False, encoding="utf-8-sig")
    print(nest.to_string(index=False))

    # ============================== E 合并（--apply） ==============================
    if not apply_mode:
        print("\n[dry-run] 未写入终版；加 --apply 执行合并")
        return 0
    sec("E. 合并重标值进终版 ECHO_PG")
    book = pd.ExcelFile(FINAL)
    e = book.parse("ECHO_PG", dtype=str)
    rli = rl.set_index("sample_id")
    # 首轮仲裁集合（ECHO 两变量）：来自 results/arbitration_decisions.csv
    arb1 = pd.read_csv(os.path.join(RES, "arbitration_decisions.csv"), dtype=str)
    arb1_map = {(r["sample_id"], r["variable"]): r["final"]
                for _, r in arb1.iterrows()
                if r["sheet"] == "ECHO_PG" and r["variable"] in ARB1_VARS["ECHO_PG"]}
    # 第二轮仲裁已决案件（仲裁终值登记后存在，见 results/round2_arbitration_decisions_round2.csv）
    arb2_path = os.path.join(RES, "round2_arbitration_decisions_round2.csv")
    arb2_map = {}
    if os.path.exists(arb2_path):
        a2df = pd.read_csv(arb2_path, dtype=str)
        arb2_map = {(r["sample_id"], r["variable"]): r["decision"] for _, r in a2df.iterrows()}
        print(f"已载入第二轮仲裁终值 {len(arb2_map)} 例：{sorted(arb2_map)}")
    res_rows, n_arb_reuse, n_arb2, n_pending = [], 0, 0, 0
    for i in e.index:
        sid = e.at[i, "sample_id"]
        for var in ["echo_lvh", "echo_la_dilate"]:
            e.at[i, "A1_" + var] = rli.at[sid, "A1_" + var]
            e.at[i, "A2_" + var] = rli.at[sid, "A2_" + var]
        pairs = [("echo_lvh", e.at[i, "A1_echo_lvh"], e.at[i, "A2_echo_lvh"]),
                 ("echo_la_dilate", e.at[i, "A1_echo_la_dilate"], e.at[i, "A2_echo_la_dilate"])]
        # per-variable 终值解析：共识 → 首轮仲裁（规则同 v2.0）→ 第二轮仲裁 → 待仲裁
        for var, x, y in pairs:
            if x == y:
                fin_v, src = x, "consensus_v2"
            elif (sid, var) in arb1_map:
                fin_v, src = arb1_map[(sid, var)], "arbitration_round1(v2.0同规则)"
                n_arb_reuse += 1
            elif (sid, var) in arb2_map:
                fin_v, src = arb2_map[(sid, var)], "arbitration_round2"
                n_arb2 += 1
            else:
                fin_v, src = "", "pending_arbitration"
                n_pending += 1
            res_rows.append(dict(sheet="ECHO_PG", sample_id=sid, variable=var,
                                 A1=x, A2=y, final=fin_v, source=src))
        # 仲裁列：共识 → 空；经仲裁 → 记录终值（每行至多一个仲裁变量）
        arb_vals = [r["final"] for r in res_rows[-2:] if r["source"].startswith("arbitration")]
        if len(arb_vals) > 1:
            print(f"【警告】{sid} 行有两个仲裁变量，仲裁列仅能记录第一个")
        e.at[i, "arbitration"] = arb_vals[0] if arb_vals else ""
    resdf = pd.DataFrame(res_rows)
    # 终值变化统计：重标后终值 vs 首轮终值（首轮终值=A1 if A1==A2 else 仲裁）
    g1 = book.parse("ECHO_PG", dtype=str).set_index("sample_id")
    for var in ["echo_lvh", "echo_la_dilate"]:
        old_final = np.where(g1["A1_" + var] == g1["A2_" + var], g1["A1_" + var],
                             g1["arbitration"].fillna(""))
        new_final = resdf[resdf.variable == var].set_index("sample_id")["final"].fillna("")
        both = pd.DataFrame({"old": old_final, "new": new_final}).dropna()
        n_flip_pos = int(((both["old"] == "0") & (both["new"] == "1")).sum())
        n_flip_neg = int(((both["old"] == "1") & (both["new"] == "0")).sum())
        print(f"{var}: 患病率 首轮终值 {(both['old'] == '1').sum()}/300 → "
              f"重标后 {(both['new'] == '1').sum()}/300（0→1 {n_flip_pos} 例，1→0 {n_flip_neg} 例）")
    # 写回终版：全部 sheet 先入内存 -> 写临时文件 -> 验证 -> 原子替换
    # （不得在 ExcelWriter 打开同一文件后再 book.parse()：ExcelFile 为懒加载流式读取，
    #   writer 创建即截断文件，后续 parse 会读到空文件并损坏终版——已实测踩坑）
    sheets = {sh: (e if sh == "ECHO_PG" else book.parse(sh, dtype=str)) for sh in book.sheet_names}
    book.close()  # 释放 FINAL 读句柄，否则 os.replace 目标被占用
    tmp = FINAL[:-5] + ".tmp.xlsx"  # pandas 要求 .xlsx 后缀
    with pd.ExcelWriter(tmp, engine="openpyxl") as w:
        for sh, df in sheets.items():
            df.to_excel(w, sheet_name=sh, index=False)
    with pd.ExcelFile(tmp, engine="openpyxl") as chk:
        assert chk.sheet_names == list(sheets), "临时文件 sheet 不一致"
        assert len(chk.parse("ECHO_PG", dtype=str)) == 300, "临时文件 ECHO_PG 行数异常"
    os.replace(tmp, FINAL)
    resdf.to_csv(os.path.join(RES, "round2_final_resolution.csv"), index=False, encoding="utf-8-sig")
    pend = resdf[resdf["source"] == "pending_arbitration"]
    pend.to_csv(os.path.join(RES, "round2_arbitration_queue.csv"), index=False, encoding="utf-8-sig")
    print(f"\n终版已更新 -> {FINAL}")
    print(f"终值解析表 -> {os.path.join(RES, 'round2_final_resolution.csv')}；"
          f"沿用首轮仲裁 {n_arb_reuse} 例，第二轮仲裁 {n_arb2} 例，待仲裁 {n_pending} 例")
    if n_pending:
        print("【注意】重标后新分歧且无既有仲裁 → results/round2_arbitration_queue.csv，需仲裁后终值才完整")
    else:
        print("【M1】ECHO 两变量终值全部就绪（共识+仲裁），无待仲裁案件")

    # ---- F 合并后验收：A1/A2 vs 终值（门槛 F1_pos>=0.90、acc>=0.95、分年份层 acc>=0.90）----
    sec("F. 合并后验收（ECHO_PG 两变量，重标口径）")
    final_check = pd.ExcelFile(FINAL)
    fe = final_check.parse("ECHO_PG", dtype=str)
    final_check.close()
    yr = fe["exam_date"].astype(str).str[:4]
    acc_rows = []
    for var in ["echo_lvh", "echo_la_dilate"]:
        fin_map = resdf[resdf.variable == var].set_index("sample_id")["final"]
        fin_v = fe["sample_id"].map(fin_map)  # 按 sample_id 对齐到 fe 行索引
        for rater in ("A1", "A2"):
            r = fe[f"{rater}_{var}"]
            m = fin_v.notna() & (fin_v.astype(str).str.strip() != "")
            acc = float(np.mean(r[m] == fin_v[m]))
            f1 = f1_pos(r[m].tolist(), fin_v[m].tolist())
            acc_rows.append(dict(variable=var, comparison=f"{rater}_vs_final",
                                 n=int(m.sum()), accuracy=round(acc, 3), F1_pos=round(f1, 3)))
            for y in sorted(yr[m].unique()):
                mm = m & (yr == y)
                acc_rows.append(dict(variable=var, comparison=f"{rater}_vs_final@{y}",
                                     n=int(mm.sum()),
                                     accuracy=round(float(np.mean(r[mm] == fin_v[mm])), 3),
                                     F1_pos=""))
    acc_df = pd.DataFrame(acc_rows)
    acc_df.to_csv(os.path.join(RES, "round2_postmerge_acceptance.csv"), index=False,
                  encoding="utf-8-sig")
    print(acc_df.to_string(index=False))
    bad = acc_df[(acc_df["accuracy"] < 0.95)
                 | (acc_df["F1_pos"].apply(lambda x: x != "" and x < 0.90))]
    bad_layer = acc_df[acc_df["comparison"].str.contains("@") & (acc_df["accuracy"] < 0.90)]
    print("\n【通过】合并后验收全部达标"
          if not len(bad) and not len(bad_layer) else
          f"\n【未达标】总体: {', '.join(bad['comparison'])}; 层: {', '.join(bad_layer['comparison'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
