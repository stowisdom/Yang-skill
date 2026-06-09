# -*- coding: utf-8 -*-
"""
DDL HTML Report Generator - 东方极简「墨」风格
风格定位：东方极简「墨」——深色、留白、内敛、意蕴丰富
"""

from datetime import datetime, timedelta
import os
import json
import math

# ============ 配置 ============
OUTPUT_DIR = r"C:\Users\lenovo\.craft-agent\workspaces\my-workspace\sessions\{date}\data"

def get_output_path(now: datetime):
    """根据当前日期生成输出路径"""
    date_str = now.strftime("%Y-%m-%d")
    output_dir = OUTPUT_DIR.format(date=date_str)
    os.makedirs(output_dir, exist_ok=True)
    return os.path.join(output_dir, "DDL_Report.html")

# ============ 任务分类与颜色（墨色调和） ============
COLORS = {
    "A": "#4a6fa5",      # 墨蓝
    "B": "#5a7a5a",      # 墨绿
    "C": "#a55a5a",      # 赤墨
    "expired": "#6a6a6a", # 淡墨-已过期
    "critical": "#8a4a4a", # 深赤墨-极度紧急
    "long_term": "#5a5a5a", # 淡墨-长期任务
    "out": "#6a6a6a",    # 淡墨-其他
}

CATEGORY_NAMES = {
    "A": "从容",
    "B": "适中", 
    "C": "紧迫",
    "expired": "已逝",
    "critical": "危急",
    "long_term": "悠远",
    "out": "特殊",
}

def parse_ddl(date_str: str, year: int = 2026):
    """解析截止日期字符串"""
    # 处理格式：4/8 或 4/30
    if "--" in date_str:
        parts = date_str.split("--")
        date_part = parts[1].strip()
    else:
        date_part = date_str.strip()
    
    # 处理日期范围格式：4/13~4/16，取截止日期（后半段）
    if "~" in date_part:
        date_part = date_part.split("~")[-1].strip()
    
    month_day = date_part.split("/")
    month = int(month_day[0])
    day = int(month_day[1])
    return datetime(year, month, day, 23, 59, 59)

def classify_task(during: timedelta):
    """根据时差分类任务"""
    total_hours = during.total_seconds() / 3600
    total_days = during.total_seconds() / 86400
    total_weeks = total_days / 7

    if during.total_seconds() <= 0:
        return "已逝", COLORS["expired"], "expired"
    elif total_hours < 4:
        return "危急", COLORS["critical"], "critical"
    elif total_weeks > 12:
        return "悠远", COLORS["long_term"], "long_term"
    # C类: 1周≤during≤3周 或 1天≤during≤2天 或 4小时≤during≤24小时
    elif 4 <= total_hours <= 24:
        return "紧迫", COLORS["C"], "C"
    elif 1 <= total_days <= 2:
        return "紧迫", COLORS["C"], "C"
    elif 1 <= total_weeks <= 3:
        return "紧迫", COLORS["C"], "C"
    # B类: 3周<during≤9周 或 2天<during≤4天
    elif 2 < total_days <= 4:
        return "适中", COLORS["B"], "B"
    elif 3 < total_weeks <= 9:
        return "适中", COLORS["B"], "B"
    # A类: 9周<during≤12周 或 4天<during≤7天
    elif 4 < total_days <= 7:
        return "从容", COLORS["A"], "A"
    elif 9 < total_weeks <= 12:
        return "从容", COLORS["A"], "A"
    else:
        return "特殊", COLORS["out"], "out"

def format_during(during: timedelta):
    """格式化时间差为可读字符串"""
    total_seconds = int(during.total_seconds())
    if total_seconds <= 0:
        abs_seconds = abs(total_seconds)
        days = abs_seconds // 86400
        hours = (abs_seconds % 86400) // 3600
        mins = (abs_seconds % 3600) // 60
        if days > 0:
            return f"已逝 {days}日{hours}时"
        elif hours > 0:
            return f"已逝 {hours}时{mins}分"
        else:
            return f"已逝 {mins}分"

    days = total_seconds // 86400
    hours = (total_seconds % 86400) // 3600
    mins = (total_seconds % 3600) // 60

    if days > 0:
        return f"余 {days}日{hours}时{mins}分"
    elif hours > 0:
        return f"余 {hours}时{mins}分"
    else:
        return f"余 {mins}分"

