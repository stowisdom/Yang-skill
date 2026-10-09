#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 长件机械臂：切章 / 合卷 / 看状态。

只干机械事：
  --split   把书/长文切成 chunks/NN-slug.md，写 结构台账.json
  --assemble 把各章产物拼成整卷 排版.html / 排版.pdf / 原文.txt，跑整卷机检
  --status  读台账与各章机检，打一张进度表

判断（L0-L5 编排、子 agent 标注决策）留给 AI，本脚本不替帆做内容决定。
"""
import argparse, json, re, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CHECK = HERE / 'check.py'


# ---------------- 结构计数（单一真源） ----------------
def count_structure(text):
    """统计 md 结构元素个数。台账对账用：切完后各章之和必须等于源文件 totals。"""
    counts = {
        'chars': len(text),
        'h1': 0, 'h2': 0, 'h3': 0,
        'tables': 0, 'table_rows': 0,
        'code_blocks': 0, 'code_lines': 0,
        'imgs': 0, 'list_items': 0,
    }
    in_fence = False
    in_table = False
    for line in text.splitlines():
        stripped = line.strip()
        # 代码围栏：只计 ``` 行本身，内部代码行交给 code_lines
        if re.match(r'^\s*```', stripped):
            in_fence = not in_fence
            if in_fence:
                counts['code_blocks'] += 1
            continue
        if in_fence:
            counts['code_lines'] += 1
            continue
        # 表格：连续 | 行算一张表，非分隔线的行算行数
        if stripped.startswith('|') and '|' in stripped[1:]:
            if not in_table:
                in_table = True
                counts['tables'] += 1
            if not re.fullmatch(r'[\s:\-|]+', stripped.strip('|').replace('|', '')):
                counts['table_rows'] += 1
            continue
        else:
            in_table = False
        # 标题
        if re.match(r'^#\s', stripped):
            counts['h1'] += 1
        elif re.match(r'^##\s', stripped):
            counts['h2'] += 1
        elif re.match(r'^###\s', stripped):
            counts['h3'] += 1
        # 列表项
        if re.match(r'^(?:[-*+]|\d+[.、])\s', stripped):
            counts['list_items'] += 1
        # 独立行图片
        if re.fullmatch(r'^\s*!\[([^\]]*)\]\(([^)]*)\)\s*$', stripped):
            counts['imgs'] += 1
    return counts


def slugify(title):
    """标题前 8 个汉字/字母/数字；空则 '续'。"""
    t = re.sub(r'[^\u4e00-\u9fffA-Za-z0-9]', '', title).strip()
    if not t:
        return '续'
    return t[:8]


# ---------------- 图片路径重写 ----------------
def rewrite_img_paths(text, src_dir):
    """把相对路径图片改成绝对路径；http(s) URL 原样保留。"""
    def repl(m):
        alt, src = m.group(1), m.group(2)
        if src.lower().startswith(('http://', 'https://')):
            return m.group(0)
        p = Path(src)
        if not p.is_absolute():
            p = src_dir / p
        return f'![{alt}]({p.as_posix()})'
    return re.sub(r'!\[([^\]]*)\]\(([^)]*)\)', repl, text)


# ---------------- Markdown 切章 ----------------
def _heading_level(line):
    m = re.match(r'^(#{1,6})\s', line.strip())
    return len(m.group(1)) if m else None


def _split_points(text, level):
    """返回所有可下刀的行号（指定层级标题行，不在围栏/表格内）。"""
    points = []
    in_fence = False
    in_table = False
    ls = text.splitlines()
    for i, line in enumerate(ls):
        stripped = line.strip()
        if re.match(r'^\s*```', stripped):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        if stripped.startswith('|') and '|' in stripped[1:]:
            in_table = True
            continue
        else:
            in_table = False
        lvl = _heading_level(line)
        if lvl == level:
            points.append(i)
    return points


def _split_by_level(text, level, max_chars):
    """按 level 级标题切；**切点之前的内容自成一快，一块都不许丢**；超限则降一级再切。

    2026-10-06 修两处静默丢块：
      1) 旧实现对 `len(sub) > max_chars` 之外的子块不 append ⇒ 整章被丢；
      2) 切点列表直接从第一个标题起算 ⇒ 首个标题之前的封面/引言被跳过。
    """
    if level > 3:
        return [text.strip()] if text.strip() else []
    points = _split_points(text, level)
    if not points:
        return _split_by_level(text, level + 1, max_chars)
    ls = text.splitlines()
    bounds = [0] + list(points) + [len(ls)]
    out = []
    for a, b in zip(bounds, bounds[1:]):
        seg = '\n'.join(ls[a:b]).strip()
        if not seg:
            continue
        if len(seg) > max_chars:
            out.extend(_split_by_level(seg, level + 1, max_chars))
        else:
            out.append(seg)
    return out


def split_md(text, max_chars):
    """按 h1→h2→h3 切章；绝不切在代码围栏或表格内部。"""
    return [c for c in _split_by_level(text, 1, max_chars) if c]


# ---------------- 散文切章 ----------------
def split_prose(text, max_chars):
    """按段落边界在 max_chars 附近切，落刀必须在句末标点之后。"""
    paras = [p.strip() for p in text.split('\n\n') if p.strip()]
    chunks = []
    buf, buf_len = [], 0
    for p in paras:
        p_len = len(p)
        if buf and buf_len + p_len > max_chars:
            chunks.append('\n\n'.join(buf))
            buf, buf_len = [p], p_len
        else:
            buf.append(p)
            buf_len += p_len
        # 单段就超 max_chars：按句切
        if p_len > max_chars:
            sentences = re.split(r'(?<=[。！？])', p)
            mini, mini_len = [], 0
            for s in sentences:
                s = s.strip()
                if not s:
                    continue
                if mini and mini_len + len(s) > max_chars:
                    chunks.append(''.join(mini))
                    mini, mini_len = [s], len(s)
                else:
                    mini.append(s)
                    mini_len += len(s)
            if mini:
                chunks[-1] = chunks[-1] + '\n\n' + ''.join(mini) if buf_len - p_len > 0 else ''.join(mini)
            buf, buf_len = [], 0
    if buf:
        chunks.append('\n\n'.join(buf))
    return [c.strip() for c in chunks if c.strip()]


# ---------------- 读写工具 ----------------
def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


# ---------------- split 命令 ----------------
def cmd_split(args):
    src = Path(args.src).resolve()
    task_dir = Path(args.dir)
    task_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir = task_dir / 'chunks'
    chunks_dir.mkdir(parents=True, exist_ok=True)

    raw = src.read_text(encoding='utf-8')
    totals = count_structure(raw)

    if args.md:
        pieces = split_md(raw, args.max_chars)
    else:
        pieces = split_prose(raw, args.max_chars)

    records = []
    for n, piece in enumerate(pieces, 1):
        # 取首行标题做 slug；散文取前 8 字
        first_line = piece.splitlines()[0].strip() if piece.strip() else ''
        if args.md:
            m = re.match(r'^#{1,6}\s+(.*)$', first_line)
            title = m.group(1).strip() if m else first_line
        else:
            title = first_line
        slug = slugify(title)
        fn = f'{n:02d}-{slug}.md'
        # 图片路径重写：相对路径 → 绝对路径
        piece = rewrite_img_paths(piece, src.parent)
        (chunks_dir / fn).write_text(piece, encoding='utf-8')
        counts = count_structure(piece)
        records.append({'file': f'chunks/{fn}', 'title': title, 'chars': len(piece), 'counts': counts})
        print(f'[split] {n:02d}: {fn}  chars={len(piece)}  h1={counts["h1"]} h2={counts["h2"]} h3={counts["h3"]} '
              f'tables={counts["tables"]} imgs={counts["imgs"]} code={counts["code_blocks"]}')

    # 校验：各章 counts 求和 == totals
    sum_counts = {k: 0 for k in totals if k != 'chars'}
    for r in records:
        for k in sum_counts:
            sum_counts[k] += r['counts'][k]
    mismatches = {k: (totals[k], sum_counts[k]) for k in sum_counts if totals[k] != sum_counts[k]}

    ledger = {
        'source': str(src),
        'max_chars': args.max_chars,
        'md': args.md,
        'totals': totals,
        'chunks': records,
        'checksum_ok': not mismatches,
        'mismatches': mismatches,
    }
    write_json(task_dir / '结构台账.json', ledger)

    print(f'[split] totals: chars={totals["chars"]}  h1={totals["h1"]} h2={totals["h2"]} h3={totals["h3"]} '
          f'tables={totals["tables"]} imgs={totals["imgs"]} code={totals["code_blocks"]}')
    if mismatches:
        print(f'[split] FAIL 切章对账红：{mismatches}')
        return 1
    print('[split] PASS 切章对账绿')
    return 0


# ---------------- assemble 命令 ----------------
def _extract_head(html):
    """取 <head>...</head> 内容。"""
    m = re.search(r'<head[^>]*>(.*?)</head>', html, re.S | re.I)
    return m.group(1) if m else ''


def _extract_pages(html):
    """取 <div class="page">...</div> 块列表。按 div 嵌套深度匹配，避免被内部 div 干扰。"""
    pages = []
    i = 0
    while True:
        start = html.find('<div class="page', i)
        if start < 0:
            break
        # 找到开标签结束位置
        tag_end = html.find('>', start)
        if tag_end < 0:
            break
        depth = 1
        j = tag_end + 1
        while j < len(html) and depth > 0:
            next_open = html.find('<div', j)
            next_close = html.find('</div>', j)
            if next_close < 0:
                break
            if next_open >= 0 and next_open < next_close:
                depth += 1
                j = next_open + 4
            else:
                depth -= 1
                j = next_close + 6
                if depth == 0:
                    pages.append(html[start:j])
        i = j
    return pages


def _chunk_num(record_file):
    """从 chunks/NN-slug.md 文件名取 NN。"""
    return Path(record_file).stem.split('-')[0]


def cmd_assemble(args):
    task_dir = Path(args.dir)
    ledger_path = task_dir / '结构台账.json'
    if not ledger_path.exists():
        print('[assemble] FAIL 找不到 结构台账.json')
        return 1
    ledger = read_json(ledger_path)

    # 1. 结构总账：对源文件重算，并和各章 counts 求和比对
    src = Path(ledger['source'])
    if not src.exists():
        print(f'[assemble] FAIL 源文件不存在：{src}')
        return 1
    totals_now = count_structure(src.read_text(encoding='utf-8'))
    sum_counts = {k: 0 for k in totals_now if k != 'chars'}
    for r in ledger['chunks']:
        for k in sum_counts:
            sum_counts[k] += r['counts'][k]
    mismatches = {k: (totals_now[k], sum_counts[k]) for k in sum_counts if totals_now[k] != sum_counts[k]}
    if mismatches:
        print(f'[assemble] FAIL 结构台账红：{mismatches}')
        return 1
    print('[assemble] 结构总账绿')

    # 2. 拼 原文.txt
    orig_parts = []
    for r in ledger['chunks']:
        chunk_dir = task_dir / 'chunks' / _chunk_num(r['file'])
        orig_file = chunk_dir / '原文.txt'
        if not orig_file.exists():
            print(f'[assemble] FAIL 缺 原文.txt：{orig_file}')
            return 1
        orig_parts.append(orig_file.read_text(encoding='utf-8'))
    full_orig = ''.join(orig_parts)
    (task_dir / '原文.txt').write_text(full_orig, encoding='utf-8')
    print(f'[assemble] 原文.txt 合并完成：{len(full_orig)} 字')

    # 3. 拼 排版.html：用第一章的 head，取各章 .page 块，改写 img src
    pages_html = []
    first_head = ''
    for r in ledger['chunks']:
        chunk_dir = task_dir / 'chunks' / _chunk_num(r['file'])
        html_file = chunk_dir / '排版.html'
        if not html_file.exists():
            print(f'[assemble] FAIL 缺 排版.html：{html_file}')
            return 1
        html = html_file.read_text(encoding='utf-8')
        if not first_head:
            first_head = _extract_head(html)
        chunk_rel = f'chunks/{_chunk_num(r["file"])}'
        for block in _extract_pages(html):
            # 把 src="images/..." 改成 src="chunks/NN/images/..."
            block = re.sub(r'src="images/([^"]+)"', f'src="{chunk_rel}/images/\\1"', block)
            pages_html.append(block)

    full_html = ('<!doctype html>\n<html lang="zh"><head><meta charset="utf-8">' + first_head +
                 '</head>\n<body>\n' + '\n'.join(pages_html) + '\n</body></html>\n')
    (task_dir / '排版.html').write_text(full_html, encoding='utf-8')
    print(f'[assemble] 排版.html 合并完成：{len(pages_html)} 页')

    # 4. 并 PDF：先探针，再合并
    try:
        import pypdfium2 as pdfium
    except ImportError:
        print('[assemble] FAIL 缺少 pypdfium2，无法合并 PDF')
        return 1
    pdf_files = []
    for r in ledger['chunks']:
        chunk_dir = task_dir / 'chunks' / _chunk_num(r['file'])
        pdf_file = chunk_dir / '排版.pdf'
        if not pdf_file.exists():
            print(f'[assemble] FAIL 缺 排版.pdf：{pdf_file}')
            return 1
        pdf_files.append(str(pdf_file))
    merged = pdfium.PdfDocument.new()
    for pf in pdf_files:
        src = pdfium.PdfDocument(pf)
        merged.import_pages(src, pages=list(range(len(src))), index=len(merged))
        src.close()
    merged.save(str(task_dir / '排版.pdf'))
    merged.close()
    n_pages_merged = len(pdfium.PdfDocument(str(task_dir / '排版.pdf')))
    print(f'[assemble] 排版.pdf 合并完成：{n_pages_merged} 页')

    # 5. 整卷机检
    injected = task_dir / '标注清单.json'
    cmd = [sys.executable, str(CHECK), '--orig', str(task_dir / '原文.txt'),
           '--html', str(task_dir / '排版.html'), '--out', str(task_dir / '机检.json'),
           '--pdf', str(task_dir / '排版.pdf')]
    if injected.exists():
        cmd += ['--injected', str(injected)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    report = read_json(task_dir / '机检.json') if (task_dir / '机检.json').exists() else {'pass': False, 'checks': []}
    passed = report.get('pass', False)
    red = [c['name'] for c in report.get('checks', []) if not c.get('pass')]
    if not passed:
        print(f'[assemble] FAIL 整卷机检红：{red}')
        return 1
    print(f'[assemble] PASS 整卷机检绿')
    print(f'[assemble] 交付：章数={len(ledger["chunks"])} 页数={n_pages_merged} 字数={len(full_orig)} pass=True')
    return 0


# ---------------- status 命令 ----------------
def cmd_status(args):
    task_dir = Path(args.dir)
    ledger_path = task_dir / '结构台账.json'
    if not ledger_path.exists():
        print('[status] FAIL 找不到 结构台账.json')
        return 1
    ledger = read_json(ledger_path)
    print(f'{"章":>3}  {"标题":<16} {"字数":>8} {"页数":>6} 状态')
    total_chars = 0
    total_pages = 0
    for r in ledger['chunks']:
        chunk_dir = task_dir / 'chunks' / _chunk_num(r['file'])
        check_file = chunk_dir / '机检.json'
        if check_file.exists():
            j = read_json(check_file)
            ok = j.get('pass', False)
            red = ','.join(c['name'] for c in j.get('checks', []) if not c.get('pass'))
            status = 'PASS' if ok else f'FAIL:{red}'
            pages = len(re.findall(r'<div class="page[^"]*"[^>]*>', (chunk_dir / '排版.html').read_text(encoding='utf-8'))) if (chunk_dir / '排版.html').exists() else 0
        else:
            status = 'TODO'
            pages = 0
        n = int(Path(r['file']).stem.split('-')[0])
        title = r['title'][:14]
        print(f'{n:3}  {title:<16} {r["chars"]:>8} {pages:>6} {status}')
        total_chars += r['chars']
        total_pages += pages
    print(f'{"合计":>3}  {"":<16} {total_chars:>8} {total_pages:>6}')
    return 0


# ---------------- 入口 ----------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--split', action='store_true')
    ap.add_argument('--assemble', action='store_true')
    ap.add_argument('--status', action='store_true')
    ap.add_argument('--in', dest='src')
    ap.add_argument('--dir', required=True)
    ap.add_argument('--md', action='store_true')
    ap.add_argument('--max-chars', type=int, default=20000)
    a = ap.parse_args()

    modes = sum([a.split, a.assemble, a.status])
    if modes != 1:
        print('[longdoc] 必须且只能指定 --split / --assemble / --status 之一')
        return 2
    if a.split and not a.src:
        print('[longdoc] --split 必须配 --in')
        return 2

    if a.split:
        return cmd_split(a)
    if a.assemble:
        return cmd_assemble(a)
    return cmd_status(a)


if __name__ == '__main__':
    sys.exit(main())
