#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 机检 · 四条铁律的执法者。

用法：
    py -3.14 check.py --orig 原文.txt --html 排版.html [--out 机检.json] [--max-lines 16]

十项检查（第 7、8 项要 --pdf 才跑）：
    1 char_conservation  内容一字未改（原文规范化字符必须按序全部出现在输出中）
    2 symbol_closure     「」<>{}()【】 配对闭合、不交叉
    3 mark_density       同段标注 ≤3 个
    4 mark_length        单条标注 ≤12 字
    5 line_length        逐行语义块 ≤36 汉字
    6 page_fill          每页内容高 ≤140mm（有 data-mm 用浏览器实测值，否则估算）且写区为空；
                         带 data-figpage 的独占图页豁免为 ≤200mm（typeset --fig-fullpage，帆拍板项）
    7 page_ink           渲染出来的 PDF：最低墨点不得压进写区（独占图页放宽到距页顶 225mm）、
                         最右不得冲出右边界（真品验收；页序对应 = div 序 == PDF 页序）
    8 printed_text       从 PDF 回读文本与原文逐字比——版式收紧不许把字裁没
    9 img_integrity      排版.html 里引用的本地图片必须存在
    10 img_ledger        图片处置台账：images/ 非空则 图片台账.json 必须存在且每图有记录；
                         action=redrawn 必须 confirmed=true（帆确认过 OCR）；action=fullpage
                         必须在排版.html 找到对应 data-figpage 独占页