def get_progress_ratio(during: timedelta, category: str):
    """计算进度条比例（越紧急，进度条越满）"""
    total_hours = during.total_seconds() / 3600
    if category == "expired":
        return 1.0
    elif category == "critical":
        return 0.95
    elif category == "C":
        max_h = 3 * 7 * 24
        ratio = 1 - (total_hours / max_h)
        return max(0.7, min(0.9, ratio))
    elif category == "B":
        max_h = 9 * 7 * 24
        ratio = 1 - (total_hours / max_h)
        return max(0.4, min(0.65, ratio))
    elif category == "A":
        max_h = 12 * 7 * 24
        ratio = 1 - (total_hours / max_h)
        return max(0.15, min(0.35, ratio))
    elif category == "long_term":
        return 0.05
    return 0.5

def _format_node_time(dt, now):
    """格式化小时级节点的时间显示"""
    if dt.date() == now.date():
        return dt.strftime("%H:%M")
    else:
        return f"{dt.month}/{dt.day} {dt.strftime('%H:%M')}"

def calculate_sqrt_nodes(total_days_float, now):
    """计算开根号时间节点
    第一节点：总量开根号后向下取整（取小不取大）
    第二节点：(总量-第一节点)开根号后向下取整
    ≥2天时以「日」为单位，<2天但≥2小时时以「时」为单位
    """
    display_total_days = round(total_days_float)
    total_hours_float = total_days_float * 24
    display_total_hours = round(total_hours_float)
    
    if display_total_days >= 2:
        # ── 以天为单位 ──
        sqrt1 = math.sqrt(display_total_days)
        n1 = math.floor(sqrt1)
        if n1 == 0:
            return None, None, None, None
        
        remaining = display_total_days - n1
        sqrt2 = math.sqrt(remaining) if remaining > 0 else 0
        n2 = math.floor(sqrt2) if remaining > 0 else 0
        
        node1_dt = now + timedelta(days=n1)
        node1_date_str = f"{node1_dt.month}/{node1_dt.day}"
        eq1 = '=' if abs(sqrt1 - n1) < 0.001 else '≈'
        node1_formula = f"√{display_total_days} {eq1} {n1}日"
        
        node2_date_str = None
        node2_formula = None
        if n2 > 0:
            node2_dt = node1_dt + timedelta(days=n2)
            node2_date_str = f"{node2_dt.month}/{node2_dt.day}"
            eq2 = '=' if abs(sqrt2 - n2) < 0.001 else '≈'
            node2_formula = f"√{remaining} {eq2} {n2}日"
        
        return node1_date_str, node2_date_str, node1_formula, node2_formula
    
    elif display_total_hours >= 2:
        # ── 以小时为单位 ──
        sqrt1 = math.sqrt(display_total_hours)
        n1 = math.floor(sqrt1)
        if n1 == 0:
            return None, None, None, None
        
        remaining = display_total_hours - n1
        sqrt2 = math.sqrt(remaining) if remaining > 0 else 0
        n2 = math.floor(sqrt2) if remaining > 0 else 0
        
        node1_dt = now + timedelta(hours=n1)
        node1_date_str = _format_node_time(node1_dt, now)
        eq1 = '=' if abs(sqrt1 - n1) < 0.001 else '≈'
        node1_formula = f"√{display_total_hours} {eq1} {n1}时"
        
        node2_date_str = None
        node2_formula = None
        if n2 > 0:
            node2_dt = node1_dt + timedelta(hours=n2)
            node2_date_str = _format_node_time(node2_dt, now)
            eq2 = '=' if abs(sqrt2 - n2) < 0.001 else '≈'
            node2_formula = f"√{remaining} {eq2} {n2}时"
        
        return node1_date_str, node2_date_str, node1_formula, node2_formula
    
    else:
        return None, None, None, None

