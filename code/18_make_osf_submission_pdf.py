# -*- coding: utf-8 -*-
"""18_make_osf_submission_pdf.py —— 生成 OSF 提交版 PDF（英文正文，去除中文使用说明/附注）
输出：30_paper-npj/osf_submission/OSF_Registration_20260903.md 与 .pdf
"""
import os
import re
import subprocess
import sys

import markdown

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "30_paper-npj", "osf_preregistration.md")
OUTDIR = os.path.join(ROOT, "30_paper-npj", "osf_submission")
MD_OUT = os.path.join(OUTDIR, "OSF_Registration_20260903.md")
HTML_OUT = os.path.join(OUTDIR, "OSF_Registration_20260903.html")
PDF_OUT = os.path.join(OUTDIR, "OSF_Registration_20260903.pdf")

CSS = """
body { font-family: 'Times New Roman', Georgia, serif; font-size: 11.5pt;
       line-height: 1.45; max-width: 760px; margin: 32px auto; color: #111; }
h1 { font-size: 17pt; border-bottom: 2px solid #333; padding-bottom: 6px; }
h2 { font-size: 14pt; margin-top: 22px; }
h3 { font-size: 12.5pt; margin-top: 18px; }
strong { color: #000; }
hr { border: none; border-top: 1px solid #999; margin: 18px 0; }
"""


def clean(text: str) -> str:
    # 去页首中文使用说明块（从 "> **使用说明" 到其后第一个 "---"）
    text = re.sub(r"> \*\*使用说明（中文[\s\S]*?\n---\n", "", text, count=1)
    # 去文末中文附注（从 "### 中文附注" 到文件尾）
    text = re.sub(r"\n### 中文附注（不提交 OSF[\s\S]*$", "", text)
    return text.strip() + "\n"


def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    os.makedirs(OUTDIR, exist_ok=True)
    text = clean(open(SRC, encoding="utf-8").read())
    assert "使用说明" not in text and "中文附注" not in text, "中文块未删净"
    open(MD_OUT, "w", encoding="utf-8").write(text)

    body = markdown.markdown(text, extensions=["extra", "sane_lists"])
    html = (f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<style>{CSS}</style></head><body>{body}</body></html>")
    open(HTML_OUT, "w", encoding="utf-8").write(html)

    for edge in (r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                 r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"):
        if os.path.exists(edge):
            uri = os.path.abspath(HTML_OUT).replace("\\", "/")
            r = subprocess.run([edge, "--headless", "--disable-gpu", "--no-pdf-header-footer",
                                f"--print-to-pdf={PDF_OUT}", f"file:///{uri}"],
                               capture_output=True, text=True, timeout=120)
            if os.path.exists(PDF_OUT):
                break
    if os.path.exists(PDF_OUT):
        print(f"PDF  -> {PDF_OUT}（{os.path.getsize(PDF_OUT)//1024} KB）")
    else:
        print("PDF 生成失败（未找到 Edge），HTML 已备：", HTML_OUT)
    print(f"MD   -> {MD_OUT}（{len(text.splitlines())} 行）")


if __name__ == "__main__":
    sys.exit(main())
