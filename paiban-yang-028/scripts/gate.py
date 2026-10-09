#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 事件闸门（PreToolUse hook 用）。

宿主把工具调用 JSON 从 stdin 喂进来；本脚本判断：这是不是一次「未过排版机检就出 PDF/HTML」的渲染动作。
退出码：0=放行；2=阻塞（宿主会把 stderr 回给模型）。

放行规则（按序）：
    1. 非 Bash 工具 / 命令不含渲染特征            → 0
    2. 命令含 --paiban-ok（帆明确授权直出）        → 0
    3. 环境变量 PAIBAN_GATE=off（调试逃生门）      → 0
    4. 目标 .html 同目录有机检凭据且 pass=true      → 0
    5. 其余                                        → 2 阻塞

设计约束：只拦渲染命令，不拦 Write/Edit；不放全命令行进日志。
"""
import json, os, re, sys
from pathlib import Path

RENDER = re.compile(r'(--print-to-pdf|\brender\.py\b|\bmd2pdf\b|\bweasyprint\b|(--headless[^\n]*\bpdf\b))', re.I)
HTML_ARG = re.compile(r'["\']?([^\s"\']+\.html?)["\']', re.I)
HTML_ARG2 = re.compile(r'([^\s"\']+\.html?)', re.I)


def emit_allow():
    sys.exit(0)


def emit_block(reason):
    try:
        sys.stderr.buffer.write((reason + '\n').encode('utf-8', 'replace'))
        sys.stderr.flush()
    except Exception:
        sys.stderr.write('[paiban-gate] blocked')
    sys.exit(2)


def valid_credential(rep_path, html_path):
    """凭据有效须同时满足：存在 + pass=true + 校验对象就是这个 html + html 未被改过。"""
    if not rep_path.exists():
        return False, 'absent'
    try:
        rep = json.loads(rep_path.read_text(encoding='utf-8'))
    except Exception:
        return False, 'unreadable'
    if rep.get('pass') is not True:
        return False, 'pass=false'
    if Path(str(rep.get('html', ''))).name.lower() != html_path.name.lower():
        return False, 'for-other-file'
    try:
        if html_path.stat().st_mtime > rep_path.stat().st_mtime + 1:
            return False, 'stale-html-edited-after-check'
    except OSError:
        return False, 'unstatable'
    return True, 'ok'


def main():
    # 宿主喂进来的是 UTF-8 JSON；Windows 下 sys.stdin 默认按 GBK 解，中文路径会糊成乱码
    # （实测：排版.html → 鎺掔増.html，导致凭据判为 absent 误拦）。必须显式按字节读再解 UTF-8。
    try:
        raw = sys.stdin.buffer.read().decode('utf-8', 'replace')
    except Exception:
        raw = sys.stdin.read()
    try:
        ev = json.loads(raw or '{}')
    except Exception:
        emit_allow()                      # 解析不了就不误拦

    if str(ev.get('tool_name', '')).lower() not in ('bash', 'shell', 'terminal'):
        emit_allow()

    ti = ev.get('tool_input') or {}
    cmd = ti.get('command') if isinstance(ti, dict) else str(ti)
    cmd = cmd or ''

    if not RENDER.search(cmd):
        emit_allow()
    if '--paiban-ok' in cmd:
        emit_allow()
    if os.environ.get('PAIBAN_GATE', '').lower() == 'off':
        emit_allow()

    cands = HTML_ARG.findall(cmd) or HTML_ARG2.findall(cmd)
    why = []
    for c in cands:
        p = Path(c)
        if not p.is_absolute():
            p = Path.cwd() / p
        for name in ('机检.json', 'check.json'):
            ok, reason = valid_credential(p.parent / name, p)
            why.append(f'{p.name}:{reason}')
            if ok:
                emit_allow()

    # 找不到任何 html（例如纯字符串命令）→ 保守放行，避免误拦
    if not cands:
        emit_allow()

    emit_block('[paiban-yang-028] 未过机检，渲染已拦。' + '; '.join(why[:4]) +
               ' —— 二选一：跑 /paiban 生成与该 html 同名对应的机检凭据；'
               '或帆明确直出时在命令里加 --paiban-ok。')


if __name__ == '__main__':
    main()
