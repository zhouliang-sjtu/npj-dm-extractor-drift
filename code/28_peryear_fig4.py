# -*- coding: utf-8 -*-
"""28_peryear_fig4.py —— M3d/Fig2b：分年份一致性（κ/F1）+ Fig4 图
ECG any-abnormal（gold = 1 - ecg_normal终值）逐年 κ 与目标类 F1，五条抽取器曲线：
  dict v1（生产库变量，经 gold.id 无关——直接用无否定窗口关键词规则在 gold 文本上重放）
  dict v3（main.py extract_ecg，否定窗口）
  LLM qwen2.5:14b / 7b / glm4:9b（prompt v1，字段级推导 any-abnormal，方案B口径）
gold 终值解析：A1==A2 → A1；否则 results/arbitration_decisions.csv per-variable 仲裁值
（修复 ECG_0374/0391 双仲裁行 per-row 列覆盖 bug——以仲裁 CSV 为权威）。
另附 echo 域 LLM 分年份（la_dilate / echo_normal[方案B]）→ 同 CSV。
输出：results/m3d_peryear.csv、figures/fig4_transportability.png/pdf
用法：python code/28_peryear_fig4.py
"""
import json
import os
import re
import sys

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIGD = os.path.join(ROOT, "figures")
ECG_VARS = ["ecg_normal", "ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock", "ecg_bbb",
            "ecg_rate", "ecg_srirr", "ecg_axis", "ecg_qwave_mi", "ecg_other",
            "ecg_unreadable"]
ABN_KEYS = ["ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock", "ecg_bbb", "ecg_rate",
            "ecg_srirr", "ecg_axis", "ecg_qwave_mi", "ecg_other"]
ECG_LLMS = {"qwen2.5:14b": "llm_ecg570_v1__qwen2.5_14b.csv",
            "qwen2.5:7b": "llm_ecg570_v1__qwen2.5_7b.csv",
            "glm4:9b": "llm_ecg570_v1__glm4_9b.csv"}
ECHO_LLMS = {"qwen2.5:14b": "llm_echo300_v21__qwen2.5_14b.csv",
             "qwen2.5:7b": "llm_echo300_v21__qwen2.5_7b.csv",
             "glm4:9b": "llm_echo300_v21__glm4_9b.csv"}


PARSE_KEYS = ["label", "ecg_normal"] + [
    "ecg_af", "ecg_pac_pvc", "ecg_stt", "ecg_avblock", "ecg_bbb", "ecg_rate",
    "ecg_srirr", "ecg_axis", "ecg_qwave_mi", "ecg_other", "ecg_unreadable",
    "lvh", "la_dilate", "ef", "reflux_grade", "abnormal_flag"]
KEY_RES = {k: re.compile(rf'"{k}"\s*:\s*(?:"([^"]*)"|([\-\w.]+))') for k in PARSE_KEYS}


def parse(raw):
    """优先 json.loads；畸形输出（glm4 evidence 未转义引号）退化为字段级正则提取"""
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return json.loads(raw)
    except Exception:
        i, j = raw.find("{"), raw.rfind("}")
        if 0 <= i < j:
            try:
                return json.loads(raw[i:j + 1])
            except Exception:
                pass
    out = {}
    for k, rex in KEY_RES.items():
        m = rex.search(raw)
        if m:
            out[k] = m.group(1) if m.group(1) is not None else m.group(2)
    return out if out else None


def kappa(a, b):
    labels = sorted(set(a) | set(b))
    n = len(a)
    if n < 10:
        return np.nan, np.nan
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in labels)
    return ((po - pe) / (1 - pe)) if pe < 1 else 1.0, po


def f1_cls(a, b, cls="1"):
    tp = sum(1 for x, y in zip(a, b) if x == cls and y == cls)
    fp = sum(1 for x, y in zip(a, b) if x != cls and y == cls)
    fn = sum(1 for x, y in zip(a, b) if x == cls and y != cls)
    p = tp / (tp + fp) if tp + fp else 0.0
    r = tp / (tp + fn) if tp + fn else 0.0
    return (2 * p * r / (p + r) if p + r else 0.0)


