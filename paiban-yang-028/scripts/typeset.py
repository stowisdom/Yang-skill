#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 落版器：纯文本/转写 或 Markdown → 原文.txt（冻结基准）+ 排版.html（硬半页）。

散文/转写模式（默认）：
    py -3.12 typeset.py --in 某课.转写.txt --dir 任务目录 [--fix 纠字词表.json] [--marks 标注词表.json]
                       [--entry 正则] [--render]
Markdown 模式（保留标题层级 / 列表 / 表格 / 代码块）：
    py -3.12 typeset.py --in 某文档.md --dir 任务目录 --md [--render]
                        [--fig-fullpage img_007.png]   # 可多次：该图独占一页（帆拍板），
                                                       # 内容上限放宽到 200mm、无写区，机检凭 data-figpage 豁免

分工：确定性（繁简、词表、标点、切行、分页、结构映射）进脚本；判断（层级取舍、标注选词、〔待核〕）留 AI。
铁律 1 落点：`原文.txt` 生成即冻结为基准；HTML 只允许加标点级符号，规范化字符序列必须与原文一致，
            否则 check.py 判红。分页高度与机检共用 check.block_metrics，禁止两处各写一份算法。
"""
import argparse, html as HT, importlib.util, json, re, shutil, subprocess, sys, unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent
CSS = HERE.parent / 'templates' / 'page.css'
CHECK = HERE / 'check.py'
RENDER = HERE / 'render.py'

# 复用机检的高度模型（单一真源）
_spec = importlib.util.spec_from_file_location('paiban_check', CHECK)
_ck = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_ck)
block_metrics, CAP_MM = _ck.block_metrics, _ck.CAP_MM if hasattr(_ck, 'CAP_MM') else 140.0
CAP_MM = 140.0

# 复用渲染器的浏览器定位（无头量高要用同一个 Edge/Chrome）
_rspec = importlib.util.spec_from_file_location('paiban_render', RENDER)
_rd = importlib.util.module_from_spec(_rspec)
_rspec.loader.exec_module(_rd)

PX2MM = 25.4 / 96.0

CAP_LINE = 36
PUN = ',。、;:!?—'
KEEP_RE = re.compile(r'[一-鿿A-Za-z0-9]')
# 行内代码的圈定哨兵。不在 KEEP 字符集里 → 原文.txt 与成品两边都不留痕，铁律 1 不受影响。
CODE_O, CODE_C = chr(0), chr(1)
PUNCT_MAP = {',': '，', ':': '：', ';': '；', '?': '？', '!': '！'}

try:
    from opencc import OpenCC
    _T2S = OpenCC('t2s').convert
except Exception:
    _T2S = None

# 图物理上限（与 page.css 同源，生成端负责闸）
IMG_MAX_W_MM = 160.0
IMG_CAP_MARGIN_MM = 10.0   # .fig 上下块距预留
IMG_CAPTION_H_MM = 10.0    # 图注占位
IMG_MIN_H_MM = 48.0        # 图再缩也有下限：缩到看不清还不如让机检判红，交人来看
# 独占图页的内容上限 = .page 框高 200mm（该页无写区）。与 check.FIGPAGE_CAP_MM 同一口径，
# 机检第 6/7 项凭 data-figpage 豁免 140mm。这是帆拍板项：诊断对「重绘不了又缩到看不清」的图
# 给建议，帆点头后才用 --fig-fullpage 生效。
FIG_PAGE_CAP_MM = 200.0
IMGDIAG = HERE / 'imgdiag.py'
IMG_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp')

# KaTeX local assets
KATEX_DIR = HERE.parent / 'assets' / 'katex'
FIG_FULLPAGE_W_MM = 80.0
FIG_FULLPAGE_H_MM = 60.0
# 栅格图按这个 DPI 折算纸面尺寸。**不是屏幕的 96**：2026-09-27《Agent 设计模式》第 1 章实测，
# 书里的表格/代码图全是 600px 宽，按 96 DPI 折算成 159mm，比原书自己印的 121mm（126 DPI）
# 放大 1.31 倍——栅格没有新信息，只有插值，纸面变成「比原书还糊」。帆对着 7/8/9 页三张表提的
# 「图太糊」就是这个。120 DPI 是印刷可读的下限口径，取它做地板：600px → 127mm，
# 与原书 121mm 基本同尺寸同锐度，且不再随图片像素数瞎放大。
IMG_PRINT_DPI = 120.0
FIG_CAP_RE = re.compile(r'^(?:图|表)\s*\d+[-–]\d+\s')
# 题注判据：编号后那个空格不能省。正文里也有「图3-5展示了显式调用的执行流程…」这种句子，
# 只认「图3-5」开头就会把整段正文当题注并进图块（实测图块量到 202.8mm，硬半页直接失守）。


def _w(s):
    return len(KEEP_RE.findall(s))

# ---- Math detection (L8) ----
MATH_INLINE_RE = re.compile(r'\$([^$\n]+)\$')
MATH_BLOCK_RE = re.compile(r'\$\$([^$]+?)\$\$', re.S)


def _has_math(s):
    return bool(MATH_INLINE_RE.search(s) or MATH_BLOCK_RE.search(s))


def _wrap_math(s):
    s = MATH_BLOCK_RE.sub(lambda m: '<div class="katex-block">' + m.group(1).strip() + '</div>', s)
    s = MATH_INLINE_RE.sub(lambda m: '<span class="katex">' + m.group(1).strip() + '</span>', s)
    return s



def to_simplified(s):
    return _T2S(s) if _T2S else s


def normalize_punct(s):
    return ''.join(PUNCT_MAP.get(c, c) for c in s)


def prep(raw_text, fixmap, punct=True):
    t = to_simplified(raw_text)
    for wrong, right in sorted(fixmap.items(), key=lambda kv: -len(kv[0])):
        t = t.replace(wrong, right)
    return normalize_punct(t) if punct else t


def sentences(text):
    """散文模式：以句末标点收口，单句最长 160 字，超限在句读处再断。"""
    joined = re.sub(r'\s*\n\s*', '', text.strip())
    parts = [p.strip() for p in re.split(r'(?<=[。！？])', joined) if p.strip()]
    out = []
    for p in parts:
        while len(p) > 160:
            head = p[:160]
            cut = max(head.rfind(c) for c in '，；：、')
            cut = cut + 1 if cut > 40 else 160
            out.append(p[:cut].strip())
            p = p[cut:].strip()
        if p:
            out.append(p)
    return out


line_em, CAP_EM = _ck.line_em, _ck.CAP_EM   # 行宽算法与机检同一真源，禁止两处各写一份


ATOM_RE = re.compile(CODE_O + '[^' + CODE_C + ']*' + CODE_C   # 行内代码：整段一个原子
                   + '|「[^」]*」|[{][^}]*[}]|【[^】]*】|<[^>]*>|[(（][^)）]*[)）]'
                   # 中文破折号「——」是两个码位，末位 `|.` 会把每个 — 各判一个原子，
                   # 于是行宽刚好满时刀口落在两个 — 中间，纸面变成「上行以 — 收尾 /
                   # 下行以 — 开头」。SDD 课件 17 份实测 531 对「——」里 345 处被劈（65%）。
                   # 圈成不可拆原子后整对挪到下一行，字符不增不减。
                   + '|—{2,}'
                   + '|[A-Za-z0-9_./$-]+|.', re.S)   # 英文词整体不可拆；括号注释全角半角都算


SPLIT_AT = r'(?<=[/|,;，、 ：])'      # 原子内部可下刀处：分隔符留在前一片

# 禁则（行首 / 行尾）：收标点不许开新行，开括号不许留在行尾。
# 为什么算呈现层：只挪分刀的位置，字符一个不增不减（铁律 1 不受影响）。
# 「，」孤零零挂在行首时，眼睛要先跳回上一行才知道这句话没完——正是要压掉的外在负荷。
# 实测触发场景：一整串括号注释被 _expand_long 逐字拆开后，刀口落在「）」和「，」之间。
# 「—」同一条：源文件里单独成段的破折号（如「— Andrej Karpathy」被并进上文时）不许开新行。
# 注意禁则是尽力而为——接回上家会超 37.8em 就放弃这一刀，物理行宽优先。真让「——」不劈行的是
# 上面 ATOM_RE 那条原子化，这条只是补住单个 — 挂行首的边角。
NO_LINE_START = '，。、；：！？）】》”’…％—,.;:!?)'
NO_LINE_END = '（【《“‘(['


def _glue(atoms, cap_em):
    """把违反禁则的刀口并回邻居原子。并完超宽就放弃这一刀——禁则是尽力而为，
    物理行宽（37.8em）是硬闸，不许为了好看冲出右边界。
    内容闸（≤36 汉字当量）同样是硬闸：并进来的原子一旦超当量，填充环节没法再拆它
    （它是不可拆原子），机检第 5 项就直接判红——所以两条闸在这里一起判。"""
    def fits(x):
        return line_em(x, x.count(CODE_O)) <= cap_em and _han(x) <= CAP_LINE

    out = []
    for a in atoms:
        if (out and a and a[0] in NO_LINE_START
                and not a.startswith(CODE_O)
                and fits(out[-1] + a)):
            out[-1] += a                       # 行首收标点 → 接上家（代码段尾的哨兵后接标点也安全）
        else:
            out.append(a)
    merged = []
    for a in out:
        if (merged and a and merged[-1] and merged[-1][-1] in NO_LINE_END
                and not merged[-1].startswith(CODE_O)
                and fits(merged[-1] + a)):
            merged[-1] += a                    # 行尾开括号 → 拖下家一起走
        else:
            merged.append(a)
    return merged


def _split_atom(a, cap_em):
    """一个超宽原子 → 若干片。代码段每片重新圈定（跨行时哨兵才不会不配对）；
    括号串直接切，括号跟着首末片走，字符不增不减。代码内部无分隔符时按 cap_em 硬切，
    每段都重新包 CODE_O/CODE_C，绝不产出裸哨兵字符。"""
    if a.startswith(CODE_O):
        inner = a[1:-1]
        pieces = [p for p in re.split(SPLIT_AT, inner) if p]
        if len(pieces) <= 1:
            # 无分隔符：按行宽切成若干段，每段仍是独立代码原子
            pieces = []
            buf = ''
            for ch in inner:
                trial = CODE_O + buf + ch + CODE_C
                if line_em(trial, 1) > cap_em and buf:
                    pieces.append(CODE_O + buf + CODE_C)
                    buf = ch
                else:
                    buf += ch
            if buf:
                pieces.append(CODE_O + buf + CODE_C)
        else:
            pieces = [CODE_O + p + CODE_C for p in pieces]
        return pieces
    pieces = [p for p in re.split(SPLIT_AT, a) if p]
    if len(pieces) <= 1:
        pieces = list(a)
    return pieces


def _expand_long(atoms, cap_em):
    """超宽原子必须能拆开——「不可拆」只对放得下的原子成立。
    实测两类翻车（都冲出 185mm 版心右沿）：一个 177 字符的函数清单被当整体；
    一整串「（弹窗 8 个、输入框/表单 12 个、…、辅助功能点 13 个）」被当括号原子。"""
    out, queue = [], list(atoms)
    while queue:
        a = queue.pop(0)
        if line_em(a, a.count(CODE_O)) <= cap_em or len(a) <= 1:
            out.append(a)
        else:
            queue[:0] = _split_atom(a, cap_em)
    return out


def _expand_code(atoms, cap_em):
    """兼容旧名。"""
    return _expand_long(atoms, cap_em)


def _han(s):
    """汉字当量——**与机检第 5 项 `em_units` 同一把尺子**（W/F/A 记 1，其余记 0.5）。

    为什么不能用 `_w`：`_w` 只数汉字/字母/数字，全角标点（，。（）「」）与空格一律不计，
    于是生成端看到的「36 字」在机检那里是 36.5~42 当量，内容闸（≤36 汉字当量）等于没关。
    2026-09-21 就记过这条未修缺口（当时绕法＝人工把那句拆段）；本次《高性价比人生指南》
    41 件里 21 件被同一件事判红（如「北京市卫生健康委员会 2019 北京市加强急诊预检分」=36.5），
    按既定的真修法落地：**生成端与机检同式记账**（与 `paginate()` 那次同一个教训）。
    代码哨兵 chr(0)/chr(1) 是排版记号，不占字宽，先剥掉。"""
    return _ck.em_units(s.replace(CODE_O, '').replace(CODE_C, ''))


# Semantic boundary priority
SEM_BREAK_STRONG = '。！？；'
SEM_BREAK_MID = '，、'


def split_line_semantic(sent, cap_em=CAP_EM, indent_em=0.0):
    """Semantic-complete line splitting (prose only): prefer breaking at semantic boundaries.
    Leave the rest of current line empty rather than splitting a semantic block."""
    atoms = ATOM_RE.findall(sent)
    if not atoms:
        return []
    blocks = []
    for a in atoms:
        strength = 0
        if a and a[-1] in SEM_BREAK_STRONG:
            strength = 2
        elif a and a[-1] in SEM_BREAK_MID:
            strength = 1
        blocks.append((a, strength))
    parts, buf = [], ''
    def budget():
        return cap_em - indent_em - (2.0 if not parts else 0.0)
    for a, strength in blocks:
        if buf and (_han(buf) + _han(a) > CAP_LINE
                    or line_em(buf, buf.count(CODE_O)) + line_em(a, a.count(CODE_O)) > budget()):
            parts.append(buf)
            buf = a
            continue
        buf += a
        if strength == 2 and _w(buf) >= 8:
            parts.append(buf)
            buf = ''
    if buf.strip():
        parts.append(buf)
    result = []
    for p in parts:
        glued = _glue(ATOM_RE.findall(p), budget())
        result.append(''.join(glued))
    return [p for p in (x.strip() for x in result) if p]


def split_line(sent, cap_em=CAP_EM, indent_em=0.0):
    """句读处切 ≤CAP_LINE 字的行；标注与英文单词都是不可拆原子，绝不跨行断开。
    三条上限同时生效，先到先断：字数（排版规范）、行宽 em（版心物理宽度）、
    首行再扣 2em 首行缩进（.para 的 text-indent 只吃第一行，后面各行按整宽排）。
    indent_em = 该段的层级左缩进（.l2=1.6em、.l3=3.2em…）。
    为什么英文要整体成原子：按字符填到上限会把 `lib/storage.ts` 切成 `lib/stor / age.ts`，
    字没丢但读不动——技术文档里这种断法一眼就是机器排的。
    原子填完之后再过 _glue 一道禁则：收标点不落行首、开括号不落行尾。"""
    parts, buf = [], ''

    def budget():
        return cap_em - indent_em - (2.0 if not parts else 0.0)

    for a in _glue(_expand_long(ATOM_RE.findall(sent), budget()), budget()):
        if buf and (_han(buf) + _han(a) > CAP_LINE
                    or line_em(buf, buf.count(CODE_O)) + line_em(a, a.count(CODE_O)) > budget()):
            parts.append(buf)
            buf = a
            continue
        buf += a
        if a in PUN and _w(buf) >= 8 and a != '、':
            parts.append(buf)
            buf = ''
    if buf.strip():
        parts.append(buf)
    return [p for p in (x.strip() for x in parts) if p]


INJECTED = []        # 版式真正注入过的标注：{kind, text}——机检据此区分「我们的标注」与「原文自带符号」

FRAME_PAIRS = (('“', '”'), ('「', '」'), ('《', '》'))


def _framed(seg):
    """原文自带的框定区间（“…” / 「…」）。"""
    spans = []
    for o, c in FRAME_PAIRS:
        start = None
        for i, ch in enumerate(seg):
            if ch == o:
                start = i
            elif ch == c and start is not None:
                spans.append((start, i + 1))
                start = None
        if start is not None:                 # 只走到半个引号：剩下的都算框内，宁可不标
            spans.append((start, len(seg)))
    return spans


def _pick(seg, w):
    """第一个「不在原文框内」的出现位置；全在框内返回 -1。
    为什么要挑：作者已经用“”锚过的词再套一层版式符号 = 双重框定，违铁律 2「禁止混用」。
    2026-09-27《Agent 设计模式》第 1 章实测：113 条注入里 22 条会撞进作者的引号
    （如 “单例模式”→“「单例模式」”），而撞进去的正是全书最该框的模式名。"""
    framed = _framed(seg)
    pos = seg.find(w)
    while pos >= 0:
        if not any(a <= pos < b for a, b in framed):
            return pos
        pos = seg.find(w, pos + 1)
    return -1


def mark(text, marks, budget=3):
    """只在非代码段注入标注符号。反引号代码已被 CODE_O/CODE_C 哨兵圈成原子，
    标注符号插进哨兵之间会污染代码内容、破坏哨兵配对。
    同一个词在段内有多处时，取第一处**没被原文“”/「」框住**的（见 _pick）。"""
    used = 0
    for kind, pat in (('per', marks.get('per')), ('theory', marks.get('theory')), ('concept', marks.get('concept'))):
        for w in (pat or []):
            if used >= budget:
                break
            o, c = {'per': ('「', '」'), 'theory': ('<', '>'), 'concept': ('{', '}')}[kind]
            out, replaced = [], False
            for seg, is_code in _code_runs(text):
                if not is_code and not replaced:
                    p = _pick(seg, w)
                    if p >= 0:
                        seg = seg[:p] + o + w + c + seg[p + len(w):]
                        replaced = True
                out.append(seg)
            if replaced:
                text = ''.join(out)
                INJECTED.append({'kind': kind, 'text': w})
                used += 1
    return text, used


def unit_span(chunk, escape=True):
    """一个语义行 → 带间隙的 token 串。行内代码整段成一个 `.ci`，内部不切间隙。"""
    out = []
    for seg, is_code in _code_runs(chunk):
        if not seg:
            continue
        if is_code:
            body = HT.escape(seg, quote=False) if escape else seg
            out.append(f'<span class="ci">{body}</span>')
            continue
        for t in re.split(r'(?<=[，。、；：！？—])', seg):
            if not t:
                continue
            cls = 'u-p' if t[-1] in '，。、；：！?' else 'u'
            body = HT.escape(t, quote=False) if escape else t
            out.append(f'<span class="{cls}">{body}</span>')
    return ''.join(out) or (f'<span class="u">{HT.escape(chunk, quote=False)}</span>' if chunk else '')


def tint(html, injected=False):
    """给「」(引语/文案) 与 （）(注释) 上色——只动版式属性，一个字都不改。
    刻意不碰 <> 与 {}：技术文档里它们是泛型和对象字面量，不是「理论方法」「概念术语」标注。
    `[^<>]` 保证不跨标签：代码段、行边界都不会被半截包住。

    injected=True 只给**散文/转写模式**用：那条路没有代码，源文里一个符号都没有
    （2026-09-26 实测《必须用好计算机》docx：「」【】（）<>{} 全为 0），
    所以成品里出现的 {} 与 【】 必然是 mark()/--entry 注入的标注，必须按规范上色。
    否则「标注注入」只活在机检里——2026-09-26 实测：纸上 27 处符号与正文同色同粗，
    五要素的第一条「符号框定」等于没交付。
    【】用 .entry-i（行内加粗）而不是 .entry：.entry 带 display:block，
    散文的 【】 挂在句子中间，块级化会把一行劈成两行，而散文页高按 `.line` 计数、
    劈出来的第二行没人记账——硬半页会静默失守。

    injected 传**集合**时走 md 路径：只给「这一步 mark() 真正注入过的那几个词」上色。
    为什么不照抄散文那句传 True：技术文档正文里的 `{ id： string }`、`<T>` 是代码内容，
    全量上色等于把代码染成概念标注（v0.5「<> 与 {} 不上色」就是为它定的）。
    2026-09-26 实测的另一头：md 路径压根不调 injected 分支，传 --marks 注入的 {} 印出来
    与正文同色——同一处失效在散文路径被抓过（第 11 课），md 路径的 para_html 一直漏着。
    """
    html = re.sub(r'「[^<>]{1,40}」', lambda m: f'<span class="per">{m.group(0)}</span>', html)
    html = re.sub(r'（[^<>]{1,60}）', lambda m: f'<span class="paren">{m.group(0)}</span>', html)
    if isinstance(injected, (set, frozenset, list, tuple)):
        for w in injected:
            for o, c, cls in (('{', '}', 'concept'), ('【', '】', 'entry-i'), ('<', '>', 'theory')):
                # 成品里 <> 已被 unit_span 转义成 &lt; &gt;，按转义后的形状匹配，
                # 否则 <理论方法> 标注永远配不上色——2026-09-27《Agent 设计模式》第 1 章：
                # 全书最该显性的 25 个模式名/原则名注入后与正文同色，.theory 白写在 page.css。
                pat = re.escape(HT.escape(f'{o}{w}{c}', quote=False))
                html = re.sub(pat, lambda m, k=cls: f'<span class="{k}">{m.group(0)}</span>', html)
        return html
    if injected:
        html = re.sub(r'\{[^<>]{1,40}\}', lambda m: f'<span class="concept">{m.group(0)}</span>', html)
        html = re.sub(r'【[^<>]{1,40}】', lambda m: f'<span class="entry-i">{m.group(0)}</span>', html)
    return html


def _img_size(path):
    """读本地图片真实像素尺寸。优先 PIL，没有则手工读 PNG/JPEG 头；再不行抛错。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except Exception:
        pass
    data = Path(path).read_bytes()
    # PNG
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        i = 16
        while i < len(data):
            length = int.from_bytes(data[i:i + 4], 'big')
            chunk = data[i + 4:i + 8]
            if chunk == b'IHDR':
                w = int.from_bytes(data[i + 8:i + 12], 'big')
                h = int.from_bytes(data[i + 12:i + 16], 'big')
                return w, h
            i += 12 + length + 4
    # JPEG: SOF0/SOF2/0xC0/0xC2
    if data.startswith(b'\xff\xd8'):
        i = 2
        while i < len(data):
            if data[i] != 0xff:
                break
            marker = data[i + 1]
            if marker in (0xd9, 0xd8):
                i += 2
                continue
            length = int.from_bytes(data[i + 2:i + 4], 'big')
            if marker in (0xc0, 0xc2):
                h = int.from_bytes(data[i + 5:i + 7], 'big')
                w = int.from_bytes(data[i + 7:i + 9], 'big')
                return w, h
            i += 2 + length
    raise RuntimeError(f'需要 pillow 才能读取该图片尺寸：{path}')


