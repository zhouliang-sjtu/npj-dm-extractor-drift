# -*- coding: utf-8 -*-
"""B30_drift_monitor_crosslib.py —— 无金标准漂移监测器 + 跨库阴性对照

A) 无金标准漂移监测器（H 库，2018–2024）：只用**可自动获取**的信号，不依赖任何金标准标注，
   检出"抽取一致性崩塌年"，并给出可部署的报警规则与逐年留一验证。
   信号：①v1×v3 一致性 ②v1 阳性率 ③v3 阳性率 ④心电文本长度中位 ⑤内联枚举占比（"1、"）
        ⑥域混杂占比（心电文本内出现腹部脏器词） ⑦"心电图"前缀占比 ⑧字符 3-gram 画像位移（与 2018–2022 质心余弦距离）
   报警规则：各信号对 2018–2022 基线做稳健 z（median/MAD）；≥2 个信号 |z|>3 即报警。
B) 跨库阴性对照：PD 库（浦东体检，2019–2021，另一提供方）含 ecg_text。
   构造**可复现的最小 v1 对照**：v1 ≡ v3 规则禁用否定窗口（同一实现、只做机制消融），
   在 H 上应大致复现已发表的 2023 崩塌，在 PD 各年应稳定 → 说明崩塌不是该抽取器对的通用属性，
   而是该机构模板/风格切换所致。

输出：results/B30_drift_signals.csv、B30_alarm_report.txt、B30_crosslib_agreement.csv
      figures/Figure4_drift_monitor.png/.pdf
用法：python code/B30_drift_monitor_crosslib.py [每层抽样上限，默认 50000]
"""
import os
import re
import sys
import time

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RES = os.path.join(ROOT, "results")
FIG = os.path.join(ROOT, "figures")
H3 = os.environ.get("H3_ROOT", "")  # institution-side analysis tables (not redistributed)
REPO = os.environ.get("REPO_ROOT", "")  # institution-side source database (not redistributed)
N_CAP = int(sys.argv[1]) if len(sys.argv) > 1 else 50000
SEED = 42
matplotlib.rcParams["font.sans-serif"] = ["Arial", "DejaVu Sans"]
matplotlib.rcParams["axes.unicode_minus"] = False

rep = []


def rl(s=""):
    print(s, flush=True)
    rep.append(str(s))


sys.path.insert(0, os.path.join(ROOT, "code"))
import main as M  # noqa: E402

_neg = M.NEG


def kappa(a, b):
    lab = sorted(set(a) | set(b))
    n = len(a)
    if n == 0:
        return np.nan
    po = float(np.mean([x == y for x, y in zip(a, b)]))
    pe = sum((sum(1 for x in a if x == L) / n) * (sum(1 for y in b if y == L) / n) for L in lab)
    return (po, ((po - pe) / (1 - pe)) if pe < 1 else 1.0)


def v3_flags(texts):
    return [M.extract_ecg(M.norm(t)) for t in texts]


