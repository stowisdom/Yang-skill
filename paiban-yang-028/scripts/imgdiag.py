#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 · 图片诊断分流（T1b 第一步）。

用法：
    py -3.12 scripts/imgdiag.py --task 任务目录                  # 诊断 任务目录/images/ 下每张图
    py -3.12 scripts/imgdiag.py --task 任务目录 --pdf 书.pdf     # 先用 pypdfium2 抽内嵌图落盘再诊断

为什么存在：知识性图片（表格 / 代码截图 / 架构图）照搬进 PDF 会糊、字小看不清——
这是本模块要补的真问题。诊断先行：每张图先分流再定处置，结果落 任务目录/图片台账.json，
机检第 10 项（check.py:check_img_ledger）负责执法闭环。

四类分流：
    as-is    清晰插图/照片（等效 DPI ≥150 且文字少）   → 照搬，现有管道不动
    table    横竖线网格结构（表格型）                  → 建议 imgredraw.py --kind table 重绘为 md 表格
    code     等宽行结构、代码特征字符多（需 OCR 才判） → 建议 imgredraw.py --kind code 重绘为代码块
    diagram  文字占比中低、非表格线结构（架构图型）    → 本期照搬+警告；Mermaid 重绘在 P2，只登记命令

降级路径：没装 RapidOCR 也能跑——只按 尺寸 + 等效 DPI + 横竖线网格（纯像素，不依赖任何三方库）分流；
「疑似知识图」（宽 ≥400px 且等效 DPI <150）标 class=review，提示装 OCR 或人工判型。
重依赖纪律：rapidocr 只在 classify_with_ocr 内懒加载（onnxruntime 底座，numpy 2 原生）；
pypdfium2 仅 --pdf 模式用（函数内 import）。
实测环境（2026-09-30）：rapidocr 3.9.2（`from rapidocr import RapidOCR`，返回 RapidOCROutput
扁平结构 .boxes/.txts/.scores，不是 PaddleOCR 的按页嵌套）+ rapid-table 3.0.2。
PaddleOCR 老路已废弃（实测：3.x 删了 PPStructure；2.6 栈在本机 oneDNN/scale op 报错，勿重试）。
台账写盘合并纪律：action 已是 redrawn/fullpage（过了诊断阶段的状态）的条目，重跑只刷新诊断字段，
不许把状态打回 proposed。
退出码：0=正常；2=用法/文件错误。
"""
import argparse, json, sys, zlib
from pathlib import Path

IMG_EXTS = ('.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp')

PRINT_DPI = 120.0     # 与 typeset.IMG_PRINT_DPI 同一地板口径：120 DPI = 印刷可读下限
PAGE_W_MM = 160.0     # 版心宽：纸面落图最宽 160mm（typeset.IMG_MAX_W_MM）
DPI_BLUR = 150.0      # 等效 DPI 低于此判「打印会糊」——120 地板口径下仍有富余才放行
KNOW_PX_W = 400       # 宽 ≥400px 且糊 → 疑似知识图，提示人工判型 / 装 OCR
LINE_DARK = 128       # 暗像素灰度阈值（作用于已二值化的行表：0=墨，255=纸）
LINE_INK = 210        # 二值化阈值：浅灰表格边框（实测 51~200 都有）也算墨
H_LINE_FRAC = 0.55    # 一行暗像素占比 ≥55% 记一条横线（表格边框通常通栏）
V_LINE_FRAC = 0.40    # 一列暗像素占比 ≥40% 记一条竖线（竖线只在表格区高度内，不贯穿整图）
ANALYZE_W = 600       # 像素分析先把宽采样到 ≤600：纯 Python 扫大图太慢，判型不需要全分辨率
TERMINAL_ACTIONS = ('redrawn', 'fullpage')   # 过了诊断阶段的状态，重跑 imgdiag 不许覆盖


def _p(s):
    """明细等中文行：真控制台打中文；被重定向到管道时按 check.py 的纪律降级成 ASCII 替身——
    GBK 管道会把中文糊掉（Windows 实测），宁可是 ??? 也不吐乱码。"""
    if not sys.stdout.isatty():
        s = s.encode('ascii', 'replace').decode('ascii')
    try:
        print(s)
    except UnicodeEncodeError:
        print(s.encode('ascii', 'replace').decode('ascii'))


def dpi_eff(px_w):
    """等效 DPI = 图真正落到纸面上时的分辨率。
    与 typeset._scale_img_mm 同一份账：纸面宽 = min(px_w/120*25.4, 160mm)
    （120 DPI 地板折算，超版心宽则压回 160mm），实际 DPI = px_w / 纸面宽。"""
    paper_w = min(px_w * 25.4 / PRINT_DPI, PAGE_W_MM)
    return px_w * 25.4 / paper_w


# ---------------- 读尺寸 / 读像素（PIL 优先，stdlib 兜底） ----------------

def img_size(path):
    """读图片像素尺寸。算法与 typeset._img_size 同源（PIL → PNG/JPEG 读头）。"""
    try:
        from PIL import Image
        with Image.open(path) as im:
            return im.size
    except ImportError:
        pass
    data = Path(path).read_bytes()
    if data.startswith(b'\x89PNG\r\n\x1a\n'):
        i = 16
        while i < len(data):
            length = int.from_bytes(data[i:i + 4], 'big')
            if data[i + 4:i + 8] == b'IHDR':
                return (int.from_bytes(data[i + 8:i + 12], 'big'),
                        int.from_bytes(data[i + 12:i + 16], 'big'))
            i += 12 + length + 4
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
                return (int.from_bytes(data[i + 7:i + 9], 'big'),
                        int.from_bytes(data[i + 5:i + 7], 'big'))
            i += 2 + length
    raise RuntimeError(f'读不出图片尺寸（需要 pillow）：{path}')


def _paeth(a, b, c):
    p = a + b - c
    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    return b if pb <= pc else c


def _png_gray_stdlib(path):
    """纯 stdlib 解 PNG 成全分辨率灰度行表：8bit、非隔行、灰度/RGB/GA/RGBA，五种 filter 全支持。
    为什么自己写一份：imgdiag 的降级路径不许依赖 Pillow——selftest 的合成图就是这条路的实测对象。
    降采样不在这里做（像素级 min-pool 由 _binarize_downsample 统一负责）。"""
    data = Path(path).read_bytes()
    if not data.startswith(b'\x89PNG\r\n\x1a\n'):
        raise ValueError('not png')
    i, idat, meta = 8, bytearray(), None
    while i < len(data):
        ln = int.from_bytes(data[i:i + 4], 'big')
        tag, body = data[i + 4:i + 8], data[i + 8:i + 8 + ln]
        if tag == b'IHDR':
            meta = body
        elif tag == b'IDAT':
            idat += body
        elif tag == b'IEND':
            break
        i += 12 + ln
    if meta is None:
        raise ValueError('no IHDR')
    w, h, bd, ct, _comp, _flt, inter = (int.from_bytes(meta[0:4], 'big'), int.from_bytes(meta[4:8], 'big'),
                                        meta[8], meta[9], meta[10], meta[11], meta[12])
    if bd != 8 or inter:
        raise ValueError(f'只支持 8bit 非隔行 PNG（bitdepth={bd} interlace={inter}）')
    ch = {0: 1, 2: 3, 4: 2, 6: 4}[ct]
    raw = zlib.decompress(bytes(idat))
    stride = w * ch
    rows, prev, pos = [], bytearray(stride), 0
    for _y in range(h):
        f = raw[pos]
        line = bytearray(raw[pos + 1:pos + 1 + stride])
        pos += 1 + stride
        if f == 1:      # Sub
            for x in range(ch, stride):
                line[x] = (line[x] + line[x - ch]) & 255
        elif f == 2:    # Up
            for x in range(stride):
                line[x] = (line[x] + prev[x]) & 255
        elif f == 3:    # Average
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                line[x] = (line[x] + ((a + prev[x]) >> 1)) & 255
        elif f == 4:    # Paeth
            for x in range(stride):
                a = line[x - ch] if x >= ch else 0
                c = prev[x - ch] if x >= ch else 0
                line[x] = (line[x] + _paeth(a, prev[x], c)) & 255
        elif f != 0:
            raise ValueError(f'unknown filter {f}')
        if ch >= 3:
            rows.append([(line[x * ch] * 299 + line[x * ch + 1] * 587 + line[x * ch + 2] * 114) // 1000
                         for x in range(w)])
        else:
            rows.append([line[x * ch] for x in range(w)])
    return rows


def _binarize_downsample(rows, max_w):
    """灰度行表 → 二值行表（0=墨/255=纸），宽超 max_w 时按块 min-pool（块内有墨即墨）。
    为什么不能均值降采样：2026-09-30 实测，900×320 表格截图均值缩到 600 宽后
    1px 竖线被平均成灰整条消失（4 条竖线全丢、6 条横线只剩 2 条），网格判型直接失明。
    先按 210 二值化再 min-pool，细线在降采样后依然整根保住。"""
    rows = [[0 if v < LINE_INK else 255 for v in row] for row in rows]
    w, h = len(rows[0]), len(rows)
    step = max(1, w // max_w)
    if step == 1:
        return rows
    out = []
    for y in range(0, h, step):
        band = rows[y:y + step]
        out.append([0 if any(b[x] == 0 for b in band) else 255
                    for x in range(0, w, step)])
    return out


def gray_pixels(path, max_w=ANALYZE_W):
    """→ 二值行表（list[list[int]]，0=墨/255=纸）或 None。Pillow 优先；无 Pillow 时 stdlib 解 PNG；
    JPEG 无 Pillow 则放弃（退回尺寸+DPI 分流）。"""
    try:
        from PIL import Image
    except ImportError:
        Image = None
    if Image is not None:
        try:
            with Image.open(path) as im:
                g = im.convert('L').point(lambda v: 0 if v < LINE_INK else 255)
                if g.width > max_w:
                    # 二值化后再 BOX 均值缩放：块内有墨均值就被拉低，阈值 250 等价 min-pool 的近似
                    g = g.resize((max_w, max(1, round(g.height * max_w / g.width))), Image.BOX)
                    g = g.point(lambda v: 0 if v < 250 else 255)
                w, h = g.size
                data = g.tobytes()          # 'L' 模式一字节一像素；Pillow 12 起 getdata 弃用
                return [list(data[y * w:(y + 1) * w]) for y in range(h)]
        except Exception:
            pass
    if str(path).lower().endswith('.png'):
        try:
            return _binarize_downsample(_png_gray_stdlib(path), max_w)
        except Exception:
            return None
    return None


def detect_grid(rows):
    """横竖线检测（输入是二值行表：0=墨/255=纸）：行墨占比 ≥H_LINE_FRAC 记横线、
    列 ≥V_LINE_FRAC 记竖线，相邻成行并成一条。返回 (横线条数, 竖线条数, 墨总占比)。
    为什么纯像素判表格线：表格的横竖边框是图里最稳的结构特征，不需要 OCR、不需要装任何库。
    阈值实测口径：横线要 ≥3 条或竖线 ≥3 条才算网格——一个矩形外框（2横×2竖）不算，
    否则带边框的照片会被系统性误判成表格。"""
    nw, nh = len(rows[0]), len(rows)
    dark_tot = 0
    h_flags = []
    for row in rows:
        d = sum(1 for v in row if v < LINE_DARK)
        dark_tot += d
        h_flags.append(d >= nw * H_LINE_FRAC)
    v_flags = []
    for x in range(nw):
        d = sum(1 for y in range(nh) if rows[y][x] < LINE_DARK)
        v_flags.append(d >= nh * V_LINE_FRAC)

    def bands(flags):
        n, run = 0, False
        for f in flags:
            if f and not run:
                n, run = n + 1, True
            elif not f:
                run = False
        return n

    return bands(h_flags), bands(v_flags), dark_tot / max(nw * nh, 1)


# ---------------- 分流 ----------------

def _is_grid(grid):
    """网格判据：≥3横+≥2竖 或 ≥2横+≥3竖。矩形外框（2×2）刻意不算，见 detect_grid。"""
    return bool(grid) and ((grid[0] >= 3 and grid[1] >= 2) or (grid[0] >= 2 and grid[1] >= 3))


def classify_basic(px_w, px_h, grid):
    """无 OCR 降级分流：尺寸 + 等效 DPI + 横竖线网格。"""
    dpi = dpi_eff(px_w)
    if _is_grid(grid):
        note = (f'检测到横竖线网格（横 {grid[0]} 条 × 竖 {grid[1]} 条），判表格型；'
                + (f'等效 DPI {dpi:.0f}<150，直接印会糊。' if dpi < DPI_BLUR else f'等效 DPI {dpi:.0f} 达标，也可照搬。')
                + '建议 py -3.12 scripts/imgredraw.py --kind table 重绘为 md 表格（proposed，待帆拍板）')
        return 'table', 'redraw-table', note
    if dpi >= DPI_BLUR:
        return 'as-is', 'as-is', f'等效 DPI {dpi:.0f} ≥150 且无表格线结构，清晰插图/照片，照搬'
    if px_w >= KNOW_PX_W:
        return 'review', 'review', (
            f'疑似知识图：宽 {px_w}px ≥400 且等效 DPI {dpi:.0f} <150，直接印会糊；'
            '无 OCR 不能细分表格/代码/架构图。建议：① 装 RapidOCR 后重跑本脚本自动判型'
            '（安装步骤见 REFERENCE.md「图片处理（T1b）」节）；② 或人工判型后 imgredraw.py --kind table|code')
    return 'as-is', 'as-is', f'小图（{px_w}px 宽），等效 DPI {dpi:.0f}，照搬（可能略糊，交付时提醒帆瞄一眼）'


_OCR_ENGINE = None   # RapidOCR 单例：模型只加载一次，一个任务目录多张图复用


def _flatten_ocr(out):
    """RapidOCR 的 RapidOCROutput → [(x0,y0,x1,y1,text)]。
    实测（rapidocr 3.9.2）：返回扁平结构，.boxes 是 N×4×2 四点坐标数组，.txts/.scores 等长对齐；
    空页/检不出时 .boxes 是 None。"""
    if out is None or getattr(out, 'boxes', None) is None:
        return []
    res = []
    for box, text in zip(out.boxes, out.txts):
        xs = [float(p[0]) for p in box]
        ys = [float(p[1]) for p in box]
        res.append((min(xs), min(ys), max(xs), max(ys), str(text)))
    return res


def classify_with_ocr(img_path, px_w, px_h, grid):
    """有 RapidOCR 时用文字占比细分 code / diagram / as-is；表格仍以网格线为准（OCR 认线不如像素直判）。
    任何一步失败返回 None 回退 classify_basic——OCR 是增强，不是前提。"""
    global _OCR_ENGINE
    try:
        from rapidocr import RapidOCR              # 懒加载：主链与无 OCR 环境都不需要它
    except ImportError:
        return None
    try:
        if _OCR_ENGINE is None:
            _OCR_ENGINE = RapidOCR()               # 首跑自动下载/校验自带模型（约 40MB，多镜像）
        boxes = _flatten_ocr(_OCR_ENGINE(str(img_path)))
    except Exception:
        return None
    dpi = dpi_eff(px_w)
    if _is_grid(grid):
        return 'table', 'redraw-table', (
            f'横竖线网格（横 {grid[0]} × 竖 {grid[1]}）+ OCR 到 {len(boxes)} 个文本块，判表格型；'
            f'建议 imgredraw.py --kind table 重绘为 md 表格（proposed，待帆拍板）')
    if not boxes:
        return 'as-is', 'as-is', f'OCR 无文字；等效 DPI {dpi:.0f}，插图/照片，照搬'
    area = sum((x1 - x0) * (y1 - y0) for x0, y0, x1, y1, _t in boxes) / max(px_w * px_h, 1)
    text = ''.join(t for _x0, _y0, _x1, _y1, t in boxes)
    codeish = sum(1 for c in text if c in '=#{}()<>;/_') / max(len(text), 1)
    if len(boxes) >= 4 and codeish >= 0.06:
        return 'code', 'redraw-code', (
            f'OCR {len(boxes)} 行、代码特征字符占比 {codeish:.0%}，判代码型；'
            f'建议 imgredraw.py --kind code 重绘为代码块（proposed，待帆拍板）')
    if area < 0.03:
        return 'as-is', 'as-is', f'文字占比 {area:.0%} 极低；等效 DPI {dpi:.0f}，插图/照片，照搬'
    return 'diagram', 'as-is', (
        f'文字占比 {area:.0%} 中低、非表格线结构 → 架构图型，本期照搬'
        + (f'；等效 DPI {dpi:.0f}<150，缩到看不清时建议 typeset --fig-fullpage 独占页' if dpi < DPI_BLUR else '')
        + '；Mermaid 重绘在 P2，只登记命令')


def diagnose_one(path):
    """单张图 → 台账条目。读不出尺寸/像素时如实记 unknown，不猜。"""
    e = {'file': path.name, 'px_w': 0, 'px_h': 0, 'dpi_eff': 0, 'class': 'unknown',
         'action': 'review', 'confirmed': False, 'notes': ''}
    try:
        px_w, px_h = img_size(path)
    except Exception as ex:
        e['notes'] = f'读不出图片尺寸（{ex}），需人工判型'
        return e
    e.update(px_w=px_w, px_h=px_h, dpi_eff=round(dpi_eff(px_w), 1))
    px = gray_pixels(path)
    grid = detect_grid(px) if px else None
    r = classify_with_ocr(path, px_w, px_h, grid)
    if r is None:
        r = classify_basic(px_w, px_h, grid)
    e['class'], e['action'], e['notes'] = r
    return e


# ---------------- 台账 ----------------

def write_ledger(task, entries):
    """写 图片台账.json。合并纪律：action 已是 redrawn/fullpage 的条目只刷新诊断字段，
    状态与 confirmed 原样保留——重跑诊断不许把「已重绘」「已拍板独占页」打回 proposed。
    返回 (保留状态数, 被移除的已消失图片名)。"""
    path = task / '图片台账.json'
    old = {}
    if path.exists():
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
            items = doc.get('images') if isinstance(doc, dict) else doc
            old = {e.get('file'): e for e in items or [] if isinstance(e, dict)}
        except (OSError, ValueError):
            pass            # 台账坏了：重诊断重建，保不住旧状态就如实从零开始
    merged, kept, stale = [], 0, set(old)
    for e in entries:
        o = old.get(e['file'])
        stale.discard(e['file'])
        if o and o.get('action') in TERMINAL_ACTIONS:
            kept += 1
            e['action'], e['confirmed'] = o['action'], bool(o.get('confirmed'))
            e['notes'] = (o.get('notes') or '') + f'｜imgdiag 重跑仅刷新诊断：class={e["class"]} dpi={e["dpi_eff"]}'
        merged.append(e)
    doc = {'version': 1, 'script': 'scripts/imgdiag.py',
           'fields': ('file/px_w/px_h/dpi_eff/class/action/confirmed/notes；'
                      'action 初值为建议动作（proposed 语义写在 notes），confirmed=false 待帆拍板；'
                      'action ∈ as-is|redraw-table|redraw-code|review|redrawn|fullpage'),
           'images': merged}
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding='utf-8')
    return kept, sorted(stale)


def read_ledger(task):
    """读台账 → {file: entry}；没有或坏了返回 {}（调用方自行决定空台账语义）。"""
    path = task / '图片台账.json'
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
        items = doc.get('images') if isinstance(doc, dict) else doc
        return {e.get('file'): e for e in items or [] if isinstance(e, dict) and e.get('file')}
    except (OSError, ValueError):
        return {}


# ---------------- --pdf 抽图 ----------------

def extract_pdf_images(pdf_path, img_dir):
    """用 pypdfium2 把 PDF 内嵌图抽落盘到 img_dir（懒加载：只有 --pdf 模式需要它）。
    返回抽到的文件名列表；抽不出的单张（exotic 编码）记警告跳过，不让一张坏图拖死整本。"""
    try:
        import pypdfium2 as pdfium
    except ImportError:
        _p('缺 pypdfium2：py -3.12 -m pip install pypdfium2')
        raise SystemExit(2)
    pdf = pdfium.PdfDocument(str(pdf_path))
    names, n = [], 0
    try:
        for page in pdf:
            for obj in page.get_objects():
                if obj.type != pdfium.raw.FPDF_PAGEOBJ_IMAGE:
                    continue
                n += 1
                stem = f'img_pdf_{n:03d}'
                try:
                    got = pdfium.PdfImage(obj).extract(str(img_dir / stem))
                    if got:
                        names.append(Path(got).name)
                        continue
                except Exception:
                    pass
                try:
                    # DCT/JPX 等编码 extract 不了时退回位图（要 Pillow）
                    out = img_dir / f'{stem}.png'
                    pdfium.PdfImage(obj).get_bitmap().to_pil().save(out)
                    names.append(out.name)
                except Exception:
                    _p(f'[WARN] 第 {n} 张内嵌图抽不出来，跳过')
    finally:
        pdf.close()
    return names


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--task', required=True, help='任务目录（含 images/）')
    ap.add_argument('--pdf', default=None, help='先把该 PDF 的内嵌图抽进 images/ 再诊断')
    a = ap.parse_args()

    task = Path(a.task)
    if not task.is_dir():
        _p(f'[imgdiag] 任务目录不存在：{task}')
        return 2
    img_dir = task / 'images'
    img_dir.mkdir(exist_ok=True)

    if a.pdf:
        src = Path(a.pdf)
        if not src.exists():
            _p(f'[imgdiag] PDF 不存在：{src}')
            return 2
        names = extract_pdf_images(src, img_dir)
        print(f'[imgdiag] pdf extract: {len(names)} images -> {img_dir.name}/')

    files = sorted(p for p in img_dir.iterdir() if p.suffix.lower() in IMG_EXTS)
    if not files:
        print('[imgdiag] no images in images/ (ledger not needed)')   # 空 images/ 时机检第 10 项空真通过
        return 0

    entries = [diagnose_one(f) for f in files]
    kept, stale = write_ledger(task, entries)
    for e in entries:
        print(f"[imgdiag] {e['file']} {e['px_w']}x{e['px_h']} dpi={e['dpi_eff']} "
              f"class={e['class']} action={e['action']}")
    print(f'[imgdiag] ledger -> 图片台账.json images={len(entries)} kept_states={kept} stale_removed={len(stale)}')
    _p('\n逐张明细（notes）：')
    for e in entries:
        _p(f"  {e['file']}：{e['notes']}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
