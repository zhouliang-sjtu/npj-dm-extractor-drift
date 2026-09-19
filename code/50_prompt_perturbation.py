# -*- coding: utf-8 -*-
"""50_prompt_perturbation.py —— 修回预案第四件：语义等价 prompt 扰动敏感性（2026-09-11）

目的：Limitations 声明"未检验冻结 prompt 内语义保持改写的稳健性"——本实验补上。
设计（有界）：ECG 域全量 570 份金样本 × 主模型 qwen2.5:14b × 2 个语义等价改写变体，
  推理参数与冻结基线完全一致（temperature=0, seed=42, format=json, num_predict=400,
  Ollama /api/chat），仅 system prompt 变化：
  A_paraphrase —— 措辞同义改写（段落结构与规则顺序不变，全部阈值/枚举/例外逐条保留）
  B_reorder    —— 判定规则顺序重排（特异→一般）+ 编号样式改变；标签列表与输出 JSON
                  示例键序不变（防 schema 漂移）
  两变体均与基线 v1 prompt（sha256 前 16 位 dbb1ebe717ad3497）语义等价。
评估：29 口径（A1==A2→A1，否则仲裁终值）逐变量 κ/F1_pos/acc 与预注册 gate
  （κ≥0.80, F1≥0.90, acc≥0.95, 分层 acc≥0.90）；any_abnormal（normal=0&unreadable=0）
  overall 与逐年 κ/F1（对照 results/m3d_peryear.csv 同帧口径）。
输出：data/llm_ecg570_aparaphrase__qwen2.5_14b.csv / _breorder_…（基线同格式，断点续跑）
      results/prompt_perturbation_eval.csv
用法：python code/50_prompt_perturbation.py [--limit=0] [--eval-only]
"""
import hashlib
import json
import os
import sys
import time
import urllib.request

import pandas as pd

import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
DATA = os.path.join(ROOT, "data")
PROMPT_V0 = os.path.join(ROOT, "docs", "prompts", "llm_ecg_prompt_template_v1.md")
GOLD = os.path.join(DATA, "gold_ecg_H.csv")
MODEL = "qwen2.5:14b"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ---------------- 语义等价变体（仅 system prompt；判定内容逐条保留） ----------------
PROMPT_A = """# 角色与任务
你是一名心电图（ECG）报告结构化标注助手。请对下面的中文心电图检查结论进行标注，输出12个取值为0或1的多标签：
ecg_normal, ecg_af, ecg_pac_pvc, ecg_stt, ecg_avblock, ecg_bbb, ecg_rate, ecg_srirr, ecg_axis, ecg_qwave_mi, ecg_other, ecg_unreadable

# 标注规则（与《标注手册》v2.0 保持一致）
1. 否定表述优先处理：若出现"未见/无明显/无"等否定词，则紧随其后的8个字符范围内出现的阳性关键词一律不视为阳性（例如"未见ST-T改变"→ecg_stt=0；"未见明显异常"→ecg_normal=1）
2. ecg_normal=1：报告中包含"正常心电图/大致正常/未见明显异常/正常范围"等表述，并且不存在下面任何一项异常
3. ecg_af=1：房颤、心房颤动、心房扑动、房扑（即使同时出现"窦性"字样仍应标为1，例如"房颤伴快速心室率"）
4. ecg_pac_pvc=1：早搏、期前收缩、过早搏动（房性与室性均标为1，无需区分类型）
5. ecg_stt=1：ST-T改变、ST段抬高/压低、T波低平/倒置/高尖、心肌缺血
6. ecg_avblock=1：一度/二度/三度房室传导阻滞、Ⅰ/II/III度AVB
7. ecg_bbb=1：左/右束支传导阻滞、分支阻滞、室内传导阻滞
8. ecg_rate=1：窦性心动过速（>100）或窦性心动过缓（<60）；窦性心律60-100不属于本类；房颤/房扑伴快速心室率（"快速型/心室率快"）标为1；非窦性的心动过速（如非阵发性交界区心动过速）不属于本类
9. ecg_srirr=1：窦性心律不齐/窦性心动不齐（包括错别字变体）
10. ecg_axis=1：电轴左偏/右偏、顺/逆钟向转位、低电压；"电轴不偏"不属于本类；"左心室（高）电压"不属于本类（无器质性含义，任何一列都不计入）
11. ecg_qwave_mi=1：异常Q波、病理性Q波、陈旧性下壁/前壁梗死
12. ecg_other=1：预激、逸搏、起搏器、房室分离、肥大/肥厚、紊乱性心律、窦房阻滞、房室连接处（交界区）心动过速；"早期复极（综合征）/ST段J点抬高提示早期复极"属于正常变异，不计入本列
13. ecg_unreadable=1：文本缺失/×/弃检/拒检/无法判读，或为与心电图域不相符的其他检查内容；此时其余11个字段全部填0

# 输出格式（严格JSON，除JSON外不得输出任何文字）
{"ecg_normal":0,"ecg_af":0,"ecg_pac_pvc":0,"ecg_stt":0,"ecg_avblock":0,"ecg_bbb":0,"ecg_rate":0,"ecg_srirr":0,"ecg_axis":0,"ecg_qwave_mi":0,"ecg_other":0,"ecg_unreadable":0,"evidence":"原文关键句"}
- 所有字段只能填0或1；evidence 摘录作为判定依据的关键原文

# 金标准协议
1. 验收集：ECG 域全量 570 份（年份×关键词分层＋AF/传导阻滞/ST-T 稀有层过采样），由两名临床医师独立盲法双标注，不一致个案由仲裁人裁决
2. 验收标准：与金标准相比 Cohen's κ≥0.80、目标类 F1≥0.90、准确率≥95%；各年份层内准确率≥90%
3. LLM 版本/温度/种子/prompt 哈希写入 extractor_manifest 并写入论文方法节；prompt 或模型升级仅作敏感性分析，不回写主库
"""

