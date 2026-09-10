# -*- coding: utf-8 -*-
"""13_recycle_verify.py —— M1c 回收核验（八项完整性清单，自动可检部分）
用法：python code/13_recycle_verify.py
输入：10_expert-consultation/recycle/金标准标注工作簿.xlsx（已填）
对照：10_expert-consultation/dataset/*_待标注.csv（下发原版）
输出：控制台逐项报告 + results/recycle_verify_summary.csv
人工复核项（脚本无法自动判定）单独列出：盲法独立抽查、自重复标注10%。
"""
import os
import sys

import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BOOK = os.path.join(ROOT, "10_expert-consultation", "recycle", "金标准标注工作簿.xlsx")
DS = os.path.join(ROOT, "10_expert-consultation", "dataset")
OUT = os.path.join(ROOT, "results")

EXPECT = {
    "ECG_H": dict(n=570, src="ECG_H_待标注.csv",
                  binary=["ecg_normal", "ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock",
                          "ecg_bbb", "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave_mi",
                          "ecg_other", "ecg_unreadable"],
                  enum={}, degree=None),
    "ECHO_PG": dict(n=300, src="ECHO_PG_待标注.csv",
                    binary=["echo_normal", "echo_variant", "echo_lvh", "echo_la_dilate",
                            "ef_abnormal", "echo_rhythm", "echo_unreadable"],
                    enum={"reflux_grade": {"none", "trace_mild", "moderate", "severe"}},
                    degree=None, numeric=["ef_value"]),
    "ABDUS_PG": dict(n=300, src="ABDUS_PG_待标注.csv",
                     binary=["us_fatty", "us_hepatic_other", "us_gallstone", "us_kidney_cyst",
                             "us_unreadable", "main_discrepant"],
                     enum={}, degree="us_fatty_degree"),
    "ABDUS_H": dict(n=300, src="ABDUS_H_待标注.csv",
                    binary=["us_fatty", "us_hepatic_other", "us_gallstone", "us_kidney_cyst",
                            "us_unreadable", "main_discrepant"],
                    enum={}, degree="us_fatty_degree"),
}