def _scale_img_mm(px_w, px_h, cap_mm=CAP_MM, has_caption=False, extra_pad_mm=0.0):
    """按当前页容量 cap 推导图高上限，等比缩放。宽>160 或 高超限时缩到先触线的那条；
    都不超则原尺寸。图高上限 = cap − 块距 −（有图注再扣图注占位）− 额外预留，随闭环收紧联动。
    extra_pad_mm 由 split_oversized 抬高：图注折行多占一行、或图+注仍超 cap 时，
    用真实预算重算，而不是把纸面撑破。"""
    max_h_mm = (cap_mm - IMG_CAP_MARGIN_MM - extra_pad_mm
                - (IMG_CAPTION_H_MM if has_caption else 0))
    max_h_mm = max(IMG_MIN_H_MM, max_h_mm)          # 缩到看不清还不如让机检判红
    w_mm = px_w * 25.4 / IMG_PRINT_DPI
    h_mm = px_h * 25.4 / IMG_PRINT_DPI
    ratios = []
    if w_mm > IMG_MAX_W_MM:
        ratios.append(IMG_MAX_W_MM / w_mm)
    if h_mm > max_h_mm:
        ratios.append(max_h_mm / h_mm)
    if ratios:
        r = min(ratios)
        w_mm, h_mm = w_mm * r, h_mm * r
    return int(round(w_mm)), int(round(h_mm))