def generate_html(tasks_data: list, now: datetime) -> str:
    """生成东方极简「墨」风格 HTML"""
    
    # 统计
    counts = {"A": 0, "B": 0, "C": 0, "critical": 0, "expired": 0, "long_term": 0, "out": 0}
    for t in tasks_data:
        cat = t["category"]
        if cat in counts:
            counts[cat] += 1
    
    # 生成任务卡片 HTML
    task_cards = []
    for i, t in enumerate(tasks_data):
        # 构建时间焦点区（开根号节点 + 截止时间）
        ddl_short = t.get('ddl_short', t['ddl'].split(' ')[0])
        
        if t.get('node1_date'):
            nodes_html = f'''
                    <div class="sqrt-node">
                        <span class="node-date" style="color: {t['color']}">{t['node1_date']}</span>
                        <span class="node-label">第 一 节 点</span>
                        <span class="node-formula">{t['node1_formula']}</span>
                    </div>'''
            if t.get('node2_date'):
                nodes_html += f'''
                    <div class="sqrt-node">
                        <span class="node-date" style="color: {t['color']}">{t['node2_date']}</span>
                        <span class="node-label">第 二 节 点</span>
                        <span class="node-formula">{t['node2_formula']}</span>
                    </div>'''
            
            time_focus_html = f'''
                <div class="time-focus">
                    <div class="sqrt-nodes">{nodes_html}
                    </div>
                    <div class="deadline-focus">
                        <span class="deadline-date">{ddl_short}</span>
                        <span class="deadline-label">截 止</span>
                    </div>
                </div>'''
        else:
            time_focus_html = f'''
                <div class="time-focus no-nodes">
                    <div class="deadline-focus-solo">
                        <span class="deadline-date-solo">{ddl_short}</span>
                        <span class="deadline-label">截 止</span>
                    </div>
                </div>'''
        
        card_html = f'''
        <div class="task-card" data-category="{t['category']}">
            <div class="card-accent" style="background-color: {t['color']}"></div>
            <div class="card-content">
                <div class="card-header">
                    <span class="task-number">#{i+1:02d}</span>
                    <h3 class="task-name">{t['name']}</h3>
                    <span class="task-category" style="color: {t['color']}; border-color: {t['color']}">{t['label']}</span>
                </div>
                {time_focus_html}
                <div class="card-meta">
                    <span class="meta-item" style="color: {t['color']}">{t['during_str']}</span>
                </div>
                <div class="progress-container">
                    <div class="progress-bar" style="width: {t['progress']*100}%; background-color: {t['color']}; box-shadow: 0 0 8px {t['color']}40;"></div>
                </div>
            </div>
        </div>
        '''
        task_cards.append(card_html)
    
    tasks_html = '\n'.join(task_cards)
    
    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>DDL 任务看板 · 墨</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:ital,wght@0,300;0,400;1,300;1,400&family=Noto+Sans+SC:wght@300;400;500&family=Noto+Serif+SC:wght@400;500;600;700;900&display=swap" rel="stylesheet">
    <style>
        :root {{
            --bg: #0a0a0a;
            --surface: #111;
            --border: #1e1e1e;
            --border-light: #2a2a2a;
            --text: #a09888;
            --text-muted: #605848;
            --text-dim: #383028;
            --white: #e8e0d4;
            --cream: #d4c8b4;
            --ink: #c4a87c;
            --ink-dim: #7a6848;
            --color-a: #4a6fa5;
            --color-b: #5a7a5a;
            --color-c: #a55a5a;
            --color-gray: #6a6a6a;
        }}
        
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}
        
        body {{
            background-color: var(--bg);
            color: var(--text);
            font-family: 'Noto Serif SC', serif;
            line-height: 2.2;
            min-height: 100vh;
        }}
        
        .container {{
            max-width: 800px;
            margin: 0 auto;
            padding: 3rem 2rem;
        }}
        
        /* 呼吸条 */
        .breath-line {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 1rem;
            padding: 1rem 0;
            border-bottom: 1px solid var(--border);
            margin-bottom: 2rem;
        }}
        
        .breath-line::before,
        .breath-line::after {{
            content: '';
            flex: 1;
            height: 1px;
            background: linear-gradient(90deg, transparent, var(--border-light), transparent);
        }}
        
        .breath-item {{
            font-family: 'Noto Sans SC', sans-serif;
            font-size: 0.65rem;
            font-weight: 300;
            color: var(--text-muted);
            letter-spacing: 0.2em;
        }}
        
        /* 标题区 */
        .header {{
            text-align: center;
            padding: 4rem 0;
            position: relative;
        }}
        
        .header-decoration {{
            font-size: 7rem;
            font-weight: 900;
            color: var(--border-light);
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            z-index: 0;
            opacity: 0.5;
            pointer-events: none;
            font-family: 'Noto Serif SC', serif;
        }}
        
        .header-content {{
            position: relative;
            z-index: 1;
        }}
        
        .header h1 {{
            font-size: 1.8rem;
            font-weight: 600;
            color: var(--white);
            letter-spacing: 0.3em;
            margin-bottom: 0.5rem;
        }}
        
        .header-subtitle {{
            font-family: 'Cormorant Garamond', serif;
            font-style: italic;
            font-size: 1rem;
            color: var(--text-muted);
            letter-spacing: 0.1em;
        }}
        
        .header-dot {{
            width: 4px;
            height: 4px;
            background-color: var(--ink);
            border-radius: 50%;
            margin: 1.5rem auto;
        }}
        
        /* 统计摘要 - 三栏网格 */
        .stats-section {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 0;
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            margin: 3rem 0;
        }}
        
        .stat-item {{
            text-align: center;
            padding: 2rem 1rem;
            border-right: 1px solid var(--border);
        }}
        
        .stat-item:last-child {{
            border-right: none;
        }}
        
        .stat-value {{
            font-size: 2rem;
            font-weight: 600;
            color: var(--white);
            display: block;
            margin-bottom: 0.5rem;
        }}
        
        .stat-label {{
            font-family: 'Noto Sans SC', sans-serif;
            font-size: 0.7rem;
            font-weight: 300;
            color: var(--text-muted);
            letter-spacing: 0.3em;
        }}
        
        /* 间奏区 */
        .interlude {{
            text-align: center;
            padding: 4rem 0;
            border-top: 1px solid var(--border);
            border-bottom: 1px solid var(--border);
            margin: 3rem 0;
        }}
        
        .interlude-text {{
            font-size: 1.2rem;
            color: var(--cream);
            letter-spacing: 0.2em;
            margin-bottom: 1rem;
        }}
        
        .interlude-sub {{
            font-family: 'Cormorant Garamond', serif;
            font-style: italic;
            font-size: 0.9rem;
            color: var(--text-muted);
        }}
        
        /* 任务卡片 */
        .tasks-section {{
            margin: 3rem 0;
        }}
        
        .task-card {{
            background-color: var(--surface);
            border: 1px solid var(--border-light);
            margin-bottom: 1.5rem;
            position: relative;
            overflow: hidden;
        }}
        
        .task-card::before {{
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 40px;
            height: 2px;
            background-color: var(--ink-dim);
        }}
        
        .card-accent {{
            position: absolute;
            left: 0;
            top: 0;
            bottom: 0;
            width: 3px;
        }}
        
        .card-content {{
            padding: 1.5rem 2rem;
            padding-left: 2.5rem;
        }}
        
        .card-header {{
            display: flex;
            align-items: center;
            gap: 1rem;
            margin-bottom: 1rem;
        }}
        
        .task-number {{
            font-family: 'Noto Sans SC', sans-serif;
            font-size: 0.7rem;
            font-weight: 300;
            color: var(--text-dim);
            letter-spacing: 0.1em;
        }}
        
        .task-name {{
            flex: 1;
            font-size: 1.2rem;
            font-weight: 600;
            color: var(--white);
            margin: 0;
        }}
        
        .task-category {{
            font-family: 'Noto Sans SC', sans-serif;
            font-size: 0.65rem;
            font-weight: 400;
            padding: 0.3rem 0.8rem;
            border: 1px solid;
            letter-spacing: 0.15em;
        }}
        
        .card-meta {{
            display: flex;
            gap: 2rem;
            margin-bottom: 1rem;
            padding-bottom: 1rem;
            border-bottom: 1px solid var(--border);
        }}
        
        .meta-item {{
            font-family: 'Noto Sans SC', sans-serif;
            font-size: 0.75rem;
            font-weight: 300;
            color: var(--text-muted);
            letter-spacing: 0.1em;
        }}
        
        /* 进度条 */
        .progress-container {{
            height: 6px;
            background-color: var(--border);
            border-radius: 3px;
            overflow: hidden;
        }}
        
        .progress-bar {{
            height: 100%;
            border-radius: 3px;
            transition: width 0.5s ease;
        }}
        
        /* 时间焦点区 - 视觉重心转向时间 */
        .time-focus {{
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            padding: 1.5rem 0;
            margin: 0.5rem 0 1rem;
            border-bottom: 1px solid var(--border);
        }}
        
        .time-focus.no-nodes {{
            justify-content: flex-start;
        }}
        
        .sqrt-nodes {{
            display: flex;
            gap: 2.5rem;
        }}
        
        .sqrt-node {{
            text-align: left;
        }}
        
        .node-date {{
            font-family: 'Noto Serif SC', serif;
            font-size: 2.8rem;
            font-weight: 700;
            line-height: 1.1;
            display: block;
        }}
        
        .node-label {{
            font-family: 'Noto Sans SC', sans-serif;
            font-size: 0.55rem;
            font-weight: 300;
            color: var(--text-dim);
            letter-spacing: 0.3em;
            display: block;
            margin-top: 0.4rem;
        }}
        
        .node-formula {{
            font-family: 'Cormorant Garamond', serif;
            font-style: italic;
            font-size: 0.75rem;
            color: var(--text-muted);
            display: block;
            margin-top: 0.2rem;
        }}
        
        .deadline-focus {{
            text-align: right;
        }}
        
        .deadline-focus-solo {{
            text-align: left;
        }}
        
        .deadline-date {{
            font-family: 'Noto Serif SC', serif;
            font-size: 2rem;
            font-weight: 600;
            color: var(--white);
            line-height: 1.1;
            display: block;
        }}
        
        .deadline-date-solo {{
            font-family: 'Noto Serif SC', serif;
            font-size: 2.2rem;
            font-weight: 600;
            color: var(--white);
            line-height: 1.1;
            display: block;
        }}
        
        .deadline-label {{
            font-family: 'Noto Sans SC', sans-serif;
            font-size: 0.55rem;
            font-weight: 300;
            color: var(--text-dim);
            letter-spacing: 0.3em;
            display: block;
            margin-top: 0.4rem;
        }}
        
        /* 尾声 */
        .footer {{
            text-align: center;
            padding: 4rem 0 2rem;
            border-top: 1px solid var(--border);
            margin-top: 3rem;
        }}
        
        .footer-quote {{
            font-size: 0.88rem;
            color: var(--text);
            font-style: italic;
            margin-bottom: 2rem;
            text-indent: 0;
        }}
        
        .footer-line {{
            width: 60px;
            height: 1px;
            background-color: var(--ink-dim);
            margin: 0 auto 2rem;
        }}
        
        .footer-copy {{
            font-family: 'Noto Sans SC', sans-serif;
            font-size: 0.65rem;
            font-weight: 300;
            color: var(--text-dim);
            letter-spacing: 0.4em;
        }}
        
        /* 竖排侧边装饰 */
        .side-decoration {{
            position: fixed;
            left: 2rem;
            top: 50%;
            transform: translateY(-50%);
            writing-mode: vertical-rl;
            text-orientation: mixed;
            font-family: 'Noto Serif SC', serif;
            font-size: 0.75rem;
            color: var(--text-dim);
            letter-spacing: 0.5em;
            opacity: 0.5;
            pointer-events: none;
        }}
        
        @media (max-width: 900px) {{
            .side-decoration {{
                display: none;
            }}
        }}
        
        /* 分类特殊样式 */
        .task-card[data-category="expired"] .task-name {{
            color: var(--text-muted);
            text-decoration: line-through;
            text-decoration-color: var(--color-gray);
        }}
        
        .task-card[data-category="critical"] {{
            border-color: var(--color-c);
            background-color: rgba(165, 90, 90, 0.05);
        }}
    </style>