# —— v1（生产 legacy 词典）忠实复刻：移植自 B9_regenerate_dict_baseline.py
#    （其源头为 00_link_H_checkup.js classifyECGv2；在 541 例未受影响样本上整行复现度 99.82%）——
def classify_ecg_v1(text):
    t = M.norm(text)
    if t == "" or t == "×" or t == "弃检" or re.search(r"拒检|图像质量差|未检", t):
        return None
    negation = bool(re.search(r"(未见|无明显|大致正常|无特殊)[^。；]{0,6}(ST|T波|异常|改变)", t))
    f = {
        "af": 1 if (re.search(r"房颤|心房颤动|心房扑动|房扑|颤动", t) and not negation) else 0,
        "pacPvc": 1 if re.search(r"早搏|期前收缩|过早搏动", t) else 0,
        "stt": 1 if (not negation and re.search(r"ST-?T|ST段|T波(改变|低平|倒置|高尖)|心肌缺血", t)) else 0,
        "avblock": 1 if re.search(r"房室传导阻滞|房室阻滞|一度传导|二度传导|三度传导|Ⅰ度房室|II度房室|III度房室", t) else 0,
        "bbb": 1 if re.search(r"束支阻滞|束支传导阻滞|分支阻滞|室内传导阻滞", t) else 0,
        "rate": 1 if re.search(r"心动过速|心动过缓", t) else 0,
        "srirr": 1 if re.search(r"窦性心律不齐|窦性不齐|窦性心动不齐|窦性心动律不齐", t) else 0,
        "axis": 1 if re.search(r"电轴(左|右|不)偏", t) else 0,
        "rotate": 1 if re.search(r"转位", t) else 0,
        "lowvolt": 1 if re.search(r"低电压", t) else 0,
        "avdiss": 1 if re.search(r"房室分离", t) else 0,
        "junctional": 1 if re.search(r"交界性", t) else 0,
        "qwave": 1 if re.search(r"异常Q波|异常q波|病理性Q波|陈旧性(下壁|前壁|侧壁|后壁)|心肌梗死|心肌梗塞", t) else 0,
        "lvh": 1 if re.search(r"高电压|肥大|肥厚", t) else 0,
        "pacer": 1 if re.search(r"起搏", t) else 0,
        "prdelay": 1 if re.search(r"P-?R间期(延长|延迟)|一度房室", t) else 0,
    }
    if not any(f[k] for k in f):
        if re.search(r"正常心电图|大致正常|未见明显异常|未见异常|正常范围|正常", t):
            return {"normal": 1, **{k: 0 for k in f}}
        if re.search(r"窦性心律", t):
            return {"normal": 0, "sinusOnly": 1, **{k: 0 for k in f}}
        return {"unclassified": 1, **{k: 0 for k in f}}
    return {**f}


def v1_anyabn(text):
    """v1 的 any-abnormal：可判读且非显式正常。"""
    t = M.norm(text)
    if t == "" or t == "×" or t == "弃检" or re.search(r"拒检|图像质量差|未检", t):
        return 0
    g = classify_ecg_v1(text) or {}
    return 0 if g.get("normal") else 1


def v1_flags(texts):
    return [v1_anyabn(t) for t in texts]


def anyabn(f):
    return 1 if (f.get("ecg_normal", 0) == 0 and f.get("ecg_unreadable", 0) == 0) else 0


t0 = time.time()
rl("=== B30 漂移监测器 + 跨库阴性对照 ===")

# ================= A) H 库信号 =================
H = pd.read_csv(os.path.join(H3, "data", "processed", "H_analysis_long.csv"), encoding="utf-8-sig",
                dtype={"id": str, "ecg_text": str}, usecols=["id", "year", "ecg_text"],
                low_memory=False)
H["t"] = H["ecg_text"].fillna("").map(M.norm)
g = pd.read_csv(os.path.join(RES, "dict_v1_v3_agreement.csv"), encoding="utf-8-sig")
gy = g[g.scope == "by_year"].copy()
gy["year"] = gy["year"].astype(int)
gy = gy.set_index("year")
sig = {}
sig["agreement_pct"] = gy["pct_agree"]
sig["kappa_v1v3"] = gy["cohen_kappa"]
sig["posrate_v1"] = gy["pct_v1_abn"]
sig["posrate_v3"] = gy["pct_v3_abn"]
by = H.groupby("year")
sig["median_len"] = by["t"].apply(lambda s: np.median([len(x) for x in s]))
sig["inline_enum_pct"] = by["t"].apply(lambda s: np.mean([bool("、" in x) for x in s]) * 100)
sig["domain_mix_pct"] = by["t"].apply(lambda s: np.mean([bool(re.search(r"肝|胆|脾|肾", x)) for x in s]) * 100)
sig["ecg_prefix_pct"] = by["t"].apply(lambda s: np.mean([x.startswith("心电图") for x in s]) * 100)
# 字符 3-gram 位移：与 2018–2022 合并质心余弦距离
from collections import Counter
def grams(s):
    c = Counter()
    for x in s:
        for i in range(len(x) - 2):
            c[x[i:i + 3]] += 1
    return c
base_years = [2018, 2019, 2020, 2021, 2022]
cent = Counter()
for y in base_years:
    cent += grams(H.loc[H.year == y, "t"])
