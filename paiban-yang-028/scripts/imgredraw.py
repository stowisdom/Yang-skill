#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 · 图片重绘（T1b 第二步）：表格图→md 表格，代码截图→代码块，整页文字→纯文本。

用法：
    py -3.12 scripts/imgredraw.py --img images/img_001.png --kind table --task 任务目录
    py -3.12 scripts/imgredraw.py --img images/img_002.png --kind code  --task 任务目录
    py -3.12 scripts/imgredraw.py --img images/img_003.png --kind text  --task 任务目录

OCR 引擎 = RapidOCR（onnxruntime 底座，numpy 2 原生）。PaddleOCR 老路已废弃，勿重试：
实测 paddleocr 3.x 删了 PPStructure；paddle 2.6 栈在本机 oneDNN/scale op 报错，全部 FLAGS 无效。
实测用法（2026-09-30，rapidocr 3.9.2 + rapid-table 3.0.2，写死在这里免得再去猜 API）：
    from rapidocr import RapidOCR
    out = RapidOCR()(img_path)          # → RapidOCROutput，扁平结构 .boxes(N×4×2)/.txts/.scores 等长对齐
    from rapid_table import RapidTable
    res = RapidTable()(img_path, ocr_results=[(out.boxes, tuple(out.txts), tuple(out.scores))])
    res.pred_htmls                      # → ['<html><body><table>…</table></body></html>']
首次运行自动校验/下载自带模型（det+rec+cls+table，约 40MB，国内多镜像通常顺）。

纪律（与 ASR 转写同一条「不猜字」）：OCR 产物必须经帆确认才算数。
    产物落 任务目录/redraw/<图名>.md（text 类是 .txt）；图片台账.json 对应条目改
    action=redrawn、confirmed=false。之后由 AI 把产物替换进 源文档.md（原图片行 →
    md 表格/代码块/正文），走现有管道进 原文.txt，铁律 1 的逐字守恒照常执法；
    帆人眼对过原图、把台账 confirmed 置 true，机检第 10 项才放行。拿不准的字标〔待确认〕，不许猜。

依赖纪律：rapidocr / rapid-table 只在函数内懒加载——typeset.py / check.py 主链绝不 import。
缺库处置：exit 2 + 傻瓜式安装步骤（不崩栈给看不懂的 traceback）。
退出码：0=成功；1=识别运行失败；2=用法错误/缺依赖。
"""
import argparse, importlib.util, json, sys
from html.parser import HTMLParser
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import imgdiag    # 台账读写、OCR 拍平与诊断字段同源，不另写一份

INSTALL_GUIDE = """未检测到图片重绘依赖（RapidOCR）。傻瓜式安装步骤：
  第 1 步：py -3.12 -m pip install rapidocr rapid-table
  第 2 步（验证）：py -3.12 scripts/selftest.py —— imgredraw-ocr / imgredraw-text 项由 skip 变 OK 即装好
  也可以不装：imgdiag.py 的降级分流（尺寸 + 等效 DPI + 横竖线网格）不需要任何三方库。"""

NEXT_STEPS = """产物已落盘，接下来的纪律动作（人工闸，机检第 10 项执法）：
  1. AI 把 redraw/ 产物替换进 源文档.md（原图片行 → md 表格/代码块/正文；text 产物先剥注释头）
  2. 帆人眼对原图确认 OCR 没认错字（拿不准的标〔待确认〕）
  3. 把 图片台账.json 里该图 confirmed 置 true
  4. 重跑 typeset.py --md —— 台账 confirmed=true 后机检第 10 项放行"""

# --kind text 产物头部的注释（替换进源文档时剥掉，不进 原文.txt）
TEXT_HEADER = """# 本文件由 imgredraw.py --kind text 从 {img} 整页 OCR 生成（RapidOCR）
# 容错纪律（同 ASR「不猜字」）：只纠有据可查的错（同音字按语义纠、词表有据），
# 拿不准的字标〔待确认〕，绝不猜字补字。替换进 源文档.md 时剥掉本注释头（# 开头的行）。