</head>
<body>
    <div class="side-decoration">时不我待 · 墨韵悠长</div>
    
    <div class="container">
        <!-- 呼吸条 -->
        <div class="breath-line">
            <span class="breath-item">{now.strftime('%Y')}</span>
            <span class="breath-item">{now.strftime('%m/%d')}</span>
            <span class="breath-item">{now.strftime('%H:%M')}</span>
        </div>
        
        <!-- 标题区 -->
        <header class="header">
            <div class="header-decoration">墨</div>
            <div class="header-content">
                <h1>DDL 任务看板</h1>
                <p class="header-subtitle">Deadlines &amp; Tasks Dashboard</p>
                <div class="header-dot"></div>
            </div>
        </header>
        
        <!-- 统计摘要 -->
        <div class="stats-section">
            <div class="stat-item">
                <span class="stat-value" style="color: {COLORS['critical']}">{counts['critical']}</span>
                <span class="stat-label">危急</span>
            </div>
            <div class="stat-item">
                <span class="stat-value" style="color: {COLORS['C']}">{counts['C']}</span>
                <span class="stat-label">紧迫</span>
            </div>
            <div class="stat-item">
                <span class="stat-value" style="color: {COLORS['B']}">{counts['B']}</span>
                <span class="stat-label">适中</span>
            </div>
            <div class="stat-item">
                <span class="stat-value" style="color: {COLORS['A']}">{counts['A']}</span>
                <span class="stat-label">从容</span>
            </div>
            <div class="stat-item">
                <span class="stat-value" style="color: {COLORS['expired']}">{counts['expired']}</span>
                <span class="stat-label">已逝</span>
            </div>
            <div class="stat-item">
                <span class="stat-value" style="color: var(--white)">{len(tasks_data)}</span>
                <span class="stat-label">总计</span>
            </div>
        </div>
        
        <!-- 间奏区 -->
        <div class="interlude">
            <p class="interlude-text">光阴似箭，日月如梭</p>
            <p class="interlude-sub">Time flies like an arrow, fruit flies like a banana.</p>
        </div>
        
        <!-- 任务列表 -->
        <div class="tasks-section">
            {tasks_html}
        </div>
        
        <!-- 尾声 -->
        <footer class="footer">
            <p class="footer-quote">「逝者如斯夫，不舍昼夜」</p>
            <div class="footer-line"></div>
            <p class="footer-copy">DDL TASK MANAGER · MO STYLE</p>
        </footer>
    </div>