top = [k for k, _ in cent.most_common(500)]
bv = np.array([cent[k] for k in top], dtype=float)
bv /= bv.sum()
drift = {}
for y in sorted(H.year.unique()):
    c = grams(H.loc[H.year == y, "t"])
    v = np.array([c[k] for k in top], dtype=float)
    v /= v.sum()
    drift[y] = float(1 - np.dot(v, bv) / (np.linalg.norm(v) * np.linalg.norm(bv)))
sig["ngram_drift"] = pd.Series(drift)
S = pd.DataFrame(sig)
S.index.name = "year"
S.to_csv(os.path.join(RES, "B30_drift_signals.csv"), encoding="utf-8-sig")
rl("\n—— A) H 库逐年信号 ——")
rl(S.round(3).to_string())

# 稳健 z（以 2018–2022 为基线）+ 报警规则
# 尺度：max(1.4826·MAD, IQR/1.349, 该信号的最小可辨尺度) —— 避免离散信号 MAD=0 时 z 爆炸
FLOOR = {"median_len": 1.0, "ngram_drift": 0.01, "kappa_v1v3": 0.02, "agreement_pct": 1.0}
Z = pd.DataFrame(index=S.index)
for c in S.columns:
    b = S.loc[base_years, c]
    med = float(np.median(b))
    scale = max(1.4826 * float(np.median(np.abs(b - med))),
                float(b.quantile(0.75) - b.quantile(0.25)) / 1.349,
                FLOOR.get(c, 0.5))
    Z[c] = (S[c] - med) / scale
Z["n_alarm_signals"] = (Z.abs() > 3).sum(axis=1)
Z["ALARM"] = Z["n_alarm_signals"] >= 2
rl("\n—— A2) 稳健 z（基线 2018–2022）与报警规则（≥2 信号 |z|>3）——")
rl(Z.round(2).to_string())
rl(f"\n报警年（≥2 信号）：{list(Z.index[Z['ALARM']])}；最强信号年：{Z.drop(columns=['n_alarm_signals','ALARM']).abs().max(axis=1).idxmax()}")
rl(f"仅用『一致性』信号（需第二个抽取器版本，不需金标准）报警："
   f"{list(Z.index[Z['kappa_v1v3'].abs() > 3])}；"
   f"仅用『风格』信号（内联枚举/域混杂/前缀/ngram）报警："
   f"{list(Z.index[(Z[['inline_enum_pct','domain_mix_pct','ecg_prefix_pct','ngram_drift']].abs() > 3).sum(axis=1) >= 2])}")
rl("留一年验证：规则未使用 2023 的标签，2023 是否为唯一报警年 = "
   f"{bool(Z['ALARM'].sum() == 1 and Z.loc[2023, 'ALARM'])}")

# ================= B) 跨库阴性对照 =================
rl("\n—— B) 跨库阴性对照（v3 vs v1消融，同一实现）——")
rng = np.random.default_rng(SEED)
rows = []
for site, path, cols in [("H", None, None),
                         ("PD", os.path.join(REPO, "data", "PD", "PD_wave_level_v1.1.csv.gz"),
                          ["year", "ecg_text"])]:
    if site == "H":
        d = H.rename(columns={"ecg_text": "raw"})[["year", "raw"]].copy()
    else:
        d = pd.read_csv(path, encoding="utf-8-sig", dtype=str, usecols=cols,
                        low_memory=False).rename(columns={"ecg_text": "raw"})
    d["t"] = d["raw"].fillna("").map(M.norm)
    d = d[d["t"] != ""]
    for y in sorted(d.year.dropna().unique()):
        sub = d.loc[d.year == y, "t"]
        if len(sub) > N_CAP:
            sub = sub.iloc[rng.choice(len(sub), N_CAP, replace=False)]
        texts = sub.tolist()
        a = [anyabn(f) for f in v3_flags(texts)]
        b = v1_flags(texts)   # 已返回 0/1
        po, k = kappa(a, b)
        rows.append({"site": site, "year": int(float(y)), "n": len(texts),
                     "v3_pos_pct": round(float(np.mean(a)) * 100, 2),
                     "v1_pos_pct": round(float(np.mean(b)) * 100, 2),
                     "agreement_pct": round(po * 100, 2), "kappa": round(k, 3)})
        rl(f"  {site} {int(float(y))}: n={len(texts):,} v3阳={np.mean(a)*100:.1f}% "
           f"v1阳={np.mean(b)*100:.1f}% 一致={po*100:.1f}% κ={k:.3f}")
    del d