"""


def _p(s):
    """真控制台打中文；管道里按 check.py 的纪律降级 ASCII，不糊不崩。"""
    if not sys.stdout.isatty():
        s = s.encode('ascii', 'replace').decode('ascii')
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode('ascii', 'replace').decode('ascii'))


def _need_ocr(table=False):
    """缺依赖 → 打印安装步骤并 exit 2。探包不 import：rapidocr 的 import 本身要拉起 onnxruntime。"""
    if importlib.util.find_spec('rapidocr') is None:
        _p(INSTALL_GUIDE)
        raise SystemExit(2)
    if table and importlib.util.find_spec('rapid_table') is None:
        _p(INSTALL_GUIDE)
        raise SystemExit(2)


def _ocr(img_path):
    """懒加载 RapidOCR 并跑一张图 → [(x0,y0,x1,y1,text)]（格式拍平走 imgdiag 同一份）。"""
    from rapidocr import RapidOCR                  # 懒加载：缺库路径在 _need_ocr 已拦
    return imgdiag._flatten_ocr(RapidOCR()(str(img_path)))


# ---------------- 表格：RapidTable → HTML → md ----------------

class _TableParser(HTMLParser):
    """RapidTable 吐的 HTML 表格 → 行文本矩阵（stdlib html.parser，不引新依赖）。
    colspan/rowspan 只取首格文本不复制——重绘产物要人眼确认后替换进源文档，以「读得对」为先。"""

    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == 'tr':
            self._row = []
        elif tag in ('td', 'th') and self._row is not None:
            self._cell = []

    def handle_endtag(self, tag):
        if tag in ('td', 'th') and self._cell is not None:
            self._row.append(''.join(self._cell).strip())
            self._cell = None
        elif tag == 'tr' and self._row is not None:
            if any(self._row):
                self.rows.append(self._row)
            self._row = None

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)


def html_to_md_table(html):
    """HTML 表格 → md 表格。单元格里的 | 转义，竖线本就是 md 表格的语法符。"""
    p = _TableParser()
    p.feed(html)
    rows = p.rows
    if not rows:
        raise RuntimeError('RapidTable 的 HTML 里没解出表格行')
    ncol = max(len(r) for r in rows)
    rows = [r + [''] * (ncol - len(r)) for r in rows]
    esc = lambda c: c.replace('|', '\\|')
    md = ['| ' + ' | '.join(esc(c) for c in rows[0]) + ' |',
          '|' + ' --- |' * ncol]
    md += ['| ' + ' | '.join(esc(c) for c in r) + ' |' for r in rows[1:]]
    return '\n'.join(md) + '\n'


def redraw_table(img_path):
    """表格图 → md 表格文本。RapidTable 出结构（pred_htmls），文字由 RapidOCR 结果填进单元格。"""
    _need_ocr(table=True)
    from rapidocr import RapidOCR                  # 懒加载：缺库路径在 _need_ocr 已拦
    from rapid_table import RapidTable
    ocr_out = RapidOCR()(str(img_path))
    ocr_res = None
    if ocr_out is not None and getattr(ocr_out, 'boxes', None) is not None:
        # 实测签名：ocr_results = [(boxes ndarray, txts tuple, scores tuple)]（每张图一个三元组）
        ocr_res = [(ocr_out.boxes, tuple(ocr_out.txts), tuple(ocr_out.scores))]
    result = RapidTable()(str(img_path), ocr_results=ocr_res)
    htmls = [h for h in (getattr(result, 'pred_htmls', None) or []) if h]
    if not htmls:
        raise RuntimeError('RapidTable 没认出表格结构——这张图可能不是表格，回 imgdiag 看判型')
    return '\n'.join(html_to_md_table(h) for h in htmls)


# ---------------- 代码 / 整页文字：RapidOCR 通用识别 → 按行重组 ----------------

def regroup_code_lines(boxes):
    """OCR 碎块按 y 聚行、行内按 x 排序、按 x0 估算缩进。
    boxes: [(x0,y0,x1,y1,text)]。截图行高稳定，聚行容差取中位行高的 0.6；
    缩进按「x0 相对全文最小 x0 的差 ÷ 中位字宽」折算成空格。"""
    if not boxes:
        return []
    hs = sorted(y1 - y0 for _x0, y0, _x1, y1, _t in boxes)
    med_h = hs[len(hs) // 2] or 1
    tol = med_h * 0.6
    rows = []
    for b in sorted(boxes, key=lambda b: ((b[1] + b[3]) / 2, b[0])):
        yc = (b[1] + b[3]) / 2
        for row in rows:
            if abs(row['yc'] - yc) <= tol:
                n = len(row['items'])
                row['yc'] = (row['yc'] * n + yc) / (n + 1)
                row['items'].append(b)
                break
        else:
            rows.append({'yc': yc, 'items': [b]})
    rows.sort(key=lambda r: r['yc'])
    min_x0 = min(b[0] for b in boxes)
    cws = sorted((b[2] - b[0]) / max(len(b[4]), 1) for b in boxes if b[4].strip())
    cw = cws[len(cws) // 2] if cws else 8.0
    lines = []
    for row in rows:
        items = sorted(row['items'], key=lambda b: b[0])
        text, prev_x1 = '', None
        for b in items:
            if prev_x1 is not None and b[0] - prev_x1 > 0.5 * cw:
                text += ' '                       # 碎块间有明显空隙才补空格，不凭空加字
            text += b[4]
            prev_x1 = b[2]
        indent = max(0, round((items[0][0] - min_x0) / max(cw, 1)))
        lines.append(' ' * indent + text)
    return lines


def redraw_code(img_path):
    """代码截图 → 代码块文本（保留行结构与缩进）。"""
    _need_ocr()
    boxes = _ocr(img_path)
    if not boxes:
        raise RuntimeError('OCR 一个字都没认出来——这张图可能不是代码截图，回 imgdiag 看判型')
    return '```\n' + '\n'.join(regroup_code_lines(boxes)) + '\n```\n'


def redraw_text(img_path, img_name):
    """整页文字截图 → 纯文本（按 y 聚行，保留缩进），产物头部注释写明容错纪律。
    为什么产物是 .txt 而不是 .md：整页文字走散文管道，AI 审读纠字后替换进 源文档.md，
    注释头（# 行）在替换时剥掉，不进 原文.txt——否则铁律 1 的逐字守恒会判红。"""
    _need_ocr()
    boxes = _ocr(img_path)
    if not boxes:
        raise RuntimeError('OCR 一个字都没认出来——这张图可能不是文字页，回 imgdiag 看判型')
    body = '\n'.join(regroup_code_lines(boxes)) + '\n'
    return TEXT_HEADER.format(img=img_name) + body