# B_reorder：规则重排（原编号）：13,1,2,5,3,8,9,4,6,7,11,10,12；编号改全角括号
_PROMPT_B_RULES = """（一）ecg_unreadable=1：文本缺失/×/弃检/拒检/无法判读，或与心电图域不符的其他检查内容；此时其余11个字段一律填0
（二）否定优先："未见/无明显/无"等否定词其后8字窗口内的阳性关键词不计数（"未见ST-T改变"→ecg_stt=0；"未见明显异常"→ecg_normal=1）
（三）ecg_normal=1：含"正常心电图/大致正常/未见明显异常/正常范围"，且无下列任何异常
（四）ecg_stt=1：ST-T改变、ST段抬高/压低、T波低平/倒置/高尖、心肌缺血
（五）ecg_af=1：房颤、心房颤动、心房扑动、房扑（"窦性"字样并存时仍标1，如"房颤伴快速心室率"）
（六）ecg_rate=1：窦性心动过速（>100）或窦性心动过缓（<60）；窦性心律60-100不算；房颤/房扑伴快速心室率（"快速型/心室率快"）=1；非窦性心动过速（如非阵发性交界区心动过速）不算
（七）ecg_srirr=1：窦性心律不齐/窦性心动不齐（含错别字变体）
（八）ecg_pac_pvc=1：早搏、期前收缩、过早搏动（房性/室性均=1，无需区分）
（九）ecg_avblock=1：一度/二度/三度房室传导阻滞、Ⅰ/II/III度AVB
（十）ecg_bbb=1：左/右束支传导阻滞、分支阻滞、室内传导阻滞
（十一）ecg_qwave_mi=1：异常Q波、病理性Q波、陈旧性下壁/前壁梗死
（十二）ecg_axis=1：电轴左偏/右偏、顺/逆钟向转位、低电压；"电轴不偏"不算；"左心室（高）电压"不算（无器质含义，任何列都不计）
（十三）ecg_other=1：预激、逸搏、起搏器、房室分离、肥大/肥厚、紊乱性心律、窦房阻滞、房室连接处（交界区）心动过速；"早期复极（综合征）/ST段J点抬高提示早期复极"属正常变异，不计入本列"""