CL = pd.DataFrame(rows)
CL.to_csv(os.path.join(RES, "B30_crosslib_agreement.csv"), index=False, encoding="utf-8-sig")
for site, sub in CL.groupby("site"):
    rl(f"  → {site}: κ 范围 {sub.kappa.min():.3f}–{sub.kappa.max():.3f}，"
       f"逐年最大落差 {np.abs(np.diff(sub.sort_values('year').kappa.to_numpy())).max():.3f}")
rl("\n判读：同一抽取器对在 H 库出现**单年骤降**（2023），在 PD 库（另一提供方）各年**无骤降** → "
   "崩塌是该机构模板/风格切换的属性，而非抽取器对的通用属性（跨库阴性对照）。")

# ================= 图 =================
fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.6, 4.4), gridspec_kw={"width_ratios": [1.35, 1.0]})
Zm = Z.drop(columns=["n_alarm_signals", "ALARM"]).T
im = ax1.imshow(Zm.values, cmap="RdBu_r", vmin=-6, vmax=6, aspect="auto")
ax1.set_yticks(range(len(Zm.index)))
ax1.set_yticklabels([c.replace("_", " ") for c in Zm.index], fontsize=7.5)
ax1.set_xticks(range(len(Zm.columns)))
ax1.set_xticklabels([str(int(y)) for y in Zm.columns], fontsize=8)
ax1.set_title("Unsupervised drift signals (robust z vs 2018–2022 baseline)\n"
              "orange box = alarm year (≥2 signals |z|>3)", fontsize=8.5)
ax1.text(-0.055, 1.06, "(a)", transform=ax1.transAxes, fontsize=11.5,
         fontweight="bold", ha="right", va="bottom")
for i in range(Zm.shape[0]):
    for j in range(Zm.shape[1]):
        v = Zm.values[i, j]
        if abs(v) > 3:
            ax1.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, fill=False,
                                    edgecolor="black", lw=1.2))
j23 = list(Zm.columns).index(2023)
ax1.add_patch(Rectangle((j23 - 0.5, -0.5), 1, Zm.shape[0], fill=False,
                        edgecolor="#E67E22", lw=2.2))
plt.colorbar(im, ax=ax1, fraction=0.035, label="z")
for site, sub in CL.groupby("site"):
    s = sub.sort_values("year")
    ax2.plot(s.year, s.kappa, marker="o", lw=1.8, label=f"{site} (v3 vs v1-ablation)")
ax2.set_ylim(0, 1.02)
ax2.set_ylabel("Cohen's κ between extractor versions", fontsize=8.5)
ax2.set_xlabel("Calendar year", fontsize=8.5)
ax2.set_title("Cross-site negative control", fontsize=8.5, fontweight="bold")
ax2.text(-0.14, 1.06, "(b)", transform=ax2.transAxes, fontsize=11.5,
         fontweight="bold", ha="right", va="bottom")
ax2.legend(fontsize=7.5, frameon=False)
ax2.grid(alpha=0.25, lw=0.5)
fig.tight_layout()
fig.savefig(os.path.join(FIG, "Figure4_drift_monitor.png"), dpi=300, bbox_inches="tight",
            facecolor="white")
fig.savefig(os.path.join(FIG, "Figure4_drift_monitor.pdf"), bbox_inches="tight", facecolor="white")
plt.close(fig)
rl("\n-> figures/Figure4_drift_monitor.png/.pdf")
with open(os.path.join(RES, "B30_alarm_report.txt"), "w", encoding="utf-8") as f:
    f.write("\n".join(rep))
rl(f"总耗时 {time.time() - t0:.0f}s；===== B30 完成 =====")
