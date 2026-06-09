# -*- coding: utf-8 -*-
"""
DDL Scheduled Task - 定时任务入口
每日自动生成 DDL 报告 → HTML → PDF，保存到桌面
"""

import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime

# ============ 路径配置 ============
SKILL_DIR = Path(__file__).parent
TASK_FILE = Path(r"C:\Users\lenovo\Desktop\Task.txt")
OUTPUT_DIR = Path(r"C:\Users\lenovo\Desktop\DDl")
HTML2PDF_JS = Path(r"C:\Users\lenovo\Desktop\拆书计划\html2pdf.js")

# 临时 HTML 输出位置
TEMP_DIR = SKILL_DIR / "temp"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def main():
    now = datetime.now()
    date_label = f"{now.month}-{now.day}"  # 如 4-17
    
    log(f"===== DDL 定时任务启动 ({date_label}) =====")
    
    # 1. 检查 Task.txt
    if not TASK_FILE.exists():
        log(f"[错误] 任务文件不存在: {TASK_FILE}")
        sys.exit(1)
    
    # 2. 读取任务
    with open(TASK_FILE, "r", encoding="utf-8") as f:
        task_lines = f.readlines()
    
    task_lines = [l.strip() for l in task_lines if l.strip()]
    log(f"[读取] {len(task_lines)} 条任务")
    
    # 3. 导入生成器并生成 HTML
    sys.path.insert(0, str(SKILL_DIR))
    from ddl_html_generator import process_tasks, generate_html
    
    tasks = process_tasks(task_lines, now)
    html_content = generate_html(tasks, now)
    
    # 保存临时 HTML
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    temp_html = TEMP_DIR / f"DDL_{date_label}.html"
    with open(temp_html, "w", encoding="utf-8") as f:
        f.write(html_content)
    log(f"[HTML] 已生成: {temp_html}")
    
    # 4. 确保输出目录存在
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 5. HTML → PDF（通过 Playwright）
    output_pdf = OUTPUT_DIR / f"{date_label}.pdf"
    
    log(f"[PDF] 开始转换...")
    result = subprocess.run(
        ["node", str(HTML2PDF_JS), str(temp_html), str(output_pdf)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(HTML2PDF_JS.parent)  # 确保能找到 node_modules
    )
    
    if result.returncode != 0:
        log(f"[错误] PDF 转换失败:")
        log(result.stderr)
        sys.exit(1)
    
    log(result.stdout.strip())
    
    # 6. 验证输出
    if output_pdf.exists():
        size_kb = output_pdf.stat().st_size / 1024
        log(f"[完成] PDF 已保存: {output_pdf} ({size_kb:.1f} KB)")
    else:
        log(f"[错误] PDF 文件未生成")
        sys.exit(1)
    
    # 7. 清理临时文件
    try:
        temp_html.unlink()
        log("[清理] 临时 HTML 已删除")
    except:
        pass
    
    log(f"===== 任务完成 =====")
    return str(output_pdf)

if __name__ == "__main__":
    main()