PROMPT_B = """# 角色与任务
你是心电图（ECG）报告结构化助手。将以下中文心电图检查结论标注为12个0/1多标签：
ecg_normal, ecg_af, ecg_pac_pvc, ecg_stt, ecg_avblock, ecg_bbb, ecg_rate, ecg_srirr, ecg_axis, ecg_qwave_mi, ecg_other, ecg_unreadable

# 判定规则（与《标注手册》v2.0 同口径，按可判读性优先排列）
""" + _PROMPT_B_RULES + """

# 输出格式（严格JSON，不输出任何其他文字）
{"ecg_normal":0,"ecg_af":0,"ecg_pac_pvc":0,"ecg_stt":0,"ecg_avblock":0,"ecg_bbb":0,"ecg_rate":0,"ecg_srirr":0,"ecg_axis":0,"ecg_qwave_mi":0,"ecg_other":0,"ecg_unreadable":0,"evidence":"原文关键句"}
- 全部字段仅填0或1；evidence 摘录判定依据的关键原文

# 金标准协议
1. 验收集：ECG 域全量 570 份（年份×关键词分层＋AF/传导阻滞/ST-T 稀有层过采样），两名临床医师独立盲法双标注，仲裁人裁决不一致个案
2. 验收标准：与金标准 Cohen's κ≥0.80，目标类 F1≥0.90，准确率≥95%；分年份层内准确率≥90%
3. LLM 版本/温度/种子/prompt 哈希写入 extractor_manifest 并写入论文方法节；prompt 或模型升级仅作敏感性分析，不回写主库
"""

VARIANTS = {"aparaphrase": PROMPT_A, "breorder": PROMPT_B}


def sha(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:16]


def call_ollama(system, text):
    body = {"model": MODEL, "stream": False, "format": "json",
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": text}],
            "options": {"temperature": 0, "seed": 42, "num_predict": 400}}
    req = urllib.request.Request("http://127.0.0.1:11434/api/chat",
                                 data=json.dumps(body).encode("utf-8"),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.loads(r.read().decode("utf-8"))["message"]["content"]


def run_variant(variant, limit=0):
    system = VARIANTS[variant]
    out_path = os.path.join(DATA, f"llm_ecg570_{variant}__{MODEL.replace(':', '_').replace('.', '')}.csv")
    gold = pd.read_csv(GOLD, encoding="utf-8-sig", dtype=str)
    if limit:
        gold = gold.head(limit)
    done = {}
    if os.path.exists(out_path):
        prev = pd.read_csv(out_path, encoding="utf-8-sig", dtype=str)
        done = dict(zip(prev["sample_id"], zip(prev["llm_raw"], prev["output_hash"])))
        print(f"  续跑：已有 {len(done)} 条")
    rows = []
    t0 = time.time()
    for i, r in enumerate(gold.itertuples(index=False)):
        if r.sample_id in done:
            rows.append({"sample_id": r.sample_id, "input_hash": sha(str(r.text)),
                         "llm_raw": done[r.sample_id][0],
                         "output_hash": done[r.sample_id][1]})
            continue
        raw = ""
        for attempt in range(3):
            try:
                raw = call_ollama(system, str(r.text))
                break
            except Exception as e:
                print(f"  重试 {r.sample_id}: {e}", flush=True)
                time.sleep(2 ** attempt)
        rows.append({"sample_id": r.sample_id, "input_hash": sha(str(r.text)),
                     "llm_raw": raw, "output_hash": sha(raw) if raw else ""})
        if (i + 1) % 20 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(gold)}  {el:.0f}s  ({el/(i+1):.1f}s/条)", flush=True)
            pd.DataFrame(rows).to_csv(out_path, index=False, encoding="utf-8-sig")
    pd.DataFrame(rows).to_csv(out_path, index=False, encoding="utf-8-sig")
    print(f"  完成 {variant}: {len(rows)} 条 -> {out_path}  "
          f"prompt_hash={sha(system)}  总耗时 {time.time()-t0:.0f}s")
    return out_path