def v1_naive_ecg(t):
    """词典 v1（无否定窗口，negation-naive）在 gold 文本上重放"""
    if not t or t.strip() in ("×", "弃检", ""):
        return None
    hits = [re.search(p, t) for p in
            [r"房颤|心房颤动|心房扑动|房扑", r"早搏|期前收缩|过早搏动", r"ST-?T|ST段|T波|心肌缺血",
             r"房室传导阻滞|房室阻滞|[一二三ⅠⅡⅢ]度房?室?传导", r"束支(传导)?阻滞|分支阻滞|室内传导阻滞",
             r"心动过速|心动过缓", r"窦性心律不齐|窦性不齐|窦性心动不齐", r"电轴(左|右)偏|转位|低电压",
             r"异常Q波|病理性Q波|陈旧性(下壁|前壁|侧壁|后壁)|心肌梗死|心肌梗塞",
             r"预激|逸搏|起搏|房室分离|肥大|肥厚|紊乱"]]
    return "1" if any(hits) else "0"


def v3_ecg_any_abnormal(t):
    sys.path.insert(0, os.path.join(ROOT, "code"))
    from main import extract_ecg  # noqa: E402
    f = extract_ecg(str(t).replace("\r\n", "\n").strip())
    if f.get("ecg_unreadable") == 1:
        return None
    return "0" if f.get("ecg_normal") == 1 else "1"


def llm_ecg_any_abnormal(raw):
    """any-abnormal = 1 - ecg_normal 字段（与 gold 定义同构）。
    注：不能用"任一异常字段"推导——2022-23 新模板的早期复极类报告 gold normal=0
    但全部异常列=0，字段推导会错判（29 口径已验证 ecg_normal 字段与 gold 几乎完全一致）"""
    p = parse(raw)
    if p is None or str(p.get("label")) == "unreadable":
        return None
    return "0" if str(p.get("ecg_normal")) == "1" else "1"


def llm_echo_normal(raw):
    p = parse(raw)
    if p is None or str(p.get("label")) == "unreadable":
        return None
    abn = (str(p.get("lvh")) == "1" or str(p.get("la_dilate")) == "1"
           or (p.get("ef") is not None and float(p.get("ef")) < 50)
           or str(p.get("reflux_grade")) in ("moderate", "severe")
           or str(p.get("label")) == "abnormal")
    return "0" if abn else "1"


def llm_echo_la(raw):
    p = parse(raw)
    if p is None or str(p.get("label")) == "unreadable":
        return None
    return str(p.get("la_dilate"))


def gold_ecg():
    """per-variable 终值：共识 → per-variable 仲裁（arbitration_decisions.csv 权威）"""
    e = pd.read_excel(os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx"),
                      sheet_name="ECG_H", dtype=str).set_index("sample_id")
    arb = pd.read_csv(os.path.join(ROOT, "results", "arbitration_decisions.csv"), dtype=str)
    arb_map = {(r["sample_id"], r["variable"]): r["final"]
               for _, r in arb.iterrows() if r["sheet"] == "ECG_H"}
    df = pd.DataFrame({"sample_id": list(e.index),
                       "year": [str(e.loc[s, "year"])[:4] for s in e.index],
                       "text": [e.loc[s, "text"] for s in e.index]})
    normals = []
    for sid in df.sample_id:
        r = e.loc[sid]
        a1, a2 = r["A1_ecg_normal"], r["A2_ecg_normal"]
        fin = a1 if (pd.notna(a1) and a1 == a2) else arb_map.get((sid, "ecg_normal"), "")
        normals.append(fin)
    df["normal_final"] = normals
    df["gold"] = df["normal_final"].map(lambda v: {"0": "1", "1": "0"}.get(str(v), ""))
    return df