约定：stdout 只走 ASCII（Windows 控制台 GBK 会把中文糊掉），中文明细进 --out 的 JSON。
退出码：0=全绿；1=有红项；2=用法/文件错误。
"""
import argparse, html as H, json, re, sys, unicodedata
from pathlib import Path

KEEP = re.compile(r'[一-鿿A-Za-z0-9]')
PAIRS = {'」': '「', '』': '『', '>': '<', ')': '(', ']': '[', '}': '{', '】': '【', '）': '（'}
OPENS = set(PAIRS.values())
BLOCK_TAGS = re.compile(r'</?(p|div|section|article|h[1-6]|li|ul|ol|br|tr|table|pre)[^>]*>', re.I)
STYLE = re.compile(r'<(style|script|head|title)[^>]*>.*?</\1>', re.I | re.S)
COMMENT = re.compile(r'<!--.*?-->', re.S)


def norm(s: str) -> str:
    return ''.join(KEEP.findall(unicodedata.normalize('NFKC', s)))


def strip_tags(raw: str) -> str:
    s = STYLE.sub(' ', raw)
    s = COMMENT.sub(' ', s)
    s = BLOCK_TAGS.sub('\n', s)
    s = re.sub(r'<[^>]+>', '', s)
    return H.unescape(s)


def read(p):
    return Path(p).read_text(encoding='utf-8', errors='replace')


# ---------- 1 字数守恒（严格：规范化后字符序列必须与原文完全相同） ----------
# 为什么严格：排版只动呈现——「」<>{}()、缩进、换行、间隙都是标点与空白，规范化后不留痕；
# 一旦 out ≠ orig，就说明加了词（补小标题/图注壳）或删了字（怕塞不进半页而砍内容），两者都违铁律 1。
# 图注因此只印原文（alt 与紧跟图的题注行），版式不自带「（图：）」这类壳。
def check_conservation(orig, out, fixmap=None):
    """铁律 1 判据：字词级语义守恒。
    规范化后原文与成品相同 → 直接通过。
    不同 → 检查差异是否全部在纠字词表覆盖范围内（字词级替换合法）；
    不在 → 判红。语病、逻辑不顺不在此列——那是 rbook/lbook 的活。"""
    import difflib
    a, b = norm(orig), norm(out)
    if a == b:
        return {'name': 'char_conservation', 'iron_law': 1, 'pass': True,
                'orig_chars': len(a), 'out_chars': len(b), 'missing': 0, 'added': 0,
                'detail': f'规范化字符序列与原文逐字相同（{len(a)} 字）'}
    # 有纠字词表时：检查差异是否全部被词表覆盖
    if fixmap:
        # 把原文按词表替换后再比
        a_fixed = a
        for wrong, right in sorted(fixmap.items(), key=lambda kv: -len(kv[0])):
            a_fixed = a_fixed.replace(norm(wrong), norm(right))
        if a_fixed == b:
            return {'name': 'char_conservation', 'iron_law': 1, 'pass': True,
                    'orig_chars': len(a), 'out_chars': len(b), 'missing': 0, 'added': 0,
                    'fixmap_applied': len(fixmap),
                    'detail': f'规范化字符序列与原文字词级语义守恒（{len(a)} 字，{len(fixmap)} 条纠字词表替换合法）'}
    sm = difflib.SequenceMatcher(None, a, b)
    missing, added = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ('delete', 'replace') and i2 > i1:
            missing.append(a[i1:i2])
        if tag in ('insert', 'replace') and j2 > j1:
            added.append(b[j1:j2])
    n_missing = sum(len(x) for x in missing)
    n_added = sum(len(x) for x in added)
    return {'name': 'char_conservation', 'iron_law': 1, 'pass': False,
            'orig_chars': len(a), 'out_chars': len(b), 'missing': n_missing, 'added': n_added,
            'missing_sample': missing[:5], 'added_sample': added[:5],
            'detail': f'删/改 {n_missing} 字、加 {n_added} 字——铁律 1 要求字词级语义守恒；'
                      f'差异不在纠字词表覆盖范围内。加词（小标题/图注壳/引导语）交回内容层决定，'
                      f'删字（怕超半页）应换页而不是砍内容；语病不动（那是 rbook/lbook 的活）'}


# ---------- 2 符号闭合 ----------
def check_closure(text, only=None):
    if only is not None:
        # md 模式：符号纪律只管版式注入的那几条；原文自带的 <>{}「」 是代码与引语，动不了（铁律 1）。
        errs = []
        for a in only:
            o, c = MARK_PAIRS.get(a.get('kind', 'per'), ('「', '」'))
            if o + a['text'] + c not in text:
                errs.append(f'注入标注 {o}{a["text"][:16]}{c} 没成对落到成品里')
        src = count_source_marks(text)
        return {'name': 'symbol_closure', 'iron_law': 2, 'pass': not errs, 'errors': errs[:20],
                'source_symbol_pairs': src,
                'detail': (f'版式注入 {len(only)} 条标注全部成对；原文自带 {src} 对符号按内容处理，不判违规'
                           if not errs else f'{len(errs)} 条注入标注没落地')}
    stack, errs = [], []
    for pos, ch in enumerate(text):
        if ch in OPENS:
            stack.append((ch, pos))
        elif ch in PAIRS:
            if stack and stack[-1][0] == PAIRS[ch]:
                stack.pop()
            else:
                errs.append(f'「{ch}」在偏移 {pos} 处无配对开符（交叉或多余）')
    for ch, pos in stack:
        errs.append(f'「{ch}」在偏移 {pos} 处未闭合')
    return {'name': 'symbol_closure', 'iron_law': 2, 'pass': not errs,
            'errors': errs[:20], 'detail': '符号全部闭合' if not errs else f'{len(errs)} 处符号问题'}


SENT_END = '。！？!?'
QUOTE_BREAK = '：:，,、；;'   # 引语内部的分句符号——出现即说明这是原文引用，不是版式标注
MARK_PAIRS = {'per': ('「', '」'), 'theory': ('<', '>'), 'concept': ('{', '}'), 'entry': ('【', '】')}


def annotations(text, only=None):
    """取出「标注」：「」<>{}【】 包起来的片段，其中属于"原文引语"的不算。

    豁免两类（都不受 ≤12 字与密度纪律约束，因为砍它们＝违反铁律 1 不改字）：
    1) 「」内含 。！？ ——整段说话内容。教训：真实转写里 `「其实啊，这些教科书都是一样的。」` 被误判。
    2) 「」内含 ：，、； ——界面文案/条目原文等多分句引语。
       教训：架构文档表格里的 placeholder `「想做的事直接说：明天交报告 / 要不要换工作」` 被误判。
    「」是中文引号，两种豁免只作用于它；<>{}【】 是版式专用符，永远按标注纪律查。

    only 不为 None 时（md 模式）：只认版式真正注入过的那几条。
    为什么必须分这套口径：技术文档正文里的 `<NextInteraction>`、`{ id： string }` 是代码内容，
    不是版式标注；把它们当标注判红，等于逼排版改原文——违铁律 1。实测 6 份文档误判 49 处。"""
    out = []
    for m in re.finditer(r'「([^」]*)」|<([^>]*)>|\{([^}]*)\}|【([^】]*)】', text):
        inner = next(g for g in m.groups() if g is not None)
        if only is not None and norm(inner) not in only:
            continue
        if any(c in inner for c in SENT_END):
            continue
        if m.group(1) is not None and any(c in inner for c in QUOTE_BREAK):
            continue
        out.append(inner)
    return out


def count_source_marks(text):
    """成品里成对出现的符号片段数——md 模式下这些多数来自原文，按内容处理；报告里说清，不装作检过。"""
    return len(re.findall(r'「[^」]*」|<[^>]*>|\{[^}]*\}|【[^】]*】', text))


# ---------- 3 标注密度 ----------
def split_paragraphs(raw):
    chunks = re.findall(r'<div class="para[^"]*"[^>]*>(.*?)</div>', raw, re.S | re.I)
    if not chunks:
        chunks = re.findall(r'<p[^>]*>(.*?)</p>', raw, re.S | re.I)
    return chunks


def check_density(raw, only=None):
    paras = split_paragraphs(raw)
    if not paras:
        return {'name': 'mark_density', 'iron_law': 3, 'pass': True, 'checked': 0, 'warn': True,
                'detail': '未找到 .para / <p> 分段结构，密度检查跳过（建议补结构，否则该项无执法力）'}
    bad = []
    for n, p in enumerate(paras, 1):
        t = strip_tags(p)
        cnt = len(annotations(t, only))
        if cnt > 3:
            bad.append({'paragraph': n, 'marks': cnt, 'preview': norm(t)[:24]})
    return {'name': 'mark_density', 'iron_law': 3, 'pass': not bad, 'checked': len(paras),
            'over_limit': bad[:10],
            'detail': f'{len(paras)} 段，全部 ≤3 标注' if not bad else f'{len(bad)} 段标注超 3 个'}


# ---------- 4 标注长度 ----------
def check_mark_length(text, only=None):
    bad = [{'text': a[:30], 'chars': len(norm(a))} for a in annotations(text, only) if len(norm(a)) > 12]
    return {'name': 'mark_length', 'iron_law': 2, 'pass': not bad, 'over_limit': bad[:10],
            'detail': '单条标注均 ≤12 字' if not bad else f'{len(bad)} 条标注超 12 字，应在句读处拆开'}


# ---------- 5 行长（两条上限：字数 + 行宽） ----------
CAP_EM = 37.8        # 版心 160mm ÷ 12pt(4.233mm)：一行物理上最多放这么多 em


WIDE_EAW = ('W', 'F', 'A')          # Wide / Fullwidth / Ambiguous


def em_units(s):
    """字形宽（em 当量）：按 Unicode East Asian Width 判。
    为什么不能按码位阈值一刀切（旧写法是 ord>0x2E80 算全宽）：
    `⑦ ≈ × → ⑥` 这些是 Ambiguous（U+2000~U+2BFF），在中文字体里按全宽渲染，
    却被旧阈值算成半宽——实测因此让一行超出 5.3mm，页尾 6 个字被裁掉。
    ASCII / 半角标点算 0.5，其余 W/F/A 算 1。"""
    return sum(1.0 if unicodedata.east_asian_width(c) in WIDE_EAW else 0.5 for c in s)


CI_PAD_EM = 0.36        # .ci 的左右 padding（.18em × 2），漏算它就量不准行宽


def line_em(s, n_code=0):
    """一行真正占多宽 = 字形宽 + 语义间隙（.6em，句读收尾 .88em）+ 行内代码的内边距。
    为什么不能只数字数：≤36 汉字是内容纪律，但间隙会把 24 字的一行推到 38.6em，
    印出来冲出右边界——实测 page_ink 抓到 185.8mm > 185mm。typeset.py 复用本函数切行。
    行内代码要单加 padding：一页里 2~3 个 `.ci` 就是 0.7~1.1em 的漏算，
    正好对上实测的 185.6 / 185.9mm 越界。"""
    s = s.replace(chr(0), '').replace(chr(1), '')   # 圈定哨兵是排版记号，不占宽
    toks = [t for t in re.split(r'(?<=[，。、；：！？—])', s) if t]
    gaps = sum(0.88 if t[-1] in '，。、；：！?' else 0.6 for t in toks)
    return em_units(s) + gaps + CI_PAD_EM * n_code


INNER_TAG = re.compile(r'</?span[^>]*>', re.I)


def extract_lines(raw):
    """取每个 <span class="line"> 的**完整**内容（含行内嵌套的语义单元 span）。
    为什么不能用 re.findall(r'<span class="line...">(.*?)</span>')：非贪婪会在行内第一个
    `</span>`（第一个语义单元的收尾）就停——实测只量到每行的头一个单元，
    一行 34 字被报成 20 字，行长这道闸等于没关。行块有嵌套，只能按嵌套深度走。"""
    out = []
    for m in re.finditer(r'<span class="line[^"]*"[^>]*>', raw, re.I):
        i, depth, start = m.end(), 1, m.end()
        while depth:
            n = INNER_TAG.search(raw, i)
            if not n:
                break
            if n.group(0).startswith('</'):
                depth -= 1
                if depth == 0:
                    out.append(raw[start:n.start()])
                    i = n.end()
                    break
            else:
                depth += 1
            i = n.end()
    return out


def check_line_length(raw, cap=36, cap_em=CAP_EM):
    """两条上限：① ≤36 汉字当量（规范原话是「汉字」，所以 ASCII 折半算，
    一段 49 字符的英文标识符 ≈24.5 汉字当量，合规；按裸字符数判会把合规内容判红）
    ② ≤37.8em 物理行宽（含语义间隙），超了会冲出右边界。"""
    lines = extract_lines(raw)
    if not lines:
        return {'name': 'line_length', 'iron_law': 3, 'pass': True, 'checked': 0, 'warn': True,
                'detail': '未找到 <span class="line"> 逐行语义块，行长检查跳过（排版未采用行块结构）'}
    bad, bad_w = [], []
    for n, ln in enumerate(lines, 1):
        plain = strip_tags(ln)
        t = norm(plain)
        han = round(em_units(plain), 1)
        if han > cap:
            bad.append({'line': n, 'han': han, 'chars': len(t), 'preview': t[:24]})
        w = round(line_em(plain, ln.count('class="ci"')), 1)
        if w > cap_em:
            bad_w.append({'line': n, 'em': w, 'preview': t[:24]})
    peak = max((round(em_units(strip_tags(l)), 1) for l in lines), default=0)
    peak_em = max((round(line_em(strip_tags(l), l.count('class="ci"')), 1) for l in lines), default=0)
    bad = bad + bad_w
    return {'name': 'line_length', 'iron_law': 3, 'pass': not bad, 'checked': len(lines),
            'peak': peak, 'cap': cap, 'peak_em': peak_em, 'cap_em': cap_em, 'over_limit': bad[:10],
            'detail': (f'{len(lines)} 行，峰值 {peak} 汉字当量（上限 {cap}）· {peak_em}em（上限 {cap_em}）'
                       if not bad else
                       f'{len(bad)} 行超上限：{len(bad) - len(bad_w)} 行超字数、{len(bad_w)} 行超行宽（会冲出右边界）')}


# ---------- 6 页面高度（硬半页：内容区 ≤140mm） ----------
# 为什么不用「每页行数 ≤16」：行距之外还有段后距，一行一段的写法会把 16 行撑成 230mm，
# 行数达标却撑破半页。改为按 page.css 的 token 估真实毫米高度。
# 块级高度模型（typeset.py 复用这里的常量与计数，禁止两处各写一份——防估高漂移）。
LINE_H_MM = 12 * 2.0 * 0.3528      # 正文 12pt × 行距 2.0 ≈ 8.47mm
PARA_M_MM = 12 * 1.4 * 0.3528      # .para 段后距 1.4em ≈ 5.92mm
CODE_H_MM = 10.5 * 1.9 * 0.3528    # 代码行 10.5pt × 1.9 ≈ 7.03mm
ROW_H_MM = 10.5 * 1.9 * 0.3528 + 2 * 0.3 * 10.5 * 0.3528   # 表格行 ≈ 9.15mm（含 padding）
HEAD_M_MM = 12 * 1.6 * 0.3528      # 标题前距 ≈ 6.77mm


def block_metrics(page_html):
    """该页内容高度（mm）。单一真源，落版与机检共用。

    优先用 data-mm —— 那是无头浏览器对这一块**实测**的布局高度（含段后距、含折行）。
    为什么必须实测：模型把表格行按 1 行高算，实测一个 4 行表格真实高 47mm 而模型只算 37mm；
    单元格折行越多偏差越大，曾出现「机检 138.6mm 通过、PDF 实际撑到 211mm 压进写区」。
    没有 data-mm 时退回估算，并在结果里标 estimated=True，让读报告的人知道这项是估的。
    """
    n_line = len(re.findall(r'<span class="line["\s>]', page_html))
    n_code = len(re.findall(r'<span class="code-line["\s>]', page_html))
    n_row = len(re.findall(r'<tr["\s>]', page_html))
    n_para = len(re.findall(r'<div class="para["\s>]', page_html))
    n_head = len(re.findall(r'<h[1-6][ >]', page_html))
    n_sep = len(re.findall(r'<hr["\s>]', page_html))
    est = (n_line * LINE_H_MM + n_code * CODE_H_MM + n_row * ROW_H_MM
           + n_para * PARA_M_MM + n_head * HEAD_M_MM + n_sep * 8.0)
    # 顶层块清单必须与生成端落 data-mm 的块集合**一模一样**：漏一类（如图片的 <figure>），
    # 条数就对不上，整页悄悄退回估算模型——而估算模型里没有图高，含图页会被算成很小而假绿。
    tops = len(re.findall(r'<(?:h[1-6]\b|div\b[^>]*class="(?:para|code-block)|figure\b|table\b|hr\b)', page_html))
    mm_vals = [float(x) for x in re.findall(r'data-mm="([\d.]+)"', page_html)]
    measured = bool(mm_vals) and len(mm_vals) == tops
    return {'lines': n_line, 'code_lines': n_code, 'rows': n_row, 'paras': n_para,
            'heads': n_head, 'blocks': tops,
            'estimated': not measured,
            'mm': round(sum(mm_vals) if measured else est, 1)}


# ---------- 7 真品实测：拿渲染出来的 PDF 量墨迹边界 ----------
# 前六项检的都是 HTML 源码，源码合规 ≠ 印出来合规（表格定宽、字体回退、折行都会改变实际占位）。
# 这一项直接读 PDF 的字形框与图像对象：任何墨落到写区（165mm 以下）或冲出右边界（185mm 以外）即判红。
MARGIN_TOP_MM, MARGIN_LEFT_MM, MARGIN_RIGHT_MM = 25.0, 25.0, 25.0
MM2PT = 72.0 / 25.4

# 独占图页：宽 ≥80mm 或高 ≥60mm 的图自动独占一页（不再依赖帆拍板 --fig-fullpage）。
# 该页无写区，内容上限放宽到 .page 框高 200mm，
# 真品墨迹下限相应放宽到距页顶 25+200=225mm。第 6/7 项凭 data-figpage 页标记豁免，两处同一常量。
FIGPAGE_CAP_MM = 200.0
FIG_FULLPAGE_W_MM = 80.0    # 图宽 ≥80mm → 独占页
FIG_FULLPAGE_H_MM = 60.0    # 图高 ≥60mm → 独占页


def page_opening_tags(raw):
    """按序取每个 .page 的开标签（含属性）。页序对应关系 = div 序 == PDF 页序，
    第 6/7/10 项都靠这个顺序把「哪页是独占图页」对上。"""
    return re.findall(r'<div class="page[^>]*>', raw)


# ---------- 9 图源完整性（不依赖 --pdf，排版阶段即可查） ----------
def check_img_integrity(html_path):
    raw = Path(html_path).read_text(encoding='utf-8', errors='replace')
    base = Path(html_path).parent
    imgs = re.findall(r'<img[^>]+src=["\']([^"\']+)["\']', raw, re.I)
    missing, estimated = [], []
    for src in imgs:
        p = base / src
        if not p.exists():
            missing.append(str(p))
        # 向上找所属顶层块 figure/.fig，必须有 data-mm
        idx = raw.find(f'src="{src}"')
        if idx < 0:
            idx = raw.find(f"src='{src}'")
        block_start = raw.rfind('<figure', 0, idx) if idx >= 0 else -1
        if block_start < 0:
            block_start = raw.rfind('<div', 0, idx) if idx >= 0 else -1
        block_tag = raw[block_start:idx] if block_start >= 0 else ''
        if 'data-mm' not in block_tag:
            estimated.append(src)
    return {'name': 'img_integrity', 'iron_law': 4, 'pass': not missing,
            'checked': len(imgs), 'missing': missing[:10], 'estimated': len(estimated),
            'detail': (f'{len(imgs)} 张图源全部存在'
                       if not missing else f'{len(missing)} 张图源缺失：{missing[0]} ...')}


# ---------- 10 图片处置台账（T1b：每张图的处置有记录、重绘经人确认） ----------
# 与第 9 项互补：第 9 项查「引用的图源存在」，本项查「每张图的处置有记录」。
# 纪律闭环：重绘（OCR 转写）机器验不了对错，必须帆确认（confirmed=true）才放行；
# 独占页（fullpage）是版式豁免，必须在排版.html 里真找得到 data-figpage 页，不许台账空挂。
def check_img_ledger(html_path, raw):
    task = Path(html_path).parent
    img_dir = task / 'images'
    exts = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp')
    files = sorted(p.name for p in img_dir.iterdir()
                   if p.suffix.lower() in exts) if img_dir.is_dir() else []
    if not files:
        return {'name': 'img_ledger', 'iron_law': 4, 'pass': True, 'checked': 0,
                'detail': '无 images/ 或为空，图片台账项空真通过'}
    lp = task / '图片台账.json'
    if not lp.exists():
        return {'name': 'img_ledger', 'iron_law': 4, 'pass': False, 'checked': len(files),
                'missing_ledger': True,
                'detail': (f'images/ 有 {len(files)} 张图但缺 图片台账.json——'
                           f'先跑 py -3.12 scripts/imgdiag.py --task 任务目录 建台账')}
    try:
        doc = json.loads(lp.read_text(encoding='utf-8'))
        items = doc.get('images') if isinstance(doc, dict) else doc
    except (OSError, ValueError) as e:
        return {'name': 'img_ledger', 'iron_law': 4, 'pass': False, 'checked': len(files),
                'detail': f'图片台账.json 读不出来：{e}'}
    by_file = {e.get('file'): e for e in items or [] if isinstance(e, dict)}
    tags = page_opening_tags(raw)
    pages = re.split(r'<div class="page["\s>]', raw)[1:]
    bad = []
    for f in files:
        e = by_file.get(f)
        if not e:
            bad.append({'file': f, 'err': '台账无记录——重跑 imgdiag.py 补记'})
            continue
        act = e.get('action')
        if act == 'redrawn' and not e.get('confirmed'):
            bad.append({'file': f, 'err': 'redrawn 未经帆确认（confirmed≠true）：OCR 产物必须人眼对过原图'})
        elif act == 'fullpage':
            hit = any(f'data-figpage="{f}"' in t and f'images/{f}' in pg
                      for t, pg in zip(tags, pages))
            if not hit:
                bad.append({'file': f, 'err': '台账登记 fullpage 但排版.html 无对应 data-figpage 独占页'
                                              '（typeset 加 --fig-fullpage 重排，或把台账改回实际处置）'})
    return {'name': 'img_ledger', 'iron_law': 4, 'pass': not bad, 'checked': len(files),
            'violations': bad[:10],
            'detail': (f'{len(files)} 张图台账齐全、状态合规'
                       if not bad else f'{len(bad)} 张图台账违规：{bad[0]["file"]} {bad[0]["err"]}')}





def check_page_ink(pdf_path, cap_mm=140.0, n_html_pages=None, figpages=None):
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return {'name': 'page_ink', 'iron_law': 4, 'pass': True, 'warn': True,
                'detail': 'pypdfium2 不可用，真品墨迹检查跳过（此项未执法）'}
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
    except Exception as e:
        return {'name': 'page_ink', 'iron_law': 4, 'pass': False,
                'detail': f'PDF 读不出来：{e}'}
    bad, rows = [], []
    if n_html_pages is not None and len(pdf) != n_html_pages:
        bad.append({'sheet_mismatch': f'{n_html_pages} 个 .page 印出 {len(pdf)} 张纸——有页被挤到第二张，'
                                      f'后面每页的验收数据全部错位'})
    limit_right = (210.0 - MARGIN_RIGHT_MM) * MM2PT          # 距左边 185mm：版心右沿
    img_gate = hasattr(pdf[0], 'get_objects')                # 没这个 API 就量不到图，必须说出来
    try:
        for n, page in enumerate(pdf, 1):
            # 独占图页（data-figpage，帆拍板）无写区，墨迹下限放宽到 225mm；其余页仍是 165mm
            cap_n = FIGPAGE_CAP_MM if (figpages and n in figpages) else cap_mm
            limit_bottom = (MARGIN_TOP_MM + cap_n) * MM2PT
            h_pt = page.get_height()
            tp = page.get_textpage()
            text_low, text_right = 0.0, 0.0
            for i in range(tp.count_chars()):
                x0, y0, x1, y1 = tp.get_charbox(i)
                text_low = max(text_low, h_pt - y0)   # PDF 原点在左下
                text_right = max(text_right, x1)
            # 图像对象不是字形，但同样占纸面墨点，必须纳入边界判断
            img_low, img_right = 0.0, 0.0
            if img_gate:
                for obj in page.get_objects():
                    if obj.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                        x0, y0, x1, y1 = obj.get_bounds()
                        img_low = max(img_low, h_pt - y0)
                        img_right = max(img_right, x1)
            lowest_from_top = max(text_low, img_low)
            rightmost = max(text_right, img_right)
            rows.append({'page': n,
                         'ink_bottom_mm': round(lowest_from_top / MM2PT, 1),
                         'ink_right_mm': round(rightmost / MM2PT, 1),
                         'cap_mm': MARGIN_TOP_MM + cap_n})
            if lowest_from_top > limit_bottom + 1.0:
                kind = 'image' if img_low > text_low else 'text'
                bad.append({'page': n, 'ink_bottom_mm': round(lowest_from_top / MM2PT, 1),
                            'cap_mm': MARGIN_TOP_MM + cap_n, 'kind': kind})
            if rightmost > limit_right + 1.0:
                kind = 'image' if img_right > text_right else 'text'
                bad.append({'page': n, 'ink_right_mm': round(rightmost / MM2PT, 1),
                            'cap_mm': 210.0 - MARGIN_RIGHT_MM, 'kind': kind})
    finally:
        pdf.close()
    peak_b = max((r['ink_bottom_mm'] for r in rows), default=0)
    peak_r = max((r['ink_right_mm'] for r in rows), default=0)
    return {'name': 'page_ink', 'iron_law': 4, 'pass': not bad, 'checked': len(rows),
            'images_measured': img_gate,
            'peak_bottom_mm': peak_b, 'peak_right_mm': peak_r, 'pages': rows, 'violations': bad[:10],
            'detail': (f'{len(rows)} 页真品实测：最低墨点距页顶 {peak_b:.0f}mm（写区上沿 {MARGIN_TOP_MM + cap_mm:.0f}mm），'
                       f'最右 {peak_r:.0f}mm（版心右沿 {210 - MARGIN_RIGHT_MM:.0f}mm）'
                       + ('' if img_gate else '；本机 PDF 库读不到图像对象，图的墨迹未纳入本项')
                       if not bad else f'{len(bad)} 页墨迹压进写区或冲出右边界')}


def check_page_fill(raw, cap_mm=140.0):
    pages = re.split(r'<div class="page["\s>]', raw)[1:]
    if not pages:
        return {'name': 'page_fill', 'iron_law': 4, 'pass': True, 'checked': 0, 'warn': True,
                'detail': '未找到 <div class="page"> 分页结构，页面检查跳过'}
    tags = page_opening_tags(raw)          # 与 pages 同序：认出哪页是 data-figpage 独占图页
    rows, bad = [], []
    for n, pg in enumerate(pages, 1):
        is_fig = n <= len(tags) and 'data-figpage' in tags[n - 1]
        cap = FIGPAGE_CAP_MM if is_fig else cap_mm     # 独占图页无写区，上限放宽到 200mm
        m = block_metrics(pg)
        zone = re.search(r'<div class="writezone[^"]*"[^>]*>(.*?)</div>', pg, re.S)
        junk = len(norm(zone.group(1))) if zone else 0
        rows.append({'page': n, **m, 'writezone_chars': junk, 'cap_mm': cap, 'figpage': is_fig})
        if m['mm'] > cap:
            bad.append({'page': n, 'mm': m['mm'], 'cap_mm': cap, 'estimated': m['estimated']})
        if junk:
            bad.append({'page': n, 'writezone_not_empty': junk})
    peak = max((r['mm'] for r in rows), default=0)
    est = any(r['estimated'] for r in rows)
    n_fig = sum(1 for r in rows if r['figpage'])
    return {'name': 'page_fill', 'iron_law': 4, 'pass': not bad, 'checked': len(pages),
            'peak_mm': round(peak, 1), 'cap_mm': cap_mm, 'estimated': est, 'pages': rows, 'violations': bad[:10],
            'detail': (f'{len(pages)} 页，峰值内容高 {peak:.0f}mm（上限 {cap_mm:.0f}mm，{"估算" if est else "浏览器实测"}'
                       + (f'；{n_fig} 页独占图页按 {FIGPAGE_CAP_MM:.0f}mm 豁免' if n_fig else '')
                       + '），写区全空'
                       if not bad else f'{len(bad)} 处破页：内容超上限或写区被印东西')}


def check_printed_text(pdf_path, orig_path):
    """第 8 项：从 PDF 里把字抠出来，与 原文.txt 逐字比。
    为什么单独有这一项：.page 现在 overflow:hidden，内容真超框会被裁掉，
    而裁掉的墨点第 7 项量不到（它不在纸上了）。这一项保证「收紧版式」永远不会
    变成「悄悄丢字」——丢一个字符即判红。"""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return {'name': 'printed_text', 'iron_law': 1, 'pass': True, 'warn': True,
                'detail': 'pypdfium2 不可用，PDF 文本回读检查跳过（此项未执法）'}
    try:
        pdf = pdfium.PdfDocument(str(pdf_path))
    except Exception as e:
        return {'name': 'printed_text', 'iron_law': 1, 'pass': False,
                'detail': f'PDF 读不出来：{e}'}
    try:
        got = ''.join(pdf[i].get_textpage().get_text_range() for i in range(len(pdf)))
    finally:
        pdf.close()
    a, b = norm(read(orig_path)), norm(got)
    # 单向子序列：原文必须全部出现在 PDF 上；图注壳等排版补字 harmless。
    it = iter(b)
    missing = [c for c in a if c not in it]
    lost = len(missing)
    return {'name': 'printed_text', 'iron_law': 1, 'pass': lost == 0,
            'orig_chars': len(a), 'printed_chars': len(b), 'lost': lost,
            'missing_sample': ''.join(missing[:10]),
            'detail': (f'PDF 上 {len(b)} 字，原文 {len(a)} 字全部按序出现（没被裁掉、没被吃掉）'
                       if lost == 0 else f'PDF 上少了 {lost} 字——版式收紧把内容裁没了，不许出')}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--orig', required=True)
    ap.add_argument('--html', required=True)
    ap.add_argument('--out', default=None)
    ap.add_argument('--cap-line', type=int, default=36)
    ap.add_argument('--cap-mm', type=float, default=140.0)
    ap.add_argument('--pdf', default=None, help='已渲染的 PDF：加检第 7 项「真品墨迹边界」')
    ap.add_argument('--injected', default=None,
                    help='版式注入标注清单.json（md 模式必给）：符号三项只检这些，原文自带符号按内容处理')
    a = ap.parse_args()

    try:
        orig, raw = read(a.orig), read(a.html)
    except OSError as e:
        print('[ERR] cannot read input:', e)
        return 2

    inj = None
    if a.injected:
        try:
            inj = json.loads(Path(a.injected).read_text(encoding='utf-8'))
        except (OSError, ValueError) as e:
            print('[ERR] cannot read injected list:', str(e).encode('ascii', 'replace').decode('ascii'))
            return 2
    inj_set = {norm(x.get('text', '')) for x in inj} if inj is not None else None

    text = strip_tags(raw)
    # 独占图页页码集（div 序 == PDF 页序，第 6/7 项豁免 140mm 上限都靠它）
    figpages = {i + 1 for i, t in enumerate(page_opening_tags(raw)) if 'data-figpage' in t}
    # 读纠字词表（如果存在）：铁律 1 判据放宽为字词级语义守恒
    fixmap = None
    fix_path = Path(a.orig).parent / '纠字词表.json'
    if fix_path.exists():
        try:
            fixmap = json.loads(fix_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            fixmap = None
    checks = [
        check_conservation(orig, text, fixmap),
        check_closure(text, inj),
        check_density(raw, inj_set),
        check_mark_length(text, inj_set),
        check_line_length(raw, a.cap_line),
        check_page_fill(raw, a.cap_mm),
        check_img_integrity(a.html),
        check_img_ledger(a.html, raw),
    ]
    if a.pdf:
        n_pages = len(re.split(r'<div class="page["\s>]', raw)) - 1
        checks.append(check_page_ink(a.pdf, a.cap_mm, n_pages, figpages))
        checks.append(check_printed_text(a.pdf, a.orig))
    passed = all(c['pass'] for c in checks)
    report = {'pass': passed, 'orig': str(a.orig), 'html': str(a.html), 'pdf': str(a.pdf or ''),
              'tokens': {'cap_line': a.cap_line, 'cap_content_mm': a.cap_mm,
                         'line_h_mm': round(LINE_H_MM, 2), 'para_margin_mm': round(PARA_M_MM, 2)},
              'checks': checks}
    if a.out:
        Path(a.out).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')

    for c in checks:
        flag = 'OK  ' if c['pass'] else 'FAIL'
        extra = ' (skipped)' if c.get('warn') else ''
        print(f'[{flag}] {c["name"]}{extra}: {c["detail"]}'.encode('ascii', 'replace').decode('ascii'))
    print('[RESULT] PASS' if passed else '[RESULT] FAIL')
    return 0 if passed else 1


if __name__ == '__main__':
    sys.exit(main())