def evaluate(out_paths):
    spec = importlib.util.spec_from_file_location(
        "m29", os.path.join(ROOT, "code", "29_ecg_acceptance.py"))
    m29 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m29)
    e, g = m29.gold_finals()

    def collect(fn):
        d = pd.read_csv(fn, encoding="utf-8-sig", dtype=str)
        parsed = {r.sample_id: m29.parse(r.llm_raw) for r in d.itertuples(index=False)}
        per_var = {}
        any_rows = []          # (sample_id, year, gold_any, llm_any)
        for sid in d.sample_id:
            p = parsed.get(sid)
            # any_abnormal = 1 − ecg_normal 终值（28/m3d 口径；不能用"任一异常字段"推导，
            # 2022-23 早期复极类报告 gold normal=0 但全部异常列=0，字段推导会错判）
            gv_n = g.get((sid, "ecg_normal"), "")
            llm_n = str(p.get("ecg_normal")) if p else None
            if gv_n in ("0", "1") and llm_n in ("0", "1"):
                gold_any = "0" if gv_n == "1" else "1"
                llm_any = "0" if llm_n == "1" else "1"
                any_rows.append((sid, str(e.loc[sid, "year"])[:4], gold_any, llm_any))
            for var in m29.ECG_VARS:
                gv = g.get((sid, var), "")
                if gv == "" or p is None:
                    continue
                per_var.setdefault(var, ([], []))
                per_var[var][0].append(str(gv))
                per_var[var][1].append(str(p.get(var)))
        return per_var, any_rows

    def kappa_f1(a, b):
        k, po = m29.kappa(a, b)
        return k, po, m29.f1_pos(a, b)

    rows = []
    for label, fn in out_paths.items():
        per_var, any_rows = collect(fn)
        n_pass = 0
        for var in m29.ECG_VARS:
            if var not in per_var:
                continue
            a, b = per_var[var]
            k, po, f1 = kappa_f1(a, b)
            ok = (k >= 0.80) and (f1 >= 0.90) and (po >= 0.95)
            n_pass += ok
            rows.append(dict(variant=label, model=MODEL, variable=var, year="overall", n=len(a),
                             kappa=round(k, 3), F1_pos=round(f1, 3), acc=round(po, 3),
                             gate_pass=ok))
        ay = pd.DataFrame(any_rows, columns=["sid", "year", "g", "p"])
        a_all, b_all = ay["g"].astype(str).tolist(), ay["p"].astype(str).tolist()
        k_any, po_any, f1_any = kappa_f1(a_all, b_all)
        rows.append(dict(variant=label, model=MODEL, variable="any_abnormal", year="overall",
                         n=len(ay), kappa=round(k_any, 3), F1_pos=round(f1_any, 3),
                         acc=round(po_any, 3), gate_pass=""))
        for y in sorted(ay.year.unique()):
            s = ay[ay.year == y]
            k, po, f1 = kappa_f1(s["g"].astype(str).tolist(), s["p"].astype(str).tolist())
            rows.append(dict(variant=label, model=MODEL, variable="any_abnormal", year=y,
                             n=len(s), kappa=round(k, 3), F1_pos=round(f1, 3), acc=round(po, 3),
                             gate_pass=""))
        n12 = sum(1 for r in rows if r["variant"] == label and r["year"] == "overall"
                  and r["variable"] != "any_abnormal" and r["gate_pass"])
        print(f"  {label}: {n12}/12 gate PASS；any_abnormal overall n={len(ay)} "
              f"κ={k_any:.3f} F1={f1_any:.3f}")
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(RES, "prompt_perturbation_eval.csv"),
               index=False, encoding="utf-8-sig")
    print(f"\n-> results/prompt_perturbation_eval.csv")
    return out


def main():
    limit = 0
    eval_only = "--eval-only" in sys.argv
    for a in sys.argv[1:]:
        if a.startswith("--limit="):
            limit = int(a.split("=", 1)[1])
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    v0 = open(PROMPT_V0, encoding="utf-8").read()
    print(f"baseline prompt v1 hash={sha(v0)}  (manifest 记录 dbb1ebe717ad3497)")
    out_paths = {"baseline_v1": os.path.join(DATA, "llm_ecg570_v1__qwen2.5_14b.csv")}
    if not eval_only:
        for variant in VARIANTS:
            print(f"\n== 跑批 variant={variant} ==")
            out_paths[variant] = run_variant(variant, limit)
    print("\n== 评估（29 口径 + any_abnormal）==")
    evaluate(out_paths)
    return 0


if __name__ == "__main__":
    sys.exit(main())
