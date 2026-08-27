#!/usr/bin/env python3
"""md2pdf.py — 小册子 Markdown → PDF（HTML/CSS → 浏览器 headless 打印）

用法:
    python md2pdf.py input.md [output.pdf]

输入 Markdown 约定（AI 按此生成；本文件是排版能力边界的单一事实源）:
    # 书名（首个块的标题渲染为封面）
    ## 卡片标题（卡片内标题）
    --- 单独一行 = 卡片分隔（视觉卡片边界；代码块内不要出现单独一行 ---）
    | a | b | 连续行 = 简单表格（首行为表头，|---|---| 分隔行自动丢弃）
    ``` 围栏 = 代码块（代码块之后同卡片内容照常渲染）
    其余：段落 / - 列表 / > 引用 / **粗体** / *斜体* / `行内代码`
"""

import html
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time


def find_browser():
    """定位可用的 Chromium 系浏览器（Edge / Chrome / Chromium）用于 headless 打印。"""
    env = os.environ.get("MD2PDF_BROWSER")
    if env:
        return env if os.path.exists(env) else None

    candidates = []
    if os.name == "nt":
        program_files = [
            os.environ.get("PROGRAMFILES", ""),
            os.environ.get("PROGRAMFILES(X86)", ""),
            os.environ.get("LOCALAPPDATA", ""),
        ]
        for base in program_files:
            if not base:
                continue
            candidates += [
                os.path.join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
                os.path.join(base, "Google", "Chrome", "Application", "chrome.exe"),
            ]
    elif sys.platform == "darwin":
        apps = "/Applications"
        candidates += [
            os.path.join(apps, name, "Contents", "MacOS", binary)
            for name, binary in [
                ("Google Chrome", "Google Chrome"),
                ("Microsoft Edge", "Microsoft Edge"),
                ("Chromium", "Chromium"),
            ]
        ]
    else:
        candidates += [
            shutil.which(name)
            for name in ["google-chrome", "google-chrome-stable", "microsoft-edge",
                         "microsoft-edge-stable", "chromium", "chromium-browser"]
        ]

    return next((path for path in candidates if path and os.path.exists(path)), None)


BROWSER = find_browser()

PDF_WAIT_TIMEOUT = 15  # 秒：等待 headless 浏览器把 PDF 落盘

CSS = """
<style>
/* 方案 D · 暖纸瑞士：米白纸感 + 深棕黑 + 朱红点缀 + 棕灰细线
   内容排版结构（卡片/A.a 编号）不变，仅背景/配色/线条 */
body {
  font-family: "Microsoft YaHei", "PingFang SC", "SimSun", sans-serif;
  margin: 2cm;
  line-height: 1.9;
  color: #2b2b2b;
  background: #faf6ef;
  font-size: 14px;
}
h1 {
  font-size: 28px; text-align: center; margin: 0 0 8px 0;
  color: #2b2b2b; border-bottom: 1px solid #d8cfc0; padding-bottom: 12px;
}
h2 {
  font-size: 22px; margin: 20px 0 10px 0; color: #2b2b2b;
  border-bottom: 1px solid #d8cfc0; padding-bottom: 6px;
}
h3 { font-size: 18px; margin: 14px 0 8px 0; }
p { margin: 8px 0; }
ul { margin: 8px 0; padding-left: 1.6em; }
li { margin: 4px 0; }
blockquote {
  border-left: 3px solid #c0392b;
  background: #f3ece0;
  margin: 10px 0;
  padding: 8px 14px;
  color: #4a3a1a;
}
strong { color: #2b2b2b; }
em { color: #6a6a6a; }
code {
  background: #efe8db; padding: 1px 5px; color: #2b2b2b;
  font-family: Consolas, monospace;
}
pre {
  background: #efe8db; padding: 10px 14px; overflow-x: auto;
  font-family: Consolas, monospace; font-size: 12.5px; line-height: 1.5;
}
table {
  border-collapse: collapse; margin: 10px 0; width: 100%; font-size: 13px;
}
th, td { border: 1px solid #d8cfc0; padding: 6px 10px; text-align: left; }
th { background: #f3ece0; }
hr { border: none; border-top: 1px solid #d8cfc0; margin: 22px 0; }
.cover { text-align: center; margin-bottom: 30px; }
.cover .sub { color: #6a6a6a; font-size: 13px; }
.card {
  border: 1px solid #d8cfc0;
  border-radius: 8px;
  padding: 18px 22px;
  margin: 18px 0;
  background: #fffdf9;
  page-break-inside: avoid;
}
.card h2 { margin-top: 0; }
</style>
"""


def inline(md_text):
    """处理行内标记：**粗体** *斜体* `代码`"""
    md_text = html.escape(md_text)
    md_text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", md_text)
    md_text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", md_text)
    md_text = re.sub(r"`(.+?)`", r"<code>\1</code>", md_text)
    return md_text


