# -*- coding: utf-8 -*-
"""S2_S3_supplementary_figs.py v3 —— SI 补充图归位
v3（宪章合规修订）：删除原 S2"域指纹矩阵"——其数据源为治理专班对治理前原始 Excel 的
B36_full_domain_scan.csv（治理前问题状态，非论文分析数据库），违反数据切口锚定条款；
域校验以方法学构件身份保留在正文 Methods 与 SI SM5/SM7 文字中（固化库 7 年无异域报警，
复检证据见 results/B39_v32_domain_recheck.txt）。
本脚本现在仅做：SIMEX 实测κ校正图归位为 Supplementary Figure S2。
输出：figures/SupplementaryFigureS2_SIMEX_measured_kappa.png/.pdf
"""
import os
import shutil

P1 = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # repository root
RES = os.path.join(P1, "results")
FIG = os.path.join(P1, "figures")

src = os.path.join(RES, "fig5b_simex_measured.png")
src_pdf = os.path.join(RES, "fig5b_simex_measured.pdf")
dst = os.path.join(FIG, "SupplementaryFigureS2_SIMEX_measured_kappa.png")
dst_pdf = os.path.join(FIG, "SupplementaryFigureS2_SIMEX_measured_kappa.pdf")
for s, dd in [(src, dst), (src_pdf, dst_pdf)]:
    if os.path.exists(s):
        shutil.copyfile(s, dd)
        print("copied:", os.path.basename(dd))
    else:
        print("missing (27 regenerates):", s)