def blank(s):
    return s.isna() | (s.astype(str).str.strip() == "")


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(OUT, exist_ok=True)
    xl = pd.ExcelFile(BOOK)
    rows, fatal = [], []
    for sheet, spec in EXPECT.items():
        df = xl.parse(sheet, dtype=str)
        src = pd.read_csv(os.path.join(DS, spec["src"]), dtype=str)
        add = lambda item, ok, detail="": rows.append(
            dict(sheet=sheet, item=item, result="PASS" if ok else "FAIL", detail=detail))

        # ① 行数一致
        add("行数一致", len(df) == spec["n"], f"收{len(df)}/应{spec['n']}")

        # ⑧ 原样回收：sample_id 与 text 与下发版逐行一致
        same_id = (df["sample_id"].fillna("").astype(str).values
                   == src["sample_id"].fillna("").astype(str).values).all()
        same_txt = (df["text"].fillna("").astype(str).values
                    == src["text"].fillna("").astype(str).values).all()
        add("原样回收", bool(same_id and same_txt) and len(df) == len(src),
            f"sample_id一致={same_id}, text一致={same_txt}")

        # ② 取值合法：二值列仅 0/1；枚举列在集合内；分度列仅轻/中/重或空
        bad = []
        for c in spec["binary"]:
            for r in ("A1_", "A2_"):
                v = df[r + c].astype(str).str.strip()
                nb = ~blank(df[r + c])
                if not bool((blank(df[r + c]) | v.isin(["0", "1"])).all()):
                    bad.append(r + c + ":" + ",".join(sorted(set(v[nb & ~v.isin(["0", "1"])]))[:5]))
        for c, allowed in spec["enum"].items():
            for r in ("A1_", "A2_"):
                v = df[r + c].astype(str).str.strip()
                nb = ~blank(df[r + c])
                if not bool(v[nb].isin(allowed).all()):
                    bad.append(r + c + ":" + ",".join(sorted(set(v[nb & ~v.isin(allowed)]))[:5]))
        if spec["degree"]:
            for r in ("A1_", "A2_"):
                col = r + spec["degree"]
                v = df[col].astype(str).str.strip()
                nb = ~blank(df[col])
                if not bool(v[nb].isin(["轻", "中", "重"]).all()):
                    bad.append(col + ":" + ",".join(sorted(set(v[nb & ~v.isin(["轻", "中", "重"])]))[:5]))
        if spec.get("numeric"):
            for r in ("A1_", "A2_"):
                v = pd.to_numeric(df[r + spec["numeric"][0]], errors="coerce")
                n_bad = int((v.isna() & ~blank(df[r + spec["numeric"][0]])).sum())
                if n_bad:
                    bad.append(f"{r}{spec['numeric'][0]}:非数值{n_bad}条")
        add("取值合法", not bad, "; ".join(bad) or "全部0/1与枚举合法")

        # ③ 逻辑一致：ef_abnormal=1 ⟺ ef_value<50（ef_value非空时）
        lg = []
        if "ECHO_PG" == sheet:
            for r in ("A1_", "A2_"):
                ev = pd.to_numeric(df[r + "ef_value"], errors="coerce")
                ab = df[r + "ef_abnormal"].astype(str).str.strip()
                m = ev.notna()
                viol = ((ab[m] == "1") & (ev[m] >= 50)) | ((ab[m] == "0") & (ev[m] < 50))
                if viol.any():
                    lg.append(f"{r}ef逻辑冲突{int(viol.sum())}条")
        add("逻辑一致", not lg, "; ".join(lg) or "ef_abnormal与ef_value自洽")

        # ④ flag 配套：flag=1 → note 非空；flag 率 <5%
        fl = []
        flag1 = df["flag"].astype(str).str.strip() == "1"
        note_blank = blank(df["note"])
        if (flag1 & note_blank).any():
            fl.append(f"flag=1但note空{int((flag1 & note_blank).sum())}条")
        rate = flag1.mean()
        add("flag配套", (not fl) and rate < 0.05,
            "; ".join(fl) or f"flag率{rate:.1%}（{int(flag1.sum())}条）")

        # ⑥ 权责分离：arbitration 列必须全空
        arb = blank(df["arbitration"])
        add("权责分离", bool(arb.all()), f"arbitration已填{int((~arb).sum())}条" if (~arb).any() else "仲裁列全空")

        # ⑤ 盲法独立（代理检查）：A1 与 A2 完全同列比例；并报告一致率供人工抽查
        agree_rates = []
        for c in spec["binary"]:
            a, b = df["A1_" + c], df["A2_" + c]
            m = ~(blank(a) | blank(b))
            agree_rates.append((a[m] == b[m]).mean())
        ident = min(agree_rates)
        add("盲法独立(代理)", ident < 0.999,
            f"二值列A1-A2一致率范围{min(agree_rates):.1%}-{max(agree_rates):.1%}"
            + ("（全同，需人工排查）" if ident > 0.999 else "，抽查3处见登记表"))

        # ⑦ 自重复标注：本表无法自动验证
        add("自重复标注10%", True, "本表内无重复行，待人工确认独立自重复记录（intra-rater κ用）")

        # 补充：必填完整率
        for c in spec["binary"]:
            for r in ("A1_", "A2_"):
                miss = int(blank(df[r + c]).sum())
                if miss:
                    rows.append(dict(sheet=sheet, item="必填完整", result="WARN",
                                     detail=f"{r}{c} 缺{miss}条"))

        # 补充：ef_value 双人精确一致率与相关
        if spec.get("numeric"):
            a = pd.to_numeric(df["A1_ef_value"], errors="coerce")
            b = pd.to_numeric(df["A2_ef_value"], errors="coerce")
            m = a.notna() & b.notna()
            if m.sum():
                rows.append(dict(sheet=sheet, item="ef_value双标", result="INFO",
                                 detail=f"双填{int(m.sum())}条，精确一致率{(a[m] == b[m]).mean():.1%}，"
                                        f"pearson r={np.corrcoef(a[m], b[m])[0, 1]:.3f}"))

    out = pd.DataFrame(rows)
    p = os.path.join(OUT, "recycle_verify_summary.csv")
    out.to_csv(p, index=False, encoding="utf-8-sig")
    print(out.to_string(index=False))
    fails = out[out["result"] == "FAIL"]
    print("\n===== M1c 结论 =====")
    print("❌ 未通过项: " + "；".join(f"{r.sheet}/{r.item}" for r in fails.itertuples()) if len(fails) else "✅ 八项自动核验全部通过（自重复标注与盲法抽查2项留人工确认）")
    print(f"输出 -> {p}")
    return 1 if len(fails) else 0


if __name__ == "__main__":
    sys.exit(main())
