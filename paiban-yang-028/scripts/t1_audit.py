#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""T1 对账器：证明「进排版的那份文字」和「原文」是同一份字。

用法：
    py -3.12 t1_audit.py --src 源文档.md --orig 原文.txt [--md]
    py -3.12 t1_audit.py --src 原始粘贴.txt --orig 原文.txt        # 散文/粘贴件：直接比

为什么单独有这一件：check.py 的第 1 项比的是 `原文.txt` 与成品 HTML，**两边同出一源**——
`原文.txt` 自己在 T1 就丢了字的话，八项机检会全绿着把错字送出去。
实测翻车：一份技术文档的 `KIMI_CODE_HOME` 被 md 强调符规则吃掉 27 个下划线，
而机检的 KEEP 字符集不含 `_`，没有任何一项报警。

判定分两档：
  A 硬失败 —— 差异里有汉字、字母、数字，或 `_ . / :`（标识符与路径的命脉）→ 改字了，回 T1 修。
  B 只报告 —— 差异只是 md 语法符（反引号、表格竖线、`#`、成对的 * ~ 、链接转换补的括号）
              → 呈现物，允许消失，但计数列出来给人过目。
退出码：0=无 A 档差异；1=有 A 档差异；2=用法/文件错误。stdout 全 ASCII 安全（中文按 UTF-8 输出）。
"""
import argparse, difflib, re, sys, unicodedata
from pathlib import Path

CONTENT = re.compile(r'[一-鿿A-Za-z0-9]')
FENCE = re.compile(r'^\s*(```|~~~)')
TABLE_SEP = re.compile(r'^\s*\|?[\s:\-|]+\|[\s:\-|]*$')
HEAD = re.compile(r'^(\s*)#{1,6}\s+')
LISTMARK = re.compile(r'^(\s*)(?:[-*+]|\d+[.、])\s+')
QUOTE = re.compile(r'^(\s*)>\s?')


def strip_structure(text):
    """去掉「只服务 md 结构、不承载文字」的行与行首标记。
    代码围栏**内部**的行是内容，逐字留下；只丢 ``` 那两行本身。
    反引号与强调符留在原地——它们该由 B 档报出来给人看，不该被静默豁免。"""
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            out.append(line)
            continue
        if TABLE_SEP.match(line):
            continue
        # 标题行剥掉 `####` 之后**不能再剥列表符**：《Agent 设计模式》的四级标题写成
        # 「#### 3. Agent的完美伴侣」，那个「3.」是书的编号、`typeset.md_blocks` 判标题优先会保留上纸，
        # 这里再剥一次就成了「源少、成品多」的假 A 档（2/3/8/9 章各撞一次）。
        was_head = bool(HEAD.match(line))
        line = HEAD.sub(r'\1', line)
        if not was_head:
            line = LISTMARK.sub(r'\1', line)
        out.append(QUOTE.sub(r'\1', line))
    return '\n'.join(out)


def chars(text):
    """规范化：NFKC + 只留非空白字符（空白与换行是呈现物）。"""
    return [c for c in unicodedata.normalize('NFKC', text) if not c.isspace()]


# 汉字 / 字母 / 数字，加标识符的命脉字符：这几个少一个就是改字。
HARD_CHARS = re.compile(r'[一-鿿A-Za-z0-9_./:]')
# 允许消失的只有 md 语法符（含链接转换补的括号）。
MD_OK = set('`|*~#>-[]!（）')


def classify(dropped, added):
    both = ''.join(dropped) + ''.join(added)
    if HARD_CHARS.search(both):
        return 'A'
    return 'B' if set(both) <= MD_OK else 'A'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--src', required=True, help='进 typeset 的那份输入（.md 或纯文本）')
    ap.add_argument('--orig', required=True, help='T1 冻结的 原文.txt')
    ap.add_argument('--md', action='store_true', help='输入是 Markdown，先剥结构再比')
    ap.add_argument('--max', type=int, default=20, help='最多列几处差异')
    a = ap.parse_args()

    try:
        src = Path(a.src).read_text(encoding='utf-8')
        orig = Path(a.orig).read_text(encoding='utf-8')
    except OSError as e:
        print('[ERR] cannot read input:', e)
        return 2

    left = chars(strip_structure(src) if a.md else src)
    if a.md:
        # md 图片语法：原文.txt 只留 alt，URL 部分属于 B 档结构差异。
        # 前置反引号豁免（与 typeset.md_inline 同一规则）：`` `![](x)` `` 是代码段里
        # 引用语法，两侧都原样保留，否则赦免器自己制造出「丢 ![](x)」的假 A 档（ljg-push 实测）。
        left = [c for c in re.sub(r'(?<!`)!\[([^\]]*)\]\([^)]*\)', r'\1', ''.join(left))]
    right = chars(orig)
    sm = difflib.SequenceMatcher(None, left, right, autojunk=False)
    hard, soft = [], []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            continue
        dropped, added = left[i1:i2], right[j1:j2]
        ctx = ''.join(left[max(0, i1 - 12):i2 + 12])
        tier = classify(dropped, added)
        (hard if tier == 'A' else soft).append(
            {'at': i1, 'kind': tag, 'dropped': ''.join(dropped), 'added': ''.join(added), 'context': ctx})

    print(f'[t1] src_chars={len(left)} orig_chars={len(right)} '
          f'identical={left == right} hard={len(hard)} soft={len(soft)}')
    for d in hard[:a.max]:
        print(f"  [A] {d['kind']} 丢={d['dropped'][:24]!r} 多={d['added'][:24]!r}  上下文={d['context'][:60]!r}")
    if len(hard) > a.max:
        print(f'  [A] ...另有 {len(hard) - a.max} 处')
    if soft:
        kinds = {}
        for d in soft:
            kinds[d['dropped'][:3] or d['added'][:3]] = kinds.get(d['dropped'][:3] or d['added'][:3], 0) + 1
        print(f'  [B] 纯语法符差异 {len(soft)} 处（呈现物，允许）：' +
              ', '.join(f'{k!r}×{v}' for k, v in list(kinds.items())[:8]))
    print('[RESULT] ' + ('PASS' if not hard else 'FAIL —— T1 改过字，回 T1 修，别进 T3'))
    return 0 if not hard else 1


if __name__ == '__main__':
    sys.exit(main())