def gold_echo():
    e = pd.read_excel(os.path.join(ROOT, "data", "gold_annotation_workbook_final.xlsx"),
                      sheet_name="ECHO_PG", dtype=str).set_index("sample_id")
    res = pd.read_csv(os.path.join(ROOT, "results", "round2_final_resolution.csv"), dtype=str)
    fin_la = res[res.variable == "echo_la_dilate"].set_index("sample_id")["final"]
    df = pd.DataFrame({"sample_id": list(e.index),
                       "year": [str(e.loc[s, "exam_date"])[:4] for s in e.index]})
    df["la_gold"] = df.sample_id.map(fin_la).fillna("")
    df["normal_gold"] = [r["A1_echo_normal"] if r["A1_echo_normal"] == r["A2_echo_normal"] else ""
                         for _, r in e.iterrows()]
    return df


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(FIGD, exist_ok=True)
    rows = []

    # ---- ECG any-abnormal ----
    g = gold_ecg()
    g["dict v1"] = g.text.map(v1_naive_ecg)
    g["dict v3"] = g.text.map(v3_ecg_any_abnormal)
    for model, fn in ECG_LLMS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        m = dict(zip(d.sample_id, d.llm_raw.map(llm_ecg_any_abnormal)))
        g[model] = g.sample_id.map(m)
    for ext in ["dict v1", "dict v3"] + list(ECG_LLMS):
        for scope, sub in [("overall", g)] + [(y, g[g.year == y]) for y in sorted(g.year.unique())]:
            pairs = [(x, y) for x, y in zip(sub.gold.astype(str), sub[ext].astype(str))
                     if x != "" and y != "" and x != "nan" and y != "nan"]
            if len(pairs) < 10:
                continue
            a = [x for x, _ in pairs]
            b = [y for _, y in pairs]
            k, _ = kappa(a, b)
            rows.append(dict(domain="ECG", outcome="any_abnormal", extractor=ext, year=scope,
                             n=len(pairs), cohen_kappa=(round(k, 3) if pd.notna(k) else ""),
                             F1_target=round(f1_cls(a, b), 3)))

    # ---- echo LLM 分年份 ----
    ge = gold_echo()
    for model, fn in ECHO_LLMS.items():
        d = pd.read_csv(os.path.join(ROOT, "data", fn), encoding="utf-8-sig", dtype=str)
        mnorm = dict(zip(d.sample_id, d.llm_raw.map(llm_echo_normal)))
        mla = dict(zip(d.sample_id, d.llm_raw.map(llm_echo_la)))
        for var, m in [("echo_normal", mnorm), ("echo_la_dilate", mla)]:
            col = ge.sample_id.map(m)
            for scope, sub in [("overall", ge)] + [(y, ge[ge.year == y]) for y in
                                                   sorted(ge.year.unique())]:
                gcol = "normal_gold" if var == "echo_normal" else "la_gold"
                a = ge.loc[sub.index, gcol].astype(str)
                b = col.loc[sub.index].astype(str)
                pairs = [(x, y) for x, y in zip(a, b) if x != "" and y != "" and x != "nan"
                         and y != "nan"]
                if len(pairs) < 10:
                    continue
                k, _ = kappa([x for x, _ in pairs], [y for _, y in pairs])
                rows.append(dict(domain="ECHO", outcome=var, extractor=model, year=scope,
                                 n=len(pairs), cohen_kappa=(round(k, 3) if pd.notna(k) else ""),
                                 F1_target=""))
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(ROOT, "results", "m3d_peryear.csv"), index=False,
               encoding="utf-8-sig")
    print(out[(out.domain == "ECG") & (out.year != "overall")].pivot(
        index="year", columns="extractor", values="cohen_kappa").to_string())

    # ---- Fig4 ----
    fig, ax = plt.subplots(figsize=(7.5, 4.6))
    years = sorted(y for y in out[(out.domain == "ECG") & (out.year != "overall")].year.unique())
    styles = {"dict v1": ("#7f7f7f", "s", "--"), "dict v3": ("#7f7f7f", "D", "-"),
              "qwen2.5:14b": ("#d62728", "o", "-"), "qwen2.5:7b": ("#1f77b4", "^", "-"),
              "glm4:9b": ("#2ca02c", "v", "-")}
    for ext in ["dict v1", "dict v3", "qwen2.5:14b", "qwen2.5:7b", "glm4:9b"]:
        s = out[(out.domain == "ECG") & (out.extractor == ext) & (out.year != "overall")]
        s = s.set_index("year").loc[years]
        c, mk, ls = styles[ext]
        ax.plot(years, s.cohen_kappa.astype(float), color=c, marker=mk, ls=ls, lw=1.8, ms=6,
                label=ext + (" (frozen)" if ext == "qwen2.5:14b" else ""))
    ax.axhline(0.80, color="black", ls=":", lw=1)
    ax.text(len(years) - 1.02, 0.812, "acceptance gate κ=0.80", fontsize=8, va="bottom")
    ax.set_xlabel("Calendar year (gold-standard stratum)")
    ax.set_ylabel("Cohen's κ vs adjudicated gold\n(any ECG abnormality)")
    ax.set_ylim(0, 1.05)
    ax.legend(fontsize=8, frameon=False, ncol=2)
    fig.tight_layout()
    for ext in ("png", "pdf"):
        fig.savefig(os.path.join(FIGD, f"fig4_transportability.{ext}"), dpi=300)
    plt.close(fig)
    print("-> results/m3d_peryear.csv; figures/fig4_transportability.png/pdf")
    return 0


if __name__ == "__main__":
    sys.exit(main())