# ---------------- 台账 ----------------

def update_ledger(task, img_name, out_name):
    """台账对应条目 → action=redrawn, confirmed=false（待帆确认）。
    台账缺失/缺条目时先补一条带诊断字段的——第 10 项只认「有记录 + 状态合规」。"""
    ledger = task / '图片台账.json'
    doc = None
    if ledger.exists():
        try:
            doc = json.loads(ledger.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            doc = None
    if doc is None:
        doc = {'version': 1, 'script': 'scripts/imgredraw.py', 'images': []}
    items = doc.setdefault('images', [])
    entry = next((e for e in items if isinstance(e, dict) and e.get('file') == img_name), None)
    if entry is None:
        entry = imgdiag.diagnose_one(task / 'images' / img_name)
        items.append(entry)
    entry['action'] = 'redrawn'
    entry['confirmed'] = False
    entry['notes'] = ((entry.get('notes') or '')
                      + f'｜已重绘 → redraw/{out_name}；待帆对原图确认后把 confirmed 置 true')
    ledger.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--img', required=True, help='图片路径（相对路径相对 --task 解析，如 images/img_001.png）')
    ap.add_argument('--kind', required=True, choices=['table', 'code', 'text'],
                    help='重绘类型：表格 / 代码 / 整页文字')
    ap.add_argument('--task', required=True, help='任务目录')
    a = ap.parse_args()

    task = Path(a.task)
    img = Path(a.img)
    if not img.is_absolute():
        img = task / img
    if not task.is_dir() or not img.exists():
        _p(f'[imgredraw] 任务目录或图片不存在：task={task} img={img}')
        return 2

    try:
        if a.kind == 'table':
            text, suffix = redraw_table(img), '.md'
        elif a.kind == 'code':
            text, suffix = redraw_code(img), '.md'
        else:
            text, suffix = redraw_text(img, img.name), '.txt'
    except SystemExit:
        raise
    except ImportError:
        _p(INSTALL_GUIDE)                          # rapidocr 装了但 rapid_table 没装等情况
        return 2
    except Exception as e:
        _p(f'[imgredraw] 识别失败：{e}\n原图保留在 images/ 备查；这张图可以改走人工转写，'
           f'台账手动记 action=redrawn + 产物路径。')
        return 1

    out_dir = task / 'redraw'
    out_dir.mkdir(exist_ok=True)
    out = out_dir / (img.stem + suffix)
    out.write_text(text, encoding='utf-8')
    update_ledger(task, img.name, out.name)
    print(f'[imgredraw] ok kind={a.kind} img={img.name} -> redraw/{out.name} '
          f'ledger=redrawn(confirmed=false)')
    _p(NEXT_STEPS)
    return 0


if __name__ == '__main__':
    sys.exit(main())