def _normalize_img(blocks, task_dir, src_dir):
    """把 ('img', src, alt[, 题注]) 的 src 落到任务目录 images/，并把像素尺寸写进块。
    相对路径相对源文件目录；URL 抛错（T1 负责先下载）；不存在的文件保留原样让机检抓。
    纸面 mm 在 block_html 阶段按当前 cap 现算，随闭环收紧联动。
    块定型为 ('img', 相对路径, alt, px_w, px_h, 题注, 额外预留mm)；最后一项由 split_oversized 抬高。"""
    img_dir = task_dir / 'images'
    img_dir.mkdir(parents=True, exist_ok=True)
    seen = {}          # src_path -> (img_NNN.ext, px_w, px_h)
    out = []
    n = 0
    for b in blocks:
        if b[0] != 'img':
            out.append(b)
            continue
        src, alt = b[1], b[2]
        cap_txt = b[3] if len(b) > 3 else ''
        if src.lower().startswith(('http://', 'https://')):
            raise RuntimeError(f'网络图片需先在 T1 下载到 images/ 再排版：{src}')
        src_path = Path(src)
        if not src_path.is_absolute():
            src_path = src_dir / src_path
        src_key = str(src_path.resolve()) if src_path.exists() else src
        if src_key not in seen:
            n += 1
            ext = Path(src).suffix.lower() or '.png'
            if ext not in ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp'):
                ext = '.png'
            dst = img_dir / f'img_{n:03d}{ext}'
            px_w = px_h = 0
            if src_path.exists():
                shutil.copyfile(src_path, dst)
                try:
                    px_w, px_h = _img_size(src_path)
                except Exception as e:
                    raise RuntimeError(f'读取图片尺寸失败 {src}: {e}')
            seen[src_key] = (dst.name, px_w, px_h)
        name, px_w, px_h = seen[src_key]
        out.append(('img', f'images/{name}', alt, px_w, px_h, cap_txt, 0.0))
    return out


# ---------------- Markdown → 结构块 ----------------