def table_to_html(rows):
    """| a | b | 连续行 → <table>（首行表头，--- 分隔行自动丢弃）"""
    parsed = []
    for r in rows:
        cells = [c.strip() for c in r.strip().strip("|").split("|")]
        if cells and all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c != ""):
            continue
        parsed.append(cells)
    if not parsed:
        return ""
    head, body_rows = parsed[0], parsed[1:]
    out = ["<table><thead><tr>"]
    out += [f"<th>{inline(c)}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for cells in body_rows:
        out.append("<tr>" + "".join(f"<td>{inline(c)}</td>" for c in cells) + "</tr>")
    out.append("</tbody></table>")
    return "".join(out)


def block_to_html(lines):
    """一个块（封面或卡片）→ HTML。游标推进，代码块/表格后同卡片内容不丢。"""
    out = []
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if not stripped:
            i += 1
            continue
        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # 跳过收尾围栏
            out.append("<pre><code>" + html.escape("\n".join(code_lines)) + "</code></pre>")
        elif stripped.startswith("|"):
            tbl = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                tbl.append(lines[i])
                i += 1
            html_table = table_to_html(tbl)
            if html_table:
                out.append(html_table)
            continue
        elif stripped.startswith("### "):
            out.append(f"<h3>{inline(stripped[4:])}</h3>")
        elif stripped.startswith("## "):
            out.append(f"<h2>{inline(stripped[3:])}</h2>")
        elif stripped.startswith("# "):
            out.append(f"<h1>{inline(stripped[2:])}</h1>")
        elif stripped.startswith("> "):
            out.append(f"<blockquote>{inline(stripped[2:])}</blockquote>")
        elif stripped.startswith("- "):
            out.append(f"<li>{inline(stripped[2:])}</li>")
        else:
            out.append(f"<p>{inline(stripped)}</p>")
        i += 1
    return "\n".join(out)


def md_to_html(md_text):
    lines = md_text.splitlines()
    blocks = []
    cur = []
    for line in lines:
        if line.strip() == "---":
            blocks.append(cur)
            cur = []
        else:
            cur.append(line)
    if cur:
        blocks.append(cur)

    parts = ['<!DOCTYPE html><html lang="zh"><head><meta charset="utf-8">' + CSS + "</head><body>"]
    first = True
    for blk in blocks:
        content = block_to_html(blk)
        if not content:
            continue
        if first:
            # 封面：书名 + 说明
            parts.append(f'<div class="cover">{content}<p class="sub">一天能读完的知识框架小册子</p></div>')
            first = False
        else:
            parts.append(f'<div class="card">{content}</div>')
    parts.append("</body></html>")
    return "\n".join(parts)


def html_to_pdf(html_path, pdf_path, tmp_dir):
    if BROWSER is None:
        raise RuntimeError(
            "找不到 Chromium 系浏览器（Edge / Chrome / Chromium）。"
            "可设环境变量 MD2PDF_BROWSER 指向浏览器可执行文件。"
        )
    url = "file:///" + html_path.replace("\\", "/")
    cmd = [
        BROWSER,
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--user-data-dir={os.path.join(tmp_dir, 'profile')}",
        f"--print-to-pdf={pdf_path}",
        url,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"浏览器打印失败: {result.stderr[-500:]}")
    # headless 浏览器可能先返回、后落盘，等文件大小稳定再判定
    deadline = time.time() + PDF_WAIT_TIMEOUT
    prev = -1
    while time.time() < deadline:
        size = os.path.getsize(pdf_path) if os.path.exists(pdf_path) else -1
        if size > 0 and size == prev:
            return
        prev = size
        time.sleep(0.3)
    raise RuntimeError(
        f"PDF 未生成或为空（等待 {PDF_WAIT_TIMEOUT}s 超时）: {pdf_path}")


def main():
    if len(sys.argv) < 2:
        print("用法: python md2pdf.py input.md [output.pdf]")
        sys.exit(1)
    md_path = sys.argv[1]
    pdf_path = sys.argv[2] if len(sys.argv) > 2 else os.path.splitext(md_path)[0] + ".pdf"
    pdf_path = os.path.abspath(pdf_path)

    with open(md_path, encoding="utf-8") as f:
        md_text = f.read()

    html_text = md_to_html(md_text)
    tmp_dir = tempfile.mkdtemp(prefix="rbook_")
    try:
        tmp_html = os.path.join(tmp_dir, "book.html")
        with open(tmp_html, "w", encoding="utf-8") as f:
            f.write(html_text)
        html_to_pdf(tmp_html, pdf_path, tmp_dir)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
    print(f"OK: {pdf_path}")


if __name__ == "__main__":
    main()
