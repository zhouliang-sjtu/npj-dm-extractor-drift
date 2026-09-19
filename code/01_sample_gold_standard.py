# -*- coding: utf-8 -*-
"""01_sample_gold_standard.py —— 三域金标准抽样（seed=42可复现）
① H社区ECG 600（每年60＋特殊层）
② PG echo 600（v2分层：abnormal全300/normal 150/normal_variant 150）
③ PG腹超 600（fatty 300/非fatty 300）
"""
import os
import re
import numpy as np
import pandas as pd
import psycopg2

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
OUT = os.path.join(BASE, "data")
os.makedirs(OUT, exist_ok=True)
SEED = 42

# ---------- ① H社区ECG ----------
df = pd.read_csv(os.environ["H_CHECKUP_LONG"]  # institution-side source table (not redistributed),
                 encoding="utf-8-sig", dtype={"id": str}, low_memory=False)
ecg = df[df["ecg_text"].notna() & (df["ecg_text"].astype(str).str.strip() != "")].copy()
ecg["text"] = ecg["ecg_text"].astype(str).str.slice(0, 150)
parts = []
for y, g in ecg.groupby("year"):
    parts.append(g.sample(min(60, len(g)), random_state=SEED))
special = pd.concat([
    ecg[ecg["ecg_text"].str.contains("房颤|心房颤动", na=False)].sample(min(50, (ecg["ecg_text"].str.contains("房颤|心房颤动")).sum()), random_state=SEED),
    ecg[ecg["ecg_text"].str.contains("传导阻滞", na=False)].sample(min(50, (ecg["ecg_text"].str.contains("传导阻滞")).sum()), random_state=SEED + 1),
    ecg[ecg["ecg_text"].str.contains("ST", na=False)].sample(min(50, (ecg["ecg_text"].str.contains("ST")).sum()), random_state=SEED + 2),
])
ecg_gold = pd.concat(parts + [special]).drop_duplicates(subset=["id", "year"])
ecg_gold_out = ecg_gold[["year", "id", "text"]].copy()
ecg_gold_out.insert(0, "sample_id", ["ECG_{:04d}".format(i + 1) for i in range(len(ecg_gold_out))])
ecg_gold_out.to_csv(os.path.join(OUT, "gold_ecg_H.csv"), index=False, encoding="utf-8-sig")
print(f"① ECG金标准: {len(ecg_gold_out)} 份（年度分布 {ecg_gold_out['year'].value_counts().sort_index().to_dict()}）")

# ---------- ② PG echo ----------
def rule_v2(t):
    if not t or t.strip() in ("×", "弃检"): return None
    neg = lambda seg: bool(re.search(r"(未见|无明显|无)[^。；]{0,8}" + seg, t))
    lvh = bool(re.search(r"(室间隔|左室后壁|左室壁)[^。；]{0,6}(增厚|肥厚)", t)) and not neg("增厚")
    la = bool(re.search(r"左房[^。；]{0,8}(增大|扩大|增宽)", t)) and not neg("增大")
    ef_m = re.search(r"(?:EF|LVEF|射血分数)[^0-9]{0,10}(\d{2,3})", t)
    ef_low = ef_m and float(ef_m.group(1)) < 50
    sig_ref = bool(re.search(r"(中度|重度)[^。；]{0,6}(返流|反流)", t))
    mild_ref = bool(re.search(r"(少量|轻微|轻度)[^。；]{0,6}(返流|反流)", t))
    other = bool(re.search(r"早搏|房颤|传导阻滞|起搏|血栓|赘生物|心包积液", t))
    if lvh or la or ef_low or sig_ref or other: return "abnormal"
    if mild_ref: return "normal_variant"
    return "normal"

conn = psycopg2.connect(host="127.0.0.1", port=5555, dbname="inter_mysql_tb", user="postgres")
echo = pd.read_sql("""SELECT c.report_id, c.item_result, u.his_id, u.pe_queue_date
                      FROM raw_check_result_view_input_20251224_135530 c
                      JOIN raw_tj_userinfo_view_input_20251222_211802 u ON c.report_id=u.report_id
                      WHERE c.item_combination_name='心脏超声检查' AND c.item_result IS NOT NULL""", conn)
conn.close()
echo["text"] = echo["item_result"].apply(lambda x: html.unescape(str(x)) if False else str(x))
try:
    import html as _h
    echo["text"] = echo["item_result"].apply(lambda x: _h.unescape(str(x)))
except Exception:
    pass
echo = echo.drop_duplicates(subset=["his_id", "pe_queue_date"])
echo["rule_v2"] = echo["text"].apply(rule_v2)
parts = [echo[echo["rule_v2"] == "abnormal"].sample(min(300, (echo["rule_v2"] == "abnormal").sum()), random_state=SEED),
         echo[echo["rule_v2"] == "normal"].sample(min(150, (echo["rule_v2"] == "normal").sum()), random_state=SEED),
         echo[echo["rule_v2"] == "normal_variant"].sample(min(150, (echo["rule_v2"] == "normal_variant").sum()), random_state=SEED)]
echo_gold = pd.concat(parts)
echo_gold_out = echo_gold[["his_id", "pe_queue_date", "text"]].copy()
echo_gold_out.columns = ["id", "exam_date", "text"]
echo_gold_out["text"] = echo_gold_out["text"].str.slice(0, 600)
echo_gold_out.insert(0, "sample_id", ["ECHO_{:04d}".format(i + 1) for i in range(len(echo_gold_out))])
echo_gold_out.to_csv(os.path.join(OUT, "gold_echo_PG.csv"), index=False, encoding="utf-8-sig")
print(f"② echo金标准: {len(echo_gold_out)} 份")

# ---------- ③ PG腹超 ----------
conn = psycopg2.connect(host="127.0.0.1", port=5555, dbname="inter_mysql_tb", user="postgres")
abd = pd.read_sql("""SELECT c.report_id, c.item_result, u.his_id, u.pe_queue_date
                     FROM raw_check_result_view_input_20251224_135530 c
                     JOIN raw_tj_userinfo_view_input_20251222_211802 u ON c.report_id=u.report_id
                     WHERE c.item_combination_name='腹部超声检查' AND c.item_result IS NOT NULL""", conn)
abd["text"] = abd["item_result"].apply(lambda x: str(x))
abd = abd.drop_duplicates(subset=["his_id", "pe_queue_date"])
abd["fatty"] = abd["text"].str.contains(r"脂肪肝|细密|远场回声衰减|回声衰减", regex=True).astype(int)
abd_gold = pd.concat([
    abd[abd["fatty"] == 1].sample(min(300, (abd["fatty"] == 1).sum()), random_state=SEED),
    abd[abd["fatty"] == 0].sample(min(300, (abd["fatty"] == 0).sum()), random_state=SEED),
])
abd_gold_out = abd_gold[["his_id", "pe_queue_date", "text"]].copy()
abd_gold_out.columns = ["id", "exam_date", "text"]
abd_gold_out["text"] = abd_gold_out["text"].str.slice(0, 600)
abd_gold_out.insert(0, "sample_id", ["ABD_{:04d}".format(i + 1) for i in range(len(abd_gold_out))])
abd_gold_out.to_csv(os.path.join(OUT, "gold_abdus_PG.csv"), index=False, encoding="utf-8-sig")
print(f"③ PG腹超金标准: {len(abd_gold_out)} 份（fatty=1: {(abd_gold['fatty']==1).sum()}）")

print("\n注：④H社区腹超抽样待 01b_extract_H_us_text.js 生成 H_us_text_long.csv 后运行 01c（同规则）")