def _code_runs(s):
    """'a\\x00bc\\x01d' → [('a',False),('bc',True),('d',False)]"""
    out, buf, code = [], '', False
    for ch in s:
        if ch == CODE_O:
            if buf:
                out.append((buf, code))
                buf = ''
            code = True
        elif ch == CODE_C:
            if buf:
                out.append((buf, code))
                buf = ''
            code = False
        else:
            buf += ch
    if buf:
        out.append((buf, code))
    return out


EMPH_STAR = re.compile(r'[*~]{1,3}([^*_~]+)[*~]{1,3}')
EMPH_UNDER = re.compile(r'(?<![A-Za-z0-9_])_{1,3}([^*_~]+)_{1,3}(?![A-Za-z0-9_])')


def _strip_emph(seg):
    """剥标点级强调符，两条纪律：
    ① 只在代码段之外做；
    ② 下划线按 CommonMark 的「词内不成强调」判——`KIMI_CODE_HOME`、`auto_install`、
       `session_index.jsonl` 里的下划线是标识符的一部分，当成斜体吃掉就是改字。
    实测教训：一份技术文档被吃掉 27 个下划线（KIMI_CODE_HOME → KIMICODEHOME），
    而机检的 KEEP 字符集不含 `_`，八项全绿也照不出来——这类字只能从生成端堵住。"""
    return EMPH_UNDER.sub(r'\1', EMPH_STAR.sub(r'\1', seg))


def md_inline(s):
    """去 md 语法但保留全部可读字符。
    顺序要紧：先还原链接（URL 是内容，删了就少字）→ 按反引号切出代码段圈进哨兵 →
    最后只对**非代码段**剥强调符。整串一起剥会把代码里的下划线当斜体吃掉（旧实现的坑）。"""
    # 前置反引号豁免：`` `![](x)` `` 这类「代码段里引用链接语法」不许还原，
    # 否则把代码内容里的 ![] 吃掉、半角括号变全角，T1 对账 A 档判红（ljg-push 实测）。
    # 链接正则同时豁免前置 `!`：那是图片语法，归上面图片正则管。
    s = re.sub(r'(?<!`)!\[([^\]]*)\]\(([^)]*)\)', r'\1（\2）', s)
    s = re.sub(r'(?<![`!])\[([^\]]*)\]\(([^)]*)\)', r'\1（\2）', s)
    parts = re.split(r'(`[^`\n]+`)', s)
    for i, seg in enumerate(parts):
        parts[i] = (CODE_O + seg[1:-1] + CODE_C) if i % 2 else _strip_emph(seg)
    return ''.join(parts).replace('`', '').strip()


