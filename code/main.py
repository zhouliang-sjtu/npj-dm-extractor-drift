#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""main.py —— 《纵向体检文本LLM表型化抽取与年份漂移质控系统 V1.0》统一命令行入口

子命令:
  sample        分层抽样（--domain ecg|echo|abdus_pg|abdus_h）
  extract-dict  词典/正则双轨抽取（--domain ecg|abdus --input --out）
  extract-llm   LLM批量抽取（--input --out --endpoint --model --limit）
  validate      一致性验收（--file --sheet --cols）
  manifest      抽取器版本登记（--domain --status --model --prompt-hash）
"""
import argparse
import hashlib
import json
import os
import re
import sys
import time

# ---------------- 公共工具 ----------------
BASE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(BASE, "..", "data")
LONG_CSV = os.path.join(BASE, "..", "data", "processed", "H_checkup_long.csv")
MANIFEST = os.path.join(BASE, "extractor_manifest.json")


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def norm(s):
    return str(s if s is not None else "").replace("\r\n", "\n").strip()


# ---------------- 文本抽取器（词典/规则，确定性） ----------------
NEG = lambda t, seg: bool(re.search(r"(未见|无明显|无)[^。；\n]{0,8}" + seg, t))


def extract_ecg(t):
    """ECG结论文本 -> 多标签字典（词典v3口径，否定优先）"""
    if not t or t.strip() in ("×", "弃检", ""):
        return {"ecg_unreadable": 1}
    f = {
        "ecg_af": 1 if re.search(r"房颤|心房颤动|心房扑动|房扑", t) else 0,
        "ecg_pac_pvc": 1 if re.search(r"早搏|期前收缩|过早搏动", t) else 0,
        "ecg_stt": 1 if (re.search(r"ST-?T|ST段|T波(改变|低平|倒置|高尖)|心肌缺血", t)
                         and not re.search(r"(未见|无明显)[^。；\n]{0,8}(ST|T波)", t)) else 0,
        "ecg_avblock": 1 if re.search(r"房室传导阻滞|房室阻滞|[一二三ⅠⅡⅢ]度房?室?传导", t) else 0,
        "ecg_bbb": 1 if re.search(r"束支(传导)?阻滞|分支阻滞|室内传导阻滞", t) else 0,
        "ecg_rate": 1 if re.search(r"心动过速|心动过缓", t) else 0,
        "ecg_srirr": 1 if re.search(r"窦性心律不齐|窦性不齐|窦性心动不齐|窦性心动律不齐", t) else 0,
        "ecg_axis": 1 if re.search(r"电轴(左|右)偏|转位|低电压", t) else 0,
        "ecg_qwave_mi": 1 if re.search(r"异常Q波|病理性Q波|陈旧性(下壁|前壁|侧壁|后壁)|心肌梗死|心肌梗塞", t) else 0,
        "ecg_other": 1 if re.search(r"预激|逸搏|起搏|房室分离|肥大|肥厚|紊乱", t) else 0,
    }
    f["ecg_normal"] = 1 if (not any(f.values()) and re.search(r"正常|未见|大致", t)) else 0
    f["ecg_unreadable"] = 0
    return f


def extract_abd(t, main_text=""):
    """腹部超声所见(+主检结果) -> 脂肪肝及伴发征象（描述式口径）"""
    combined = t + " " + str(main_text or "")
    in_us = bool(re.search(r"脂肪肝", t))
    in_main = bool(re.search(r"脂肪肝", main_text or ""))
    desc_hit = (re.search(r"细密", t) and re.search(r"衰减|欠清", t))
    fatty = 1 if (in_us or in_main or desc_hit) else 0
    deg = ""
    m = re.search(r"脂肪肝[^。；\n]{0,8}?(轻度|中度|重度)|((轻度|中度|重度)[^。；\n]{0,6}?脂肪肝)", t + " " + (main_text or ""))
    if m:
        deg = (m.group(1) or m.group(2) or "")
    return {
        "us_fatty": fatty,
        "us_fatty_degree": deg,
        "us_hepatic_other": 1 if re.search(r"血吸虫|肝囊肿|血管瘤|占位|肝硬化", t) else 0,
        "us_gallstone": 1 if re.search(r"胆(囊|管)?(结石|息肉)", t) else 0,
        "us_kidney_cyst": 1 if re.search(r"肾囊肿", t) else 0,
    }


def extract_echo(t):
    """心脏超声报告 -> 结构化字段（定性+数值确定性抽取）"""
    ef_m = re.search(r"(?:EF|LVEF|射血分数)[^0-9]{0,10}(\d{2,3})", t)
    ef = float(ef_m.group(1)) if ef_m else None
    neg_stt = bool(re.search(r"(未见|无明显)[^。；\n]{0,8}(ST|T波)", t))
    lvh = (re.search(r"(室间隔|左室后壁|左室壁)[^。；\n]{0,6}(增厚|肥厚)", t)
           and not NEG(t, "增厚"))
    la = re.search(r"左房[^。；\n]{0,8}(增大|扩大|增宽)", t) and not NEG(t, "增大")
    la_m = re.search(r"左房内径[^0-9]{0,4}(\d{2,3})", t)
    la_dilate = 1 if ((la_m and float(la_m.group(1)) >= 40) or la) else 0
    sig_ref = bool(re.search(r"(中度|重度)[^。；\n]{0,6}(返流|反流)", t))
    mild_ref = bool(re.search(r"(少量|轻微|轻度)[^。；\n]{0,6}(返流|反流)", t))
    rhythm = bool(re.search(r"房颤|早搏|传导阻滞|起搏|逸搏", t))
    abnormal = bool(lvh or la_dilate or (ef is not None and ef < 50) or sig_ref or rhythm)
    if abnormal:
        label = "abnormal"
    elif mild_ref:
        label = "normal_variant"
    else:
        label = "normal"
    return {"label": label, "lvh": int(bool(lvh)), "la_dilate": la_dilate,
            "ef": ef, "reflux_grade": ("severe" if re.search(r"重度", t) else
                                       "moderate" if sig_ref else
                                       "mild" if mild_ref else "none"),
            "rhythm": int(rhythm)}


# ---------------- 子命令：sample ----------------
def cmd_sample(args):
    seed = args.seed
    if args.domain == "ecg":
        import pandas as pd
        df = pd.read_csv(LONG_CSV, encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
        ecg = df[df["ecg_text"].notna()].copy()
        ecg["text"] = ecg["ecg_text"].astype(str).str.slice(0, 150)
        parts = [g.sample(min(args.per_year, len(g)), random_state=seed)
                 for _, g in ecg.groupby("year")]
        gold = pd.concat(parts).drop_duplicates(subset=["id", "year"])
    elif args.domain == "abdus_h":
        import pandas as pd
        src = os.path.join(BASE, "..", "data", "processed", "H_us_text_long.csv")
        df = pd.read_csv(src, encoding="utf-8-sig", dtype={"id": str})
        df["text"] = (df["us_text"].astype(str) + " " + df["main_text"].astype(str)).str.slice(0, 600)
        parts = [g.sample(min(args.per_year, len(g)), random_state=seed)
                 for _, g in df.groupby("year")]
        gold = pd.concat(parts).drop_duplicates(subset=["id", "year"])
    else:
        print("echo/abdus_pg 域请使用 01_sample_gold_standard.py 或 extract-llm 前先以SQL抽样")
        return
    out = gold[["year", "id", "text"]].copy()
    out.insert(0, "sample_id", [f"{args.domain.upper()}_{i+1:04d}" for i in range(len(out))])
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"[sample] {args.domain}: {len(out)} 条 -> {args.out}")


# ---------------- 子命令：extract-dict ----------------
def cmd_extract_dict(args):
    import pandas as pd
    df = pd.read_csv(args.input, encoding="utf-8-sig", dtype=str)
    text_col = "text" if "text" in df.columns else "ecg_text"
    if args.domain == "ecg":
        res = df[text_col].fillna("").apply(lambda t: extract_ecg(norm(t)))
        res = pd.DataFrame(res.tolist())
        out = pd.concat([df[["sample_id"]], df[[text_col]], res], axis=1)
    else:
        main_col = "main_text" if "main_text" in df.columns else None
        res = df.apply(lambda r: extract_abd(norm(r.get(text_col, "")),
                                             norm(r.get(main_col, "")) if main_col else ""), axis=1)
        res = pd.DataFrame(res.tolist())
        out = pd.concat([df[["sample_id"]], df[[text_col]], res], axis=1)
    out.to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"[extract-dict] {args.domain}: {len(out)} 条 -> {args.out}")


# ---------------- 子命令：extract-llm ----------------
def cmd_extract_llm(args):
    import pandas as pd
    import requests
    df = pd.read_csv(args.input, encoding="utf-8-sig", dtype=str)
    if args.limit:
        df = df.head(args.limit)
    system_prompt = (args.prompt_file and open(args.prompt_file, encoding="utf-8").read()) or args.system
    sess = requests.Session()
    rows, t0 = [], time.time()
    for i, r in enumerate(df.itertuples(index=False)):
        text = norm(getattr(r, "text", ""))
        ih = sha(text)
        try:
            resp = sess.post(args.endpoint, json={
                "model": args.model, "stream": False, "temperature": 0, "seed": args.seed,
                "messages": [{"role": "system", "content": system_prompt},
                             {"role": "user", "content": text}]}, timeout=300).json()
            raw = resp["choices"][0]["message"]["content"] \
                if "choices" in resp else resp["message"]["content"]
        except Exception as e:
            raw = f"ERROR:{e}"
        rows.append({"sample_id": getattr(r, "sample_id", i), "input_hash": ih,
                     "llm_raw": raw[:1000], "output_hash": sha(raw)})
        if (i + 1) % args.log_every == 0:
            print(f"  {i+1}/{len(df)}  累计耗时{time.time()-t0:.0f}s")
    pd.DataFrame(rows).to_csv(args.out, index=False, encoding="utf-8-sig")
    print(f"[extract-llm] {len(rows)} 条 -> {args.out}")


# ---------------- 子命令：validate ----------------
def cmd_validate(args):
    import pandas as pd
    df = pd.read_excel(args.file, sheet_name=args.sheet, dtype=str)
    rows = []
    for col in args.cols.split(","):
        a = df["A1_" + col].astype(str).str.strip().replace({"": None}).dropna()
        b = df["A2_" + col].astype(str).str.strip().replace({"": None}).dropna()
        d = pd.DataFrame({"a": a, "b": b}).dropna()
        if len(d) < 20:
            continue
        labels = sorted(set(d["a"]) | set(d["b"]))
        po = float(np_mean([x == y for x, y in zip(d["a"], d["b"])]))
        pe = sum((d["a"] == L).mean() * (d["b"] == L).mean() for L in labels)
        k = (po - pe) / (1 - pe) if pe < 1 else 1.0
        rows.append({"variable": col, "n": len(d), "po": round(po, 3), "cohen_kappa": round(k, 3)})
    pd.DataFrame(rows).to_csv(args.out, index=False, encoding="utf-8-sig")
    print(rows)
    print(f"[validate] -> {args.out}（门槛κ≥0.80）")


def np_mean(x):
    return sum(1 for v in x if v) / len(x)


# ---------------- 子命令：manifest ----------------
def cmd_manifest(args):
    with open(MANIFEST, encoding="utf-8") as f:
        m = json.load(f)
    for e in m["extractors"]:
        if e["variable_domain"] == args.domain:
            e["status"] = args.status
            if args.model:
                e["model_name"] = args.model
            if args.prompt_hash:
                e["prompt_hash_sha256_16"] = args.prompt_hash
            if args.status == "frozen":
                import datetime
                e["frozen_date"] = datetime.date.today().isoformat()
    with open(MANIFEST, "w", encoding="utf-8") as f:
        json.dump(m, f, ensure_ascii=False, indent=2)
    print(f"[manifest] {args.domain} -> {args.status}")


# ---------------- 入口 ----------------
def main():
    ap = argparse.ArgumentParser(description="纵向体检文本LLM表型化抽取与年份漂移质控系统 V1.0")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s1 = sub.add_parser("sample", help="分层抽样")
    s1.add_argument("--domain", required=True, choices=["ecg", "echo", "abdus_pg", "abdus_h"])
    s1.add_argument("--per-year", type=int, default=60)
    s1.add_argument("--out", required=True)
    s1.add_argument("--seed", type=int, default=42)
    s1.set_defaults(func=cmd_sample)

    s2 = sub.add_parser("extract-dict", help="词典/正则抽取")
    s2.add_argument("--domain", required=True, choices=["ecg", "abdus"])
    s2.add_argument("--input", required=True)
    s2.add_argument("--out", required=True)
    s2.set_defaults(func=cmd_extract_dict)

    s3 = sub.add_parser("extract-llm", help="LLM批量抽取")
    s3.add_argument("--input", required=True)
    s3.add_argument("--out", required=True)
    s3.add_argument("--endpoint", default="http://127.0.0.1:11434/api/chat")
    s3.add_argument("--model", default="qwen2.5:14b")
    s3.add_argument("--prompt-file", default="")
    s3.add_argument("--system", default="")
    s3.add_argument("--seed", type=int, default=42)
    s3.add_argument("--limit", type=int, default=0)
    s3.add_argument("--log-every", type=int, default=50)
    s3.set_defaults(func=cmd_extract_llm)

    s4 = sub.add_parser("validate", help="一致性验收")
    s4.add_argument("--file", required=True)
    s4.add_argument("--sheet", required=True)
    s4.add_argument("--cols", required=True)
    s4.add_argument("--out", default="agreement.csv")
    s4.set_defaults(func=cmd_validate)

    s5 = sub.add_parser("manifest", help="抽取器版本登记")
    s5.add_argument("--domain", required=True)
    s5.add_argument("--status", required=True, choices=["pending_validation", "validated", "frozen", "deprecated"])
    s5.add_argument("--model", default="")
    s5.add_argument("--prompt-hash", default="")
    s5.set_defaults(func=cmd_manifest)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