</body>
</html>'''
    
    return html

def process_tasks(task_lines: list, now: datetime) -> list:
    """处理任务列表，返回结构化数据"""
    tasks = []
    year = now.year
    
    for line in task_lines:
        line = line.strip()
        if not line or "--" not in line:
            continue
        
        parts = line.split("--", 1)
        name = parts[0].strip()
        date_str = parts[1].strip()
        
        try:
            ddl = parse_ddl(date_str, year)
            during = ddl - now
            label, color, category = classify_task(during)
            progress = get_progress_ratio(during, category)
            time_str = format_during(during)
            
            # 计算开根号时间节点
            total_days_float = during.total_seconds() / 86400
            node1_date, node2_date, node1_formula, node2_formula = calculate_sqrt_nodes(total_days_float, now)
            
            tasks.append({
                "name": name,
                "ddl": ddl.strftime("%m/%d %H:%M"),
                "ddl_short": f"{ddl.month}/{ddl.day}",
                "during_seconds": during.total_seconds(),
                "during_str": time_str,
                "label": label,
                "color": color,
                "category": category,
                "progress": progress,
                "node1_date": node1_date,
                "node2_date": node2_date,
                "node1_formula": node1_formula,
                "node2_formula": node2_formula,
            })
        except Exception as e:
            print(f"解析任务失败: {line}, 错误: {e}")
            continue
    
    # 按剩余时间排序
    tasks.sort(key=lambda t: t["during_seconds"])
    return tasks

def save_json(tasks: list, output_path: str):
    """保存任务数据为 JSON"""
    json_data = []
    for t in tasks:
        json_data.append({
            "name": t["name"],
            "ddl": t["ddl"],
            "remaining": t["during_str"],
            "category": t["label"],
        })
    
    json_path = output_path.replace(".html", ".json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(json_data, f, ensure_ascii=False, indent=2)
    return json_path

def generate_report(task_lines: list, now: datetime) -> tuple:
    """
    生成 DDL 报告
    返回: (html_path, json_path)
    """
    # 处理任务
    tasks = process_tasks(task_lines, now)
    
    # 生成输出路径
    output_path = get_output_path(now)
    
    # 生成 HTML
    html_content = generate_html(tasks, now)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # 保存 JSON
    json_path = save_json(tasks, output_path)
    
    return output_path, json_path, tasks

if __name__ == "__main__":
    # 测试
    test_tasks = [
        "机械原理作业--4/8",
        "计算机绘图&autocad--4/9",
        "互换性实验报告--4/8",
    ]
    now = datetime(2026, 4, 9, 8, 11, 17)
    html_path, json_path, tasks = generate_report(test_tasks, now)
    print(f"HTML: {html_path}")
    print(f"JSON: {json_path}")
    print(f"Tasks: {len(tasks)}")