def md_blocks(text):
    """返回 [('h',级,文) | ('li',缩进级,文) | ('p',0,文) | ('code',[行]) | ('table',[行[列]]) | ('img',src,alt[,题注])]"""
    blocks, lines, fence, buf = [], [], None, []
    ls = text.splitlines()
    i = 0
    while i < len(ls):
        l = ls[i]
        if re.match(r'^\s*```', l):
            if fence is None:
                if buf:
                    blocks.append(('p', 0, ' '.join(buf))); buf = []
                fence = []
            else:
                blocks.append(('code', fence)); fence = None
            i += 1; continue
        if fence is not None:
            fence.append(l)
            i += 1; continue
        if re.fullmatch(r'[-*_]{3,}', l.strip()) and set(l.strip()) <= set('-*_ '):
            # md 分隔线 = 版式的「同级硬断」。'-' 不是规范化字符（KEEP 只留汉字与字母数字），
            # 渲成 <hr> 不违反铁律 1。放在列表正则之前：`---` 若落到段落分支会变成正文里的假文字。
            if buf:
                blocks.append(('p', 0, ' '.join(buf))); buf = []
            blocks.append(('hr',))
            i += 1; continue
        m = re.fullmatch(r'^\s*!\[([^\]]*)\]\(([^)]*)\)\s*$', l)
        if m:
            # 独立行图片：从段落缓冲独立成块，行内图片仍走 md_inline 降级为 alt+地址。
            if buf:
                blocks.append(('p', 0, ' '.join(buf))); buf = []
            blocks.append(('img', m.group(2), m.group(1)))
            i += 1; continue
        if l.strip().startswith('|') and '|' in l.strip()[1:]:
            if buf:
                blocks.append(('p', 0, ' '.join(buf))); buf = []
            rows = []
            while i < len(ls) and ls[i].strip().startswith('|'):
                cells = [md_inline(c) for c in ls[i].strip().strip('|').split('|')]
                if not re.fullmatch(r'[\s:\-|]+', ls[i].strip()):
                    rows.append(cells)
                i += 1
            if rows:
                blocks.append(('table', rows))
            continue
        m = re.match(r'^(#{1,6})\s*(.*)$', l)
        if m:
            if buf:
                blocks.append(('p', 0, ' '.join(buf))); buf = []
            blocks.append(('h', min(len(m.group(1)), 4), md_inline(m.group(2))))
            i += 1; continue
        m = re.match(r'^(\s*)(?:[-*+]|\d+[.、])\s+(.*)$', l)
        if m:
            if buf:
                blocks.append(('p', 0, ' '.join(buf))); buf = []
            lvl = min(1 + len(m.group(1)) // 2, 4)
            blocks.append(('li', lvl, md_inline(m.group(2))))
            i += 1; continue
        m = re.match(r'^>\s?(.*)$', l)
        if m:
            if buf:
                blocks.append(('p', 0, ' '.join(buf))); buf = []
            blocks.append(('li', 3, md_inline(m.group(1))))
            i += 1; continue
        if not l.strip():
            if buf:
                blocks.append(('p', 0, ' '.join(buf))); buf = []
            i += 1; continue
        buf.append(md_inline(l))
        i += 1
    if buf:
        blocks.append(('p', 0, ' '.join(buf)))
    if fence:
        blocks.append(('code', fence))
    # 紧跟图的「图3-1 …」题注并进图块：分页按块装页，图与注分成两块时实测差 0.5mm 就会
    # 把题注挤到下一页开头，纸面变成「整页一张图 + 题注孤零零」。并块只挪归属，
    # 字照样按原顺序进 原文.txt（见 blocks_source_text）。
    merged = []
    for b in blocks:
        if (b[0] == 'p' and merged and merged[-1][0] == 'img' and len(merged[-1]) == 3
                and FIG_CAP_RE.match(b[2].strip())):
            merged[-1] = merged[-1] + (b[2].strip(),)
            continue
        merged.append(b)
    return merged


def blocks_source_text(blocks):
    """块 → 原文.txt：每块一行（代码逐行、表格逐行、图片只留 alt 与题注），
    语法符已去但可读字符一个不丢。
    必须与 block_html 出自同一批块，否则守恒检查会因两边解析不同而假红/假绿。"""
    out = []
    for b in blocks:
        if b[0] == 'hr':
            continue                       # 分隔线无字符（'-' 不进规范化序列）
        if b[0] == 'code':
            out += [l.strip() for l in b[1] if l.strip()]
        elif b[0] == 'table':
            for row in b[1]:
                line = ' '.join(c for c in row if c)
                if line:
                    out.append(line)
        elif b[0] == 'img':
            # 题注落在哪一格取决于走过 _normalize_img 没有：
            # md_blocks 产出 ('img', src, alt[, 题注])，归一后是 ('img', 相对路径, alt, px_w, px_h, 题注, 预留)。
            cap_txt = (b[5] if len(b) >= 7 else (b[3] if len(b) >= 4 else '')) or ''
            if b[2].strip():
                out.append(b[2].strip())   # alt 在图片那一行，按源序先回基准
            if cap_txt.strip():
                out.append(cap_txt.strip())  # 题注是原文的下一行，紧跟其后；图与路径不产字
        elif b[2].strip():
            out.append(b[2].strip())
    txt = '\n'.join(out) + '\n'
    return txt.replace(CODE_O, '').replace(CODE_C, '')   # 哨兵只服务呈现，基准里不留痕


# ---------------- 块 → HTML，并按浏览器实测高度分页 ----------------

def _disp_w(s):
    """显示宽度：与机检 em_units 同一把尺子（East Asian Width），禁止两处各写一份。"""
    return _ck.em_units(s)


def col_widths(rows):
    """按各列最长单元格的比例分配列宽（%）。
    两条夹边缺一不可（都是实测踩出来的）：
      上限 46：一列不许吃掉整行，把别的列挤成竖排；
      下限 14：短列（如「用户行动」4 字）按比例只分到 6.6% = 10.5mm，
               扣掉左右 padding 只剩 1.6 字宽 → 一个字一行竖排。14 分约给到 15%，够 5 字。
    """
    if not rows:
        return []
    ncol = max(len(r) for r in rows)
    peak = []
    for c in range(ncol):
        vals = [_disp_w(r[c]) for r in rows if c < len(r)]
        vals += [0] * (ncol - len(vals))
        peak.append(max(vals) if vals else 1)
    w = [min(max(p, 14.0), 46.0) for p in peak]
    tot = sum(w) or 1
    return [round(x / tot * 100, 2) for x in w]


def _sentinel_html(s):
    """含哨兵的行内文本 → HTML：代码段还原成 .ci，其余转义。
    单元格、标题这些「不走 unit_span 的路径」若直接 HT.escape，T1 圈进反引号的
    `*`/`_` 会带着 \\x00/\\x01 哨兵印进 HTML，Edge 渲成 .notdef 空心方框
    （实测《自学是门手艺》表格 3 ** 2 印成 3 □ 2）。无哨兵时输出与纯 escape 逐字节相同。"""
    out = []
    for seg, is_code in _code_runs(s):
        if not seg:
            continue
        body = HT.escape(seg, quote=False)
        out.append(f'<span class="ci">{body}</span>' if is_code else body)
    return ''.join(out)


def table_html(rows, cont=False):
    widths = col_widths(rows)
    cols = ''.join(f'<col style="width:{w}%">' for w in widths)
    head = ''.join(f'<th>{_sentinel_html(c)}</th>' for c in rows[0])
    body = ''.join('<tr>' + ''.join(f'<td>{_sentinel_html(c)}</td>' for c in r) + '</tr>'
                   for r in rows[1:])
    cls = ' class="cont"' if cont else ''
    return f'<table{cls}><colgroup>{cols}</colgroup><tr>{head}</tr>{body}</table>'


def para_html(text, lvl, marks, budget):
    """段/列表项 → .para。escape 必须开：技术文档正文里有 `<Spinner />`、`<NextInteraction>`
    这类尖括号内容，不转义就成了真 HTML 标签，strip_tags 一删——实测吞掉 152 字，违铁律 1。"""
    n0 = len(INJECTED)                       # 本块注入前的高度，用来圈出「本块注入了哪几个词」
    txt, used = mark(text, marks, budget)
    inj = {i['text'] for i in INJECTED[n0:]}
    lines = split_line(txt, indent_em=1.6 * (lvl - 1))
    inner = ''.join(f'<span class="line">{tint(unit_span(c, escape=True), inj or False)}</span>' for c in lines)
    return f'<div class="para l{lvl}">{inner}</div>', used


def caption_html(text):
    """图注/题注 → 一组 .line。走正文同一套切行（≤36 字 / ≤37.8em / 禁则），
    只是居中排、降到注释字号；不走切行就会印成一整行超长字，机检第 5 项判红。
    字一个不加不减（图注是原文，见 blocks_source_text）。"""
    return ''.join(f'<span class="line">{tint(unit_span(c, escape=True))}</span>'
                   for c in split_line(text, indent_em=0))


def block_html(b, marks, cap=CAP_MM):
    kind = b[0]
    if kind == 'h':
        lvl = min(b[1], 3)
        return f'<h{lvl}>{_sentinel_html(b[2])}</h{lvl}>'
    if kind == 'hr':
        return '<hr class="sep">'
    if kind == 'code':
        rows = ''.join(f'<span class="code-line">{HT.escape(l, quote=False)}</span>' for l in b[1])
        return f'<div class="code-block">{rows}</div>'
    if kind == 'table':
        return table_html(b[1])
    if kind == 'img':
        src, alt, px_w, px_h = b[1], b[2], b[3], b[4]
        cap_txt = b[5] if len(b) > 5 else ''
        pad = b[6] if len(b) > 6 else 0.0
        full = _is_figfull_block(b)
        # 图注有两个来源：md 语法自带的 alt，和原文里紧跟图的那行题注。
        # 两者都按源序印出（基准里也是 alt 在前、题注在后），一个字都不加——
        # 旧写法套了个「（图：）」壳，那是版式在正文里凭空造字，铁律 1 的严格守恒会判红。
        cap_all = ' '.join(x for x in (alt.strip(), cap_txt.strip()) if x)
        has_cap = bool(cap_all)
        # 独占页（帆拍板）：图高上限放宽到页框 200mm，其余页仍是当前闭环 cap
        w_mm, h_mm = _scale_img_mm(px_w, px_h, FIG_PAGE_CAP_MM if full else cap,
                                   has_caption=has_cap, extra_pad_mm=pad)
        style = f'width:{w_mm}mm;height:{h_mm}mm' if w_mm and h_mm else ''
        img_tag = (f'<img src="{HT.escape(src, quote=True)}" style="{HT.escape(style, quote=True)}">'
                   if style else f'<img src="{HT.escape(src, quote=True)}">')
        cap_html = f'<figcaption>{caption_html(cap_all)}</figcaption>' if has_cap else ''
        if full:
            # data-figpage 是机检第 6/7/10 项认这页豁免的凭据，值 = 图文件名（台账 file 字段）
            return (f'<figure class="fig figpage" data-figpage="{HT.escape(Path(src).name, quote=True)}">'
                    f'{img_tag}{cap_html}</figure>')
        return f'<figure class="fig">{img_tag}{cap_html}</figure>'
    if kind == 'li':
        html, _ = para_html(b[2], b[1], marks, 1)
        return html
    # 正文段与顶层列表项同起点（l1）：段首靠 2em 首行缩进定位，
    # 再叠 1.6em 左缩进会让正文比它下面的项目还靠右，层级就反了。
    html, _ = para_html(b[2], 1, marks, 2)
    return html


MEASURE_JS = """
window.addEventListener('load', () => {
  const wrap=document.getElementById('mwrap');
  const els=[...wrap.children].filter(e=>e.id!=='mout');
  const out=[];
  for(let i=0;i<els.length;i++){
    const r=els[i].getBoundingClientRect();
    // 相邻两块取「顶到顶」差即占位高，不要再减容器的 base：
    // base 会被首块塌陷出去的上边距推离视口顶（h2 的 1.6em ≈ 8.5mm），
    // 减了它 = 每一块都被少算 base，一页十几块就累计出 1.5~1.8 倍的缺口，
    // 硬半页在屏幕上"合规"、纸上压进写区（2026-10-06 双语精读册实测）。
    if(i+1<els.length){out.push(els[i+1].getBoundingClientRect().top-r.top);}
    else{const cs=getComputedStyle(els[i]);out.push(r.height+parseFloat(cs.marginBottom||'0'));}
  }
  document.getElementById('mout').textContent='MEASURE::'+JSON.stringify(out)+'::END';
});
"""


def measure(html_blocks, css_text, tag='量高', workdir=None):
    """无头浏览器实测每个顶层块在 160mm 版心里的真实占位高（mm，含与下一块的间距）。
    workdir 给定则在 workdir/.paiban_measure 下建临时文件，量完删整目录，使相对路径图片可解析。
    返回 [mm]。量不出来直接抛错——宁可不排，不许拿估算冒充实测。"""
    doc = ('<!doctype html>\n<html lang="zh"><head><meta charset="utf-8">\n<style>\n' + css_text +
           '\n</style></head>\n<body>\n<div class="page"><div class="content" id="mwrap">\n' +
           '\n'.join(html_blocks) +
           '\n</div><div class="writezone"></div></div>\n<pre id="mout" style="display:none"></pre>\n'
           '<script>' + MEASURE_JS + '</script>\n</body></html>\n')
    browser = _rd.find_browser()
    if not browser:
        raise RuntimeError('no Edge/Chrome found — 无法实测块高')
    import tempfile, shutil
    if workdir:
        tmp = Path(workdir).resolve() / '.paiban_measure'   # resolve：--dir 传相对路径时 as_uri 需要绝对路径
        tmp.mkdir(parents=True, exist_ok=True)
    else:
        tmp = Path(tempfile.mkdtemp(prefix='paiban_m_'))
    try:
        (tmp / 'index.html').write_text(doc, encoding='utf-8')
        r = subprocess.run([browser, '--headless=new', '--disable-gpu', '--no-sandbox',
                            '--virtual-time-budget=8000', f'--user-data-dir={tmp / "profile"}',
                            '--window-size=900,1400', '--dump-dom', (tmp / 'index.html').as_uri()],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=180)
        m = re.search(r'MEASURE::(\[.*?\])::END', r.stdout or '')
        if not m:
            raise RuntimeError(f'{tag}失败：浏览器没吐回高度数据 rc={r.returncode}')
        vals = [round(float(x) * PX2MM, 2) for x in json.loads(m.group(1))]
        if len(vals) != len(html_blocks):
            raise RuntimeError(f'{tag}失配：{len(vals)} 高 vs {len(html_blocks)} 块')
        return vals
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _auto_figfull(px_w, px_h):
    w_mm = px_w * 25.4 / IMG_PRINT_DPI
    h_mm = px_h * 25.4 / IMG_PRINT_DPI
    return w_mm >= FIG_FULLPAGE_W_MM or h_mm >= FIG_FULLPAGE_H_MM


def _is_figfull_block(b):
    """独占页图块：('img', …, pad, True)——第 8 元素是 --fig-fullpage 标记。"""
    return b[0] == 'img' and len(b) > 7 and b[7]


def split_oversized(b, html, span, cap):
    """超高块拆成多块：表格按行拆（首块留表头，续块 class=cont）、代码按行拆、段落按语义行拆。
    只动呈现不动字——拆出来的块拼回去，规范化字符序列不变。"""
    kind = b[0]
    if kind == 'img':
        # 图不能拆成两块，只能缩：抬高图注/块距的预留量重算尺寸（每轮 +10mm，
        # 下限由 _scale_img_mm 兜到 IMG_MIN_H_MM）。预留用尽仍超高就交下去让机检判红。
        # b[7:] 保住 --fig-fullpage 标记，拆块重来不许把独占页资格弄丢。
        pad = b[6] if len(b) > 6 else 0.0
        if pad >= cap - IMG_MIN_H_MM - IMG_CAPTION_H_MM:
            return [b]
        return [b[:6] + (round(pad + 10.0, 1),) + b[7:]]
    if kind in ('table', 'table_cont') and len(b[1]) > 1:
        rows = b[1]
        per = max(1, int(len(rows) * cap / max(span, 1) * 0.95))
        out = []
        for s in range(0, len(rows), per):
            chunk = rows[s:s + per]
            out.append(('table' if (kind == 'table' and s == 0) else 'table_cont', chunk))
        return out
    if kind == 'code' and len(b[1]) > 1:
        lines = b[1]
        per = max(1, int(len(lines) * cap / max(span, 1) * 0.95))
        return [('code', lines[s:s + per]) for s in range(0, len(lines), per)]
    if kind in ('p', 'li'):
        lvl = 2 if kind == 'p' else b[1]
        # 必须用机检同一套「按嵌套深度取整行」的解析：`<span class="line">.*?</span>` 会在
        # 行内第一个语义单元的 </span> 就停，取回的是半截行（还带着没闭合的标签），
        # 拼回去既丢字（实测一份文档丢 3287 字）又让浏览器把后面的内容整段错位。
        chunks = ['<span class="line">' + c + '</span>' for c in _ck.extract_lines(html)]
        # 每块留一个 .para 的段后距，所以行数上限要先把这 5.9mm 扣掉再除行高。
        budget = max(1, int((cap - _ck.PARA_M_MM) / _ck.LINE_H_MM))
        if len(chunks) > budget:
            return [('lineseg', lvl, chunks[s:s + budget]) for s in range(0, len(chunks), budget)]
    return [b]


def block_html_extra(b, marks, cap=CAP_MM):
    """拆块产物的渲染（table_cont / lineseg），保持与 block_html 同一套字符。"""
    if b[0] == 'table_cont':
        return table_html(b[1], cont=True)
    if b[0] == 'lineseg':
        return f'<div class="para l{b[1]}">' + ''.join(b[2]) + '</div>'
    return block_html(b, marks, cap)


def layout_blocks(blocks, marks, css_text, cap=CAP_MM, rounds=6, log=print, workdir=None):
    """块 → 浏览器实测高 → 拆超高块 → 重量，直到没有超高块。
    cap 传给 block_html，使图片尺寸随当前页容量现算。轮次用尽仍超高的原样交下去。"""
    work = list(blocks)
    for it in range(rounds):
        htmls = [block_html_extra(b, marks, cap) for b in work]
        spans = measure(htmls, css_text, workdir=workdir)
        # 独占图页按 200mm 上限生活，不吃 140mm 的拆块压力——它的上限机检第 6/7 项会单独执法
        over = {i for i, (b, s) in enumerate(zip(work, spans))
                if s > (FIG_PAGE_CAP_MM if _is_figfull_block(b) else cap) and b[0] != 'h'}
        if not over:
            return htmls, spans
        log(f'[typeset] 第 {it + 1} 轮：{len(over)} 块超 {cap:.0f}mm（峰值 {max(spans):.0f}mm），拆块后重量')
        rebuilt = []
        for i, b in enumerate(work):
            if i in over:
                rebuilt.extend(split_oversized(b, htmls[i], spans[i], cap))
            else:
                rebuilt.append(b)
        work = rebuilt
    htmls = [block_html_extra(b, marks, cap) for b in work]
    spans = measure(htmls, css_text, workdir=workdir)
    n_over = sum(1 for b, s in zip(work, spans)
                 if s > (FIG_PAGE_CAP_MM if _is_figfull_block(b) else cap) and b[0] != 'h')
    log(f'[typeset] WARN {rounds} 轮后仍有 {n_over} 块超上限')
    return htmls, spans


def _is_head(html):
    """真标题判定。不能用 startswith('<h')——`<hr>` 也算进去了，
    实测后果：分隔线被当页尾孤标题带到下一页，页高 146.5mm 破半页。"""
    return bool(re.match(r'<h[1-6][\s>"]', html))


def paginate_measured(htmls, spans, cap=CAP_MM):
    """按实测高装页；页尾孤标题（标题落在本页最后一块）挪到下一页与正文同页——
    但只在「带过去之后仍然装得下」时才挪，否则宁可留孤标题也不破硬半页。"""
    pages, cur, used = [], [], 0.0
    for h, s in zip(htmls, spans):
        if cur and used + s > cap:
            k = len(cur)
            while k > 1 and _is_head(cur[k - 1][0]):
                k -= 1
            carry = cur[k:]
            if not carry or sum(x[1] for x in carry) + s <= cap:
                pages.append(cur[:k])
                cur = carry
            else:
                pages.append(cur)
                cur = []
            used = sum(x[1] for x in cur)
        cur.append((h, s))
        used += s
    if cur:
        pages.append(cur)
    return pages


def paginate_blocks(blocks_html, cap_mm=CAP_MM):
    """【已弃用·仅散文模式兜底】按 check 的估算模型装页。
    md 模式改走 layout_blocks + paginate_measured（浏览器实测），因为估算模型算不出单元格折行。"""
    pages, cur = [], []

    def over(cand):
        return block_metrics('\n'.join(cand))['mm'] > cap_mm

    for h in blocks_html:
        if cur and over(cur + [h]):
            pages.append(cur)
            cur = []
        cur.append(h)
    if cur:
        pages.append(cur)
    return pages


def paginate(rows, cap_mm=CAP_MM):
    """散文模式：逐行装页，页高口径与 check.block_metrics 完全同式。

    block_metrics 算的是 `行数 × LINE_H + .para 块数 × PARA_M`，
    而 .para 块数由**层级变化**决定（下面的收块逻辑：lvl 一变就封一个 div）。
    旧写法把段成本摊成 `PARA_M/6` 挂在每行上，等于假定「每 6 行才一个块」；
    一旦 --entry 让页面里出现多个块（实测一页 7 块），机检按 7×5.93mm 加段距、
    生成端只算了 14×5.93/6=13.8mm，差出 27mm——51 页里 2 页直接压进写区。
    现在改成真实记账：行高照加，遇到层级变化就额外记一个块的段距，与验收同一份账。
    """
    pages, cur, used, prev = [], [], 0.0, None
    for html_line, lvl in rows:
        add = _ck.LINE_H_MM + (_ck.PARA_M_MM if cur and lvl != prev else 0.0)
        if not cur:
            add += _ck.PARA_M_MM            # 新页的第一个块同样要算段距
        if cur and used + add > cap_mm:
            pages.append(cur)
            cur, used, prev = [], 0.0, None
            add = _ck.LINE_H_MM + _ck.PARA_M_MM
        cur.append((html_line, lvl))
        used += add
        prev = lvl
    if cur:
        pages.append(cur)
    out = []
    for pg in pages:
        blocks, prev, buf = [], None, []
        for html_line, lvl in pg:
            if lvl != prev and buf:
                blocks.append(f'<div class="para l{prev}">' + ''.join(buf) + '</div>')
                buf = []
            buf.append(html_line)
            prev = lvl
        if buf:
            blocks.append(f'<div class="para l{prev}">' + ''.join(buf) + '</div>')
        out.append(blocks)
    return out


def build_lines(sents, marks, entry_re):
    rows, prev_lvl, budget = [], None, 0
    for s in sents:
        lvl, body = 2, s
        if entry_re and re.search(entry_re, s):
            m = re.search(entry_re, s)
            body = s[:m.start()] + '【' + m.group(0) + '】' + s[m.end():]
            INJECTED.append({'kind': 'entry', 'text': m.group(0)})
            lvl = 1
        if lvl != prev_lvl:
            budget = 3
            prev_lvl = lvl
        body, used = mark(body, marks, budget)
        budget = max(0, budget - used)
        for c in split_line_semantic(body, indent_em=1.6 * (lvl - 1)):
            rows.append((f'<span class="line">{tint(unit_span(c), True)}</span>', lvl))
    return rows


def with_mm(html, mm):
    """把实测高度写进块的首个开标签尾部 → check.py 用真数而不是估算模型判「硬半页」。
    必须放在属性串末尾：机检按 `class="para` 这种前缀认块，插在前面会让它认不出块、退回估算。
    mm<=0 时**不落戳**：散文模式的 span 天生是 0.0（走行高估算，不经浏览器量高），
    盖上 data-mm="0.0" 会让 check.py 认为「有实测值」并把整页算成 0mm 通过——
    等于把「硬半页」这道闸悄悄关掉。2026-09-26 实测：51 页全部 peak_mm=0.0 / estimated=false。
    不盖戳时 check.py 按它自己的口径退回估算并标 estimated=true，是真数还是估的写在报告里。"""
    i = html.find('>')
    if i < 0 or not html.startswith('<') or mm <= 0:
        return html
    return html[:i] + f' data-mm="{mm}"' + html[i:]


def _write_injected_list(path):
    """把 INJECTED 去重后落盘，供机检符号三项执法。"""
    seen, uniq = set(), []
    for inj_item in INJECTED:
        k = (inj_item['kind'], inj_item['text'])
        if k not in seen:
            seen.add(k)
            uniq.append(inj_item)
    Path(path).write_text(json.dumps(uniq, ensure_ascii=False, indent=1), encoding='utf-8')


def _ensure_img_ledger(task_dir):
    """images/ 非空而 图片台账.json 缺失或有新图未登记 → 自动跑一遍 imgdiag 兜底建账。
    为什么生成端要兜底：机检第 10 项要求每张图有处置记录；诊断是廉价的纯像素分析
    （OCR 懒加载，不装也能分流），自动补跑就不存在「忘了建台账」这种失败模式。
    已有 redrawn/fullpage 状态由 imgdiag 合并保留，不会被重跑打回 proposed。"""
    img_dir = task_dir / 'images'
    if not img_dir.is_dir():
        return
    imgs = [p.name for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXTS]
    if not imgs:
        return
    known = set()
    ledger = task_dir / '图片台账.json'
    if ledger.exists():
        try:
            doc = json.loads(ledger.read_text(encoding='utf-8'))
            items = doc.get('images') if isinstance(doc, dict) else doc
            known = {e.get('file') for e in items or [] if isinstance(e, dict)}
        except (OSError, ValueError):
            known = set()
    if ledger.exists() and set(imgs) <= known:
        return
    subprocess.run([sys.executable, str(IMGDIAG), '--task', str(task_dir)],
                   capture_output=True, timeout=300)


def _mark_ledger_fullpage(task_dir, names):
    """把 --fig-fullpage 命中的图在台账里登记为 action=fullpage + confirmed=true
    （帆在命令行拍板本身就是确认）。机检第 10 项要求台账与排版.html 的 data-figpage 互证。"""
    ledger = task_dir / '图片台账.json'
    if not ledger.exists():
        return
    try:
        doc = json.loads(ledger.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return
    items = doc.get('images') if isinstance(doc, dict) else doc
    hit = False
    for e in items or []:
        if isinstance(e, dict) and e.get('file') in names:
            e['action'] = 'fullpage'
            e['confirmed'] = True
            e['notes'] = (e.get('notes') or '') + '｜帆拍板独占页（typeset --fig-fullpage），机检第 6/7 项豁免 140mm'
            hit = True
    if hit:
        ledger.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')


def isolate_figpages(pages):
    """独占页图块从原页拔出单独成页（保序）：前后的普通块各自成页。
    paginate_measured 按实测高装页时，一张中等大小的独占图可能与普通块同页，
    这里按「独占」语义强制单页——独占是帆拍板的版式决定，不是装页算出来的。"""
    out = []
    for pg in pages:
        buf = []
        for h, s in pg:
            if 'data-figpage="' in h:
                if buf:
                    out.append(buf)
                    buf = []
                out.append([(h, s)])
            else:
                buf.append((h, s))
        if buf:
            out.append(buf)
    return out


def _page_shell(pg):
    """一页 → .page 外壳。单块且带 data-figpage 的页 = 独占图页：
    加 class figpage 与 data-figpage 属性（机检第 6/7/10 项豁免的凭据），不生成 writezone。"""
    if len(pg) == 1:
        m = re.search(r'data-figpage="([^"]+)"', pg[0][0])
        if m:
            return ('<div class="page figpage" data-figpage="' + m.group(1) + '">\n'
                    '  <div class="content">\n    ' + pg[0][0] + '\n  </div>\n</div>')
    return ('<div class="page">\n  <div class="content">\n    '
            + '\n    '.join(h for h, _ in pg)
            + '\n  </div>\n  <div class="writezone"></div>\n</div>')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--dir', required=True)
    ap.add_argument('--fix', default=None)
    ap.add_argument('--marks', default=None)
    ap.add_argument('--entry', default=None)
    ap.add_argument('--md', action='store_true', help='输入是 Markdown，保留结构')
    ap.add_argument('--fig-fullpage', dest='fig_fullpage', action='append', default=[],
                    metavar='图名', help='指定图片独占一页（可多次，按文件名匹配，如 img_007.png）；'
                                         '该页内容上限放宽到 200mm、无写区。帆拍板项，机检凭 data-figpage 豁免')
    ap.add_argument('--keep-base', action='store_true')
    ap.add_argument('--render', action='store_true')
    a = ap.parse_args()

    d = Path(a.dir)
    d.mkdir(parents=True, exist_ok=True)
    base = d / '原文.txt'
    fixmap = json.loads(Path(a.fix).read_text(encoding='utf-8')) if a.fix else {}
    marks = json.loads(Path(a.marks).read_text(encoding='utf-8')) if a.marks else {}
    raw = Path(a.src).read_text(encoding='utf-8')
    injected = None      # 散文模式沿用严格全量符号检查（转写文本里的符号都是版式加的）
    hit_figfull = set()  # --fig-fullpage 实际命中的图名（归一化后的 img_NNN.ext）

    if a.md:
        # md 模式的 原文.txt 已去掉语法符（# | ```），再拿它当 md 解析会把结构全丢→整篇一段。
        # 需要人工改字后重排：改源 .md，或用 --fix 词表；--keep-base 在 md 模式无意义，直接拒。
        if base.exists() and a.keep_base:
            print('[typeset] md 模式不支持 --keep-base（原文.txt 无 md 语法，重解析会丢结构）；'
                  '改字请改源 .md 或用 --fix')
            return 2
        # 技术文档正文的标点由作者定：`HomeScreen.tsx:19` 里的半角冒号是标识符的一部分，
        # 归一成正体全角会把 1218 处代码引用打断（实测：HomeScreen.tsx： 19）。
        blocks = md_blocks(prep(raw, fixmap, punct=False))
        orig_img_names = [Path(b[1]).name for b in blocks if b[0] == 'img']   # 归一化前的源图名
        blocks = _normalize_img(blocks, d, Path(a.src).parent)
        # 归一化不改序不改数（见 _normalize_img），按序配对 源名 → img_NNN.ext 新名
        rename = {}
        _i = 0
        for b in blocks:
            if b[0] == 'img':
                rename[orig_img_names[_i]] = Path(b[1]).name
                _i += 1
        # 独占图页（帆拍板）：给命中的 img 块打第 8 元素标记 True，block_html 据此放宽尺寸上限
        # 并落 data-figpage 戳；isolate_figpages 装页时强制单页、_page_shell 去掉写区。
        # 匹配源名与新名都行——帆手里是源 md 里的名字，台账里是归一化后的名字。
        figfull = set()
        for x in a.fig_fullpage:
            n = Path(x).name
            figfull.add(rename.get(n, n))
        auto_full = set()
        for b in blocks:
            if b[0] == 'img' and len(b) >= 6:
                px_w, px_h = b[3], b[4]
                if px_w and px_h and _auto_figfull(px_w, px_h):
                    auto_full.add(Path(b[1]).name)
        all_full = figfull | auto_full
        if all_full:
            flagged = []
            for b in blocks:
                if b[0] == 'img' and Path(b[1]).name in all_full:
                    hit_figfull.add(Path(b[1]).name)
                    b = b + (True,)
                flagged.append(b)
            blocks = flagged
            miss = figfull - hit_figfull
            if auto_full:
                print(f'[typeset] auto fullpage (size threshold): {sorted(auto_full)}')
            if miss:
                print(f'[typeset] WARN --fig-fullpage 未命中：{sorted(miss)}'
                      f'（归一化后图名是 img_NNN.ext 形式，可看 图片台账.json）')
        base.write_text(blocks_source_text(blocks), encoding='utf-8')
        css_text = CSS.read_text(encoding='utf-8')
        INJECTED.clear()
        htmls, spans = layout_blocks(blocks, marks, css_text, cap=CAP_MM, workdir=d)
        _write_injected_list(d / '标注清单.json')
        injected = d / '标注清单.json'
        current_cap = CAP_MM
        layout = lambda cap=current_cap: isolate_figpages(paginate_measured(htmls, spans, cap))
        n_units = len(blocks)
        mode = 'md/实测'
    else:
        if a.fig_fullpage:
            print('[typeset] WARN 散文模式无图片块，--fig-fullpage 被忽略')
        if base.exists() and a.keep_base:
            text = base.read_text(encoding='utf-8')
        else:
            text = prep(raw, fixmap)
            base.write_text('\n'.join(sentences(text)) + '\n', encoding='utf-8')
        sents = [l.strip() for l in base.read_text(encoding='utf-8').splitlines() if l.strip()]
        rows = build_lines(sents, marks, a.entry)
        layout = lambda cap: [[(h, 0.0) for h in pg] for pg in paginate(rows, cap)]
        n_units = len(sents)
        mode = '散文/估算'

    html_path = d / '排版.html'
    pdf_path = d / '排版.pdf'
    n_src = len(KEEP_RE.findall(base.read_text(encoding='utf-8')))

    # 台账纪律兜底（T1b）：有图就必须有 图片台账.json，缺了自动跑 imgdiag 建账；
    # --fig-fullpage 命中的图登记 fullpage + confirmed（帆拍板即确认），机检第 10 项互证。
    _ensure_img_ledger(d)
    if hit_figfull:
        _mark_ledger_fullpage(d, hit_figfull)

    def run_check(pdf=None):
        cmd = [sys.executable, str(CHECK), '--orig', str(base), '--html', str(html_path),
               '--out', str(d / '机检.json')]
        if injected:
            cmd += ['--injected', str(injected)]
        if pdf:
            cmd += ['--pdf', str(pdf)]
        return subprocess.run(cmd)

    def read_ink():
        try:
            j = json.loads((d / '机检.json').read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}
        return next((c for c in j.get('checks', []) if c['name'] == 'page_ink'), {})

    # 闭环：屏幕量高 ≠ 印刷占位（字体/取整/折行都有偏差），所以「排版 → 印 → 量真品 → 收紧上限 → 重排」。
    # 收敛依据是纸面上真实的墨点位置，不是任何一侧的估算。
    cap, attempt = CAP_MM, 0
    while True:
        attempt += 1
        pages = [[(with_mm(h, s), s) for h, s in pg] for pg in layout(cap)]
        body = [_page_shell(pg) for pg in pages]
        katex_head = ''
        if KATEX_DIR.is_dir() and (KATEX_DIR / 'katex.min.css').exists():
            kc = (KATEX_DIR / 'katex.min.css').read_text(encoding='utf-8')
            kj = (KATEX_DIR / 'katex.min.js').read_text(encoding='utf-8') if (KATEX_DIR / 'katex.min.js').exists() else ''
            katex_head = ('<style>' + kc + '</style>'
                          + ('<script>' + kj + '</script>' if kj else '')
                          + '<script>document.addEventListener("DOMContentLoaded",function(){'
                            'document.querySelectorAll(".katex").forEach(function(el){'
                            'if(typeof katex!=="undefined"){katex.render(el.textContent,el,{throwOnError:false,displayMode:false});}'
                            '});'
                            'document.querySelectorAll(".katex-block").forEach(function(el){'
                            'if(typeof katex!=="undefined"){katex.render(el.textContent,el,{throwOnError:false,displayMode:true});}'
                            '});'
                            '});</script>')
        html_path.write_text('<!doctype html>\n<html lang="zh"><head><meta charset="utf-8">'
                             + katex_head + '</head>\n<body>\n'
                             + '\n'.join(body) + '\n</body></html>\n', encoding='utf-8')
        peak = max((sum(s for _, s in pg) for pg in pages), default=0)
        print(f'[typeset] {mode} units={n_units} blocks={sum(len(p) for p in pages)} pages={len(pages)} '
              f'base_chars={n_src} cap={cap:.1f}mm peak={peak:.1f}mm '
              f't2s={"on" if _T2S else "OFF"} fix={len(fixmap)}')

        if run_check().returncode != 0:
            print('[typeset] 机检未过，不出 PDF')
            return 1
        if not a.render:
            return 0
        rr = subprocess.run([sys.executable, str(RENDER), '--html', str(html_path), '--pdf', str(pdf_path)])
        if rr.returncode != 0:
            return rr.returncode
        if run_check(pdf_path).returncode == 0:      # 源码 6 项 + 真品第 7 项全绿
            return 0
        ink = read_ink()
        n_sheets = ink.get('checked', 0)
        bottom = ink.get('peak_bottom_mm', 0) or 0
        limit = _ck.MARGIN_TOP_MM + CAP_MM
        pdf_path.unlink(missing_ok=True)             # 印坏了就不算交付
        # 独占图页（data-figpage）的真品下限是 25+200=225mm，不是 165mm——收紧判定必须按各页
        # 自己的上限算（div 序 == PDF 页序），否则合规的独占大图会被误判「压进写区」，闭环永远收不拢。
        fig_idx = {i + 1 for i, pg in enumerate(pages)
                   if len(pg) == 1 and 'data-figpage="' in pg[0][0]}
        rows_ink = ink.get('pages') or []
        if rows_ink:
            over = max((r.get('ink_bottom_mm', 0)
                        - (_ck.MARGIN_TOP_MM + (FIG_PAGE_CAP_MM if r.get('page') in fig_idx else CAP_MM))
                        for r in rows_ink), default=0.0)
        else:
            over = bottom - limit
        # 「N 页印成 M 张」本质仍是内容溢出 .page 框，属于可收的高度问题：
        # 墨点页位一错就量不准 overshoot，所以按最小步长先收，别直接判死。
        # 实测教训：卷二 69 页印成 76 张、交互架构 v2 40 页印成 41 张，
        # 早退一次都没试过收紧，等于把能救的成品当失败扔掉。
        if n_sheets and n_sheets != len(pages):
            # 有页顶出了 .page 框被拆成两张：按定步长收，别按张数比例收
            # （实测按比例一轮收 42mm，把 69 页收成 535 页还是红的）
            print(f'[typeset] {len(pages)} 页印成 {n_sheets} 张（有页溢出到第二张），定步长收 10mm 重排')
            over = max(over, 10.0)
        if over < 1.0:
            # 1mm 死区的本意是「底部合规，越界只可能来自右边界」。但死区也把真实的
            # 亚毫米高度违规一起放过了：2026-09-27《Agent 设计模式》第 5 章实测第 63 页
            # 墨底 165.7mm（限 165），over=0.7 → 被当右边界问题判死、PDF 作废，而收紧一轮就能救。
            # 所以分开判：底部仍越界 → 按最小步长再收一轮；底部合规而右边界冲 → 那才是真判死。
            right = ink.get('peak_right_mm', 0) or 0
            if over > 0:
                print(f'[typeset] 真品压进写区 {over:.1f}mm（在 1mm 死区内，仍是高度违规），'
                      f'按最小步长再收一轮')
                over = max(over, 1.0)
            elif right > 210.0 - _ck.MARGIN_RIGHT_MM:
                print(f'[typeset] FAIL 真品冲出右边界 {right:.1f}mm'
                      f'（版心右沿 {210.0 - _ck.MARGIN_RIGHT_MM:.0f}mm），底部合规，收高度无用，见机检.json')
                return 1
            else:
                print('[typeset] FAIL 真品越界但底部与右边界都不超，判据矛盾，见机检.json')
                return 1
        if attempt >= 6:
            print(f'[typeset] FAIL 收紧 {attempt} 轮仍压不进写区，已作废')
            return 1
        step = min(max(over + 1.0, 2.0), 12.0)      # 步长封顶：防一轮收太狠把页数撑爆
        if cap - step < 96.0:
            print(f'[typeset] FAIL 内容上限已收到 {cap:.1f}mm，再收就没版面了；判失败交人工看')
            return 1
        print(f'[typeset] 真品实测压进写区 {over:.1f}mm（屏幕量高偏乐观），内容上限 {cap:.1f} → '
              f'{cap - step:.1f}mm 重排')
        cap -= step
        # cap 收紧后图片尺寸上限跟着变，必须重新量高，否则图会压进写区
        INJECTED.clear()
        htmls, spans = layout_blocks(blocks, marks, css_text, cap=cap, workdir=d)
        _write_injected_list(d / '标注清单.json')
        layout = lambda cap=cap: isolate_figpages(paginate_measured(htmls, spans, cap))


if __name__ == '__main__':
    sys.exit(main())
