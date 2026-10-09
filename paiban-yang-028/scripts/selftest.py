#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 自测脚本：改脚本后跑一遍，23/23 PASS 才算完。
全部测试在临时目录进行，不污染 skill 目录。
最后两项 sync-checksums 查 S 区 / Q 区与 X 区是否同一份字节——三区不同源，等于没同步。
"""
import base64, importlib.util, json, os, re, shutil, subprocess, sys, tempfile, zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
TYPESET = HERE / 'typeset.py'
CHECK = HERE / 'check.py'
RENDER = HERE / 'render.py'
T1_AUDIT = HERE / 't1_audit.py'
GATE = HERE / 'gate.py'
IMGDIAG = HERE / 'imgdiag.py'
IMGREDRAW = HERE / 'imgredraw.py'

# 内嵌一个 1x1 透明 PNG，PIL 不可用时用
TINY_PNG = base64.b64decode(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI7wAAAABJRU5ErkJggg=='
)


def run(cmd, cwd=None, timeout=300, input_text=None):
    """运行命令，返回 (rc, stdout, stderr)。"""
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', cwd=cwd, timeout=timeout,
                       input=input_text)
    return r.returncode, r.stdout, r.stderr


def make_png(path, w=900, h=500):
    """生成一张测试 PNG。优先 PIL，失败用内嵌 tiny png 缩放不可行，所以只保证有图。"""
    try:
        from PIL import Image, ImageDraw
        im = Image.new('RGB', (w, h), '#faf6ef')
        draw = ImageDraw.Draw(im)
        draw.rectangle([50, 50, w - 50, h - 50], outline='#3a352e', width=4)
        draw.text((100, h // 2 - 20), f'Test {w}x{h}', fill='#3a352e')
        im.save(path)
        return True
    except Exception:
        path.write_bytes(TINY_PNG)
        return False


def _write_png_stdlib(path, w, h, pixel_fn):
    """纯 stdlib 写最小 PNG（8bit 灰度、非隔行、filter 0）：无 Pillow 时造测试图用。
    pixel_fn(x, y) → 0..255。与 imgdiag._png_gray_stdlib 的读取口径互为正反——
    写读两端都是自家实现，正好互测。"""
    import zlib, struct
    raw = b''.join(b'\x00' + bytes(pixel_fn(x, y) for x in range(w)) for y in range(h))

    def chunk(tag, data):
        return (struct.pack('>I', len(data)) + tag + data
                + struct.pack('>I', zlib.crc32(tag + data) & 0xffffffff))

    ihdr = struct.pack('>IIBBBBB', w, h, 8, 0, 0, 0, 0)
    Path(path).write_bytes(b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', ihdr)
                           + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b''))


def _table_pixel(w, h):
    """表格样图像素：4 横 × 4 竖通栏网格 + 单元格内深色小块（模拟文字墨点）。"""
    hlines = {10, 11, h // 3, h // 3 + 1, 2 * h // 3, 2 * h // 3 + 1, h - 11, h - 10}
    vlines = {5, 6, w // 3, w // 3 + 1, 2 * w // 3, 2 * w // 3 + 1, w - 6, w - 5}

    def fn(x, y):
        if y in hlines and 5 <= x <= w - 5:
            return 0
        if x in vlines and 10 <= y <= h - 10:
            return 0
        for r in range(3):
            for c in range(3):
                if 20 + c * (w // 3) <= x <= 60 + c * (w // 3) and 20 + r * (h // 3) <= y <= 28 + r * (h // 3):
                    return 0
        return 255
    return fn


def _text_font(size=26):
    """取一个能画中文的字体；找不到就退回 Pillow 默认位图字（画不了中文，只画 ASCII）。"""
    from PIL import ImageFont
    for cand in ('C:/Windows/Fonts/msyh.ttc', 'C:/Windows/Fonts/simsun.ttc',
                 'C:/Windows/Fonts/simhei.ttf'):
        try:
            return ImageFont.truetype(cand, size)
        except Exception:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def make_table_png(path, w=600, h=400):
    """表格样图（横竖线网格 + 单元格内真文字，RapidTable 真跑可验）。
    PIL 优先；无 PIL 用纯 stdlib 写最小 PNG（无文字，只有网格与色块）——
    imgdiag 的 stdlib 读图路（_png_gray_stdlib → _binarize_downsample）必须有自己的实测对象。"""
    try:
        from PIL import Image, ImageDraw
        im = Image.new('RGB', (w, h), 'white')
        d = ImageDraw.Draw(im)
        for y in (10, h // 3, 2 * h // 3, h - 10):
            d.line([(5, y), (w - 5, y)], fill='black', width=2)
        for x in (5, w // 3, 2 * w // 3, w - 5):
            d.line([(x, 10), (x, h - 10)], fill='black', width=2)
        font = _text_font(24)
        for r in range(3):
            for c in range(3):
                d.text((24 + c * (w // 3), 22 + r * (h // 3)), f'R{r}C{c}', fill='black', font=font)
        im.save(path)
    except Exception:
        _write_png_stdlib(path, w, h, _table_pixel(w, h))


def make_text_png(path, w=640, h=210):
    """整页文字截图样图（--kind text 的端到端对象）：三行混排，含一行缩进。
    无 PIL 返回 False，调用方走降级判定。"""
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return False
    im = Image.new('RGB', (w, h), 'white')
    d = ImageDraw.Draw(im)
    font = _text_font(26)
    for i, line in enumerate(['排版即内容测试行。', '第二行 with English words。',
                              '    缩进的一行收尾。']):
        d.text((24, 16 + i * 60), line, fill='black', font=font)
    im.save(path)
    return True


def make_gradient_png(path, w=1200, h=800):
    """大尺寸渐变无字图：无直线结构，等效 DPI ≈190 ≥150，应分流 as-is。"""
    try:
        from PIL import Image
        Image.linear_gradient('L').resize((w, h)).save(path)
    except Exception:
        _write_png_stdlib(path, w, h, lambda x, y: x * 255 // max(w - 1, 1))


def make_epub(path, title='测试', chapter_title='章一', body_html=None, image_bytes=None):
    """用 zipfile 造一个最小合法 EPUB（EPUB 2.0），供 epub2md 回归测试。"""
    path = Path(path)
    if body_html is None:
        body_html = f'<h1>{chapter_title}</h1><p>第一句。第二句。</p>'
    if image_bytes:
        body_html += '<p><img src="cover.png" alt="封面图"/></p>'
    with zipfile.ZipFile(path, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('mimetype', 'application/epub+zip', compress_type=zipfile.ZIP_STORED)
        z.writestr('META-INF/container.xml', '''<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>''')
        z.writestr('OEBPS/ch0.xhtml', f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml">
<head><meta charset="utf-8"/><title>{chapter_title}</title></head>
<body>{body_html}</body>
</html>''')
        manifest = '<item id="c1" href="ch0.xhtml" media-type="application/xhtml+xml"/>'
        if image_bytes:
            z.writestr('OEBPS/cover.png', image_bytes)
            manifest += '<item id="cover" href="cover.png" media-type="image/png"/>'
        z.writestr('OEBPS/content.opf', f'''<?xml version="1.0" encoding="UTF-8"?>
<package version="2.0" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:title>{title}</dc:title>
    <dc:language>zh-CN</dc:language>
  </metadata>
  <manifest>{manifest}</manifest>
  <spine><itemref idref="c1"/></spine>
</package>''')
    return path


def check_report(tmp, pdf=None):
    """读机检.json 返回 pass 与 checks 列表。"""
    jpath = tmp / '机检.json'
    if not jpath.exists():
        return False, []
    j = json.loads(jpath.read_text(encoding='utf-8'))
    return j.get('pass', False), j.get('checks', [])


def test_md_with_image():
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        make_png(tmp / 'img.png', 900, 500)
        (tmp / 't.md').write_text(
            '# 测试标题\n\n这是一段普通段落。\n\n![测试图片](img.png)\n\n'
            '## 二级标题\n\n| 列A | 列B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\n'
            '```python\nprint("hello")\n```\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md', '--render'])
        ok, checks = check_report(tmp)
        img_count = 0
        if ok and (tmp / '排版.pdf').exists():
            try:
                import pypdfium2 as pdfium
                pdf = pdfium.PdfDocument(str(tmp / '排版.pdf'))
                for page in pdf:
                    img_count += sum(1 for o in page.get_objects()
                                     if o.type == pdfium.raw.FPDF_PAGEOBJ_IMAGE)
                pdf.close()
            except Exception as e:
                return False, f'pdf image count error: {e}'
        return ok and img_count >= 1, f'pass={ok} images={img_count}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_md_no_image():
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 't.md').write_text(
            '# 无图回归\n\n这是一段普通段落。\n\n| 列A | 列B |\n|---|---|\n| 1 | 2 |\n| 3 | 4 |\n\n'
            '```python\nprint("hello")\n```\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md', '--render'])
        ok, _ = check_report(tmp)
        return ok, f'pass={ok}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_prose():
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 't.txt').write_text(
            '这是散文回归测试第一句。第二句验证纯文本分页行为。第三句收尾。\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.txt'),
                            '--dir', str(tmp), '--render'])
        ok, _ = check_report(tmp)
        return ok, f'pass={ok}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_missing_image():
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 't.md').write_text(
            '# 缺图源\n\n![不存在的图](nonexistent.png)\n\n一段文字。\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md'])
        _, checks = check_report(tmp)
        img = next((c for c in checks if c['name'] == 'img_integrity'), {})
        return img.get('pass') is False, f'img_integrity_pass={img.get("pass")}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_t1_audit_image():
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 'src.md').write_text(
            '![说明文字](http://x/y.png)\n\n正文一段。\n',
            encoding='utf-8')
        (tmp / 'orig.txt').write_text(
            '说明文字\n正文一段。\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(T1_AUDIT), '--src', str(tmp / 'src.md'),
                            '--orig', str(tmp / 'orig.txt'), '--md'])
        # stdout: hard=N ...
        m = re.search(r'hard=(\d+)', out)
        hard = int(m.group(1)) if m else -1
        return hard == 0 and rc == 0, f'hard={hard} rc={rc}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_gate():
    no_ok = json.dumps({"tool_name": "Bash", "tool_input": {"command": "edge --headless --print-to-pdf=a.pdf a.html"}})
    with_ok = json.dumps({"tool_name": "Bash", "tool_input": {"command": "edge --headless --print-to-pdf=a.pdf a.html --paiban-ok"}})
    rc1, _, _ = run(['py', '-3.14', str(GATE)], input_text=no_ok)
    rc2, _, _ = run(['py', '-3.14', str(GATE)], input_text=with_ok)
    return rc1 == 2 and rc2 == 0, f'no_ok_rc={rc1} with_ok_rc={rc2}'


def test_marks_skip_code():
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 't.md').write_text(
            '李笑来在书中提到，代码里要写 `LiXiaoLai` 才能匹配。\n',
            encoding='utf-8')
        (tmp / 'marks.json').write_text(
            json.dumps({'per': ['李笑来']}, ensure_ascii=False),
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md', '--marks', str(tmp / 'marks.json'), '--render'])
        ok, _ = check_report(tmp)
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace') if (tmp / '排版.html').exists() else ''
        # 代码段内不应出现标注符号
        code_bad = 'LiXiaoLai' in html and ('`李笑来`' in html or '「李笑来」' in html or '<span class="ci">李' in html)
        # 更精确：找 <span class="ci"> 内部不含「」
        ci_bad = bool(re.search(r'<span class="ci">[^<]*[「」<>{}][^<]*</span>', html))
        return ok and not ci_bad, f'pass={ok} code_marked={ci_bad}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_long_code_atom():
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        long_id = 'A' * 200
        (tmp / 't.md').write_text(
            f'超长代码标识符：`{long_id}`。\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md', '--render'])
        ok, _ = check_report(tmp)
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace') if (tmp / '排版.html').exists() else ''
        has_bare_sentinels = chr(0) in html or chr(1) in html
        return ok and not has_bare_sentinels, f'pass={ok} bare_sentinels={has_bare_sentinels}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _plain(s):
    """去标签 + 去空白：成品 HTML 里一行被切成多个 span，只有规范化后才能整句比对。"""
    return re.sub(r'\s+', '', re.sub(r'<[^>]+>', '', s))


def test_caption_merge():
    """图块回归（合并 Q 区实测）：紧跟图的「图9-1 …」题注必须与图同一个 figure，
    且题注进 原文.txt；版式不许自造「（图：）」这类壳（严格守恒会判红）。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        make_png(tmp / 'f.png', 700, 300)
        (tmp / 't.md').write_text(
            '# 图注合并\n\n正文一句收尾。\n\n![](f.png)\n图9-1 这是紧跟图的题注\n\n再来一句收尾。\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md'])
        ok, _ = check_report(tmp)
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace')
        # 注意：块上会盖 data-mm 戳，选择器必须允许 `<figure class="fig" data-mm="…">`
        figs = re.findall(r'<figure class="fig"[^>]*>.*?</figure>', html, re.S)
        in_fig = any('题注' in _plain(f) for f in figs)
        in_base = '题注' in _plain((tmp / '原文.txt').read_text(encoding='utf-8'))
        shell = '（图：' in html
        return ok and len(figs) == 1 and in_fig and in_base and not shell, \
            f'pass={ok} figures={len(figs)} cap_in_figure={in_fig} cap_in_base={in_base} shell={shell}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_fig_page_measured():
    """含图页的页高必须走浏览器实测（data-mm），不许悄悄退回估算模型——
    估算模型里没有图高，一旦退回，含图页的「硬半页」这道闸等于没关。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        make_png(tmp / 'w.png', 2400, 1600)          # 超宽：逼生成端按 160mm 物理闸缩放
        (tmp / 't.md').write_text(
            '# 含图页实测\n\n正文一句。\n\n![宽图](w.png)\n\n又一句收尾。\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md'])
        ok, checks = check_report(tmp)
        pf = next((c for c in checks if c['name'] == 'page_fill'), {})
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace')
        n_fig = len(re.findall(r'<figure class="fig"', html))
        return ok and n_fig >= 1 and pf.get('estimated') is False, \
            f'pass={ok} figures={n_fig} estimated={pf.get("estimated")} peak_mm={pf.get("peak_mm")}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------- T1b 图片处理模块 ----------

def _ledger_entry(tmp, name='img_001.png'):
    lp = tmp / '图片台账.json'
    if not lp.exists():
        return {}
    doc = json.loads(lp.read_text(encoding='utf-8'))
    ents = [e for e in doc.get('images', []) if e.get('file') == name]
    return ents[0] if ents else {}


def test_imgdiag_table():
    """带横竖线网格的表格样图 → imgdiag 应分流 table / 建议 redraw-table（纯像素判型，不需要 OCR）。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 'images').mkdir()
        make_table_png(tmp / 'images' / 'img_001.png')
        rc, out, err = run([sys.executable, str(IMGDIAG), '--task', str(tmp)])
        e = _ledger_entry(tmp)
        ok = (rc == 0 and e.get('class') == 'table' and e.get('action') == 'redraw-table'
              and e.get('confirmed') is False)
        return ok, f"rc={rc} class={e.get('class')} action={e.get('action')} dpi={e.get('dpi_eff')}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_imgdiag_photo():
    """大尺寸渐变无字图（无直线结构、等效 DPI≥150）→ 应分流 as-is 照搬。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 'images').mkdir()
        make_gradient_png(tmp / 'images' / 'img_001.png')
        rc, out, err = run([sys.executable, str(IMGDIAG), '--task', str(tmp)])
        e = _ledger_entry(tmp)
        ok = rc == 0 and e.get('class') == 'as-is' and e.get('action') == 'as-is'
        return ok, f"rc={rc} class={e.get('class')} action={e.get('action')} dpi={e.get('dpi_eff')}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _minimal_task(tmp, ledger_images=None):
    """最小任务目录：images/img_001.png + 原文.txt + 排版.html（一页一行），
    专测机检第 10 项 img_ledger 的执法，不走 typeset 全链。"""
    (tmp / 'images').mkdir(exist_ok=True)
    make_png(tmp / 'images' / 'img_001.png', 100, 60)
    (tmp / '原文.txt').write_text('一段。\n', encoding='utf-8')
    (tmp / '排版.html').write_text(
        '<!doctype html>\n<html lang="zh"><head><meta charset="utf-8"></head>\n<body>\n'
        '<div class="page">\n  <div class="content">\n    '
        '<div class="para l1"><span class="line"><span class="u">一段。</span></span></div>\n'
        '  </div>\n  <div class="writezone"></div>\n</div>\n</body></html>\n', encoding='utf-8')
    if ledger_images is not None:
        (tmp / '图片台账.json').write_text(
            json.dumps({'version': 1, 'images': ledger_images}, ensure_ascii=False), encoding='utf-8')


def _run_check10(tmp):
    run([sys.executable, str(CHECK), '--orig', str(tmp / '原文.txt'),
         '--html', str(tmp / '排版.html'), '--out', str(tmp / '机检.json')])
    j = json.loads((tmp / '机检.json').read_text(encoding='utf-8'))
    return j.get('pass'), next((c for c in j['checks'] if c['name'] == 'img_ledger'), {})


def test_img_ledger_missing():
    """有 images/ 无 图片台账.json → 第 10 项必须红（台账纪律：每张图的处置要有记录）。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        _minimal_task(tmp)
        overall, led = _run_check10(tmp)
        ok = led.get('pass') is False and led.get('missing_ledger') is True and overall is False
        return ok, f"img_ledger_pass={led.get('pass')} missing_ledger={led.get('missing_ledger')} overall={overall}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_img_ledger_unconfirmed():
    """redrawn 未确认（confirmed=false）→ 红；帆确认后（confirmed=true）→ 绿。
    OCR 产物机器验不了对错，这道人工闸是 T1b 的纪律核心。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        entry = {'file': 'img_001.png', 'px_w': 100, 'px_h': 60, 'dpi_eff': 120.0,
                 'class': 'table', 'action': 'redrawn', 'confirmed': False, 'notes': 't'}
        _minimal_task(tmp, [dict(entry)])
        _, led1 = _run_check10(tmp)
        entry['confirmed'] = True
        _minimal_task(tmp, [dict(entry)])
        overall2, led2 = _run_check10(tmp)
        ok = led1.get('pass') is False and led2.get('pass') is True and overall2 is True
        return ok, f"unconfirmed_pass={led1.get('pass')} confirmed_pass={led2.get('pass')} overall={overall2}"
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_figpage_exempt():
    """--fig-fullpage 独占页：图放宽到 200mm 上限、该页无写区、机检第 6 项豁免 140mm；
    普通页仍按 140mm 执法；台账登记 fullpage+confirmed 且第 10 项与 data-figpage 互证通过。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        make_png(tmp / 'tall.png', 800, 1900)        # 高图：普通页 140mm 装不下，独占页才放得下
        (tmp / 't.md').write_text(
            '# 独占页豁免\n\n开场一段，验证普通页仍按 140mm 执法。\n\n![高图](tall.png)\n\n'
            '收尾一段，跟在独占页后面。\n',
            encoding='utf-8')
        # 源名与新名都认：这里故意传源文件名 tall.png（归一化后是 img_001.png）
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md', '--fig-fullpage', 'tall.png'])
        ok, checks = check_report(tmp)
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace') \
            if (tmp / '排版.html').exists() else ''
        has_fp = '<div class="page figpage" data-figpage="img_001.png">' in html
        pf = next((c for c in checks if c['name'] == 'page_fill'), {})
        rows = pf.get('pages') or []
        fig_rows = [r for r in rows if r.get('figpage')]
        normal = [r for r in rows if not r.get('figpage')]
        led = _ledger_entry(tmp)
        il = next((c for c in checks if c['name'] == 'img_ledger'), {})
        exempt_works = (len(fig_rows) == 1 and fig_rows[0].get('cap_mm') == 200.0
                        and fig_rows[0].get('mm', 0) > 140)
        normal_enforced = bool(normal) and all(r.get('cap_mm') == 140.0 and r.get('mm', 0) <= 140.0
                                               for r in normal)
        ledger_ok = led.get('action') == 'fullpage' and led.get('confirmed') is True
        ok_all = (ok and has_fp and exempt_works and normal_enforced and ledger_ok
                  and il.get('pass') is True)
        return ok_all, (f'pass={ok} figpage_tag={has_fp} fig_mm={fig_rows and fig_rows[0].get("mm")} '
                        f'fig_cap={fig_rows and fig_rows[0].get("cap_mm")} normal_pages={len(normal)} '
                        f'ledger_action={led.get("action")} img_ledger={il.get("pass")}')
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_imgredraw_ocr():
    """imgredraw 两条路：缺 rapidocr → exit 2 + 傻瓜式安装指引（降级验收硬要求）；
    装了 → 真跑 RapidTable 表格重绘，产物落 redraw/ 且台账置 redrawn+confirmed=false。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 'images').mkdir()
        make_table_png(tmp / 'images' / 'img_001.png')
        rc, out, err = run([sys.executable, str(IMGREDRAW), '--img', 'images/img_001.png',
                            '--kind', 'table', '--task', str(tmp)], timeout=600)
        if importlib.util.find_spec('rapidocr') is None:
            blob = (out or '') + (err or '')
            ok = rc == 2 and 'pip install' in blob and 'rapidocr' in blob
            return ok, f'skip: rapidocr not installed; degrade rc={rc} guide={"pip install" in blob}'
        if importlib.util.find_spec('PIL') is None:
            return True, 'skip: no PIL，造不出带文字的表格样图（stdlib 兜底图无字，RapidTable 无文本可填）'
        md = tmp / 'redraw' / 'img_001.md'
        e = _ledger_entry(tmp)
        ok = (rc == 0 and md.exists() and '|' in md.read_text(encoding='utf-8')
              and e.get('action') == 'redrawn' and e.get('confirmed') is False)
        return ok, f'rc={rc} redraw_md={md.exists()} ledger_action={e.get("action")}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_imgredraw_text():
    """--kind text 整页文字重绘：无 rapidocr → exit 2 + 安装指引；
    有 → redraw/img_NNN.txt 带容错纪律注释头、正文行非空，台账置 redrawn+confirmed=false。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 'images').mkdir()
        has_img = make_text_png(tmp / 'images' / 'img_001.png')
        if not has_img:
            return True, 'skip: no PIL，造不出文字样图'
        rc, out, err = run([sys.executable, str(IMGREDRAW), '--img', 'images/img_001.png',
                            '--kind', 'text', '--task', str(tmp)], timeout=600)
        if importlib.util.find_spec('rapidocr') is None:
            blob = (out or '') + (err or '')
            ok = rc == 2 and 'pip install' in blob and 'rapidocr' in blob
            return ok, f'skip: rapidocr not installed; degrade rc={rc} guide={"pip install" in blob}'
        txt = tmp / 'redraw' / 'img_001.txt'
        if rc != 0 or not txt.exists():
            return False, f'rc={rc} txt_exists={txt.exists()} err={(err or "")[:120]}'
        content = txt.read_text(encoding='utf-8')
        body = [l for l in content.splitlines() if l.strip() and not l.startswith('#')]
        e = _ledger_entry(tmp)
        ok = (bool(body) and '待确认' in content
              and e.get('action') == 'redrawn' and e.get('confirmed') is False)
        return ok, f'rc={rc} body_lines={len(body)} ledger_action={e.get("action")}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_md_marks_colored():
    """md 路径注入的 {} 标注必须真的上色。
    旧缺陷：para_html 从不调用 tint 的 injected 分支 → 纸上 27 处符号与正文同色（标注隐形）。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 'm.json').write_text(json.dumps({'concept': ['自回归解码']}, ensure_ascii=False),
                                    encoding='utf-8')
        (tmp / 't.md').write_text(
            '# 标注上色\n\n自回归解码是主线。第二处自回归解码不该重复注入。\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md', '--marks', str(tmp / 'm.json')])
        ok, _ = check_report(tmp)
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace')
        colored = 'class="concept"' in html
        return ok and colored, f'pass={ok} colored={colored}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_prose_tint_entry():
    """散文/转写路径：原文自带的「」（）要上色，--entry 注入的【】要走 .entry-i（行内加粗）。
    .entry 带 display:block，会把句子劈成两行，而散文页高按 .line 计数——硬半页会静默失守。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 't.txt').write_text(
            '第一章 开篇。这里有一句「原话」，还有一个（注释）。第二章 收尾也一样。\n',
            encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.txt'),
                            '--dir', str(tmp), '--entry', r'第[一二三四五六七八九十]+章'])
        ok, _ = check_report(tmp)
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace')
        has = {k: (f'class="{k}"' in html) for k in ('per', 'paren', 'entry-i')}
        return ok and has['per'] and has['paren'] and has['entry-i'], f'pass={ok} {has}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_prose_no_zero_mm():
    """散文模式不经浏览器量高，span 天生是 0.0：此时不许落 data-mm 戳。
    盖上 0.0 会让机检以为「有实测值」，把整页算成 0mm 通过——硬半页闸被悄悄关掉。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        (tmp / 't.txt').write_text('散文第一句要能读。第二句继续验证分页。第三句收尾。\n' * 6,
                                   encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.txt'), '--dir', str(tmp)])
        ok, checks = check_report(tmp)
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace')
        zero = 'data-mm="0.0"' in html
        pf = next((c for c in checks if c['name'] == 'page_fill'), {})
        return ok and not zero and pf.get('estimated') is True, \
            f'pass={ok} zero_stamps={zero} estimated={pf.get("estimated")} peak_mm={pf.get("peak_mm")}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_measure_base_invariant():
    """量高必须与「前面有没有大上边距的兄弟」无关。

    2026-10-06 双语精读册实测：MEASURE_JS 写成 `next.top - base - r.top`，多减了容器
    顶边 base；而 base 会被首块塌陷出去的上边距推离视口顶（h2 的 1.6em ≈ 8.5mm），
    于是每一块都被少算 8.5mm。一页十几块累计 1.5~1.8 倍：屏幕报 peak=138.8mm 合规，
    纸上墨点到 244.6mm 压进写区，闭环收到 104mm 下限仍收不回来。"""
    spec = importlib.util.spec_from_file_location('ts_base', TYPESET)
    ts = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ts)
    css = (ROOT / 'templates' / 'page.css').read_text(encoding='utf-8')

    def para(i):
        return (f'<div class="para l1"><span class="line">第{i}段内容甲乙丙丁戊己庚辛</span>'
                f'<span class="line">第{i}段内容壬癸子丑寅卯辰巳</span></div>')

    ps = [para(i) for i in range(4)]
    with tempfile.TemporaryDirectory() as td:
        a = ts.measure(ps, css, tag='裸段落', workdir=Path(td))
        b = ts.measure(['<h2>带大上边距的标题</h2>'] + ps, css, tag='前置 h2', workdir=Path(td))[1:]
    dmax = max(abs(x - y) for x, y in zip(a, b))
    return dmax < 0.6, f'最大漂移={dmax:.2f}mm（阈值 0.6）'


def test_long_para_split_no_loss():
    """超长段落被 split_oversized 拆块时一个字不许丢。
    旧写法用非贪婪 findall 取 .line，会在行内第一个语义单元的 </span> 就停，
    取回半截行（实测一份文档丢 3287 字），拼回去浏览器还会整体错位。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        body = ''.join(f'第七{i}条要把自回归解码讲清楚才行。' for i in range(60))
        (tmp / 't.md').write_text('# 拆块不丢字\n\n' + body + '\n', encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md'])
        ok, checks = check_report(tmp)
        cons = next((c for c in checks if c['name'] == 'char_conservation'), {})
        lines = len(re.findall(r'<span class="line["\s>]',
                               (tmp / '排版.html').read_text(encoding='utf-8', errors='replace')))
        return ok and cons.get('missing') == 0 and cons.get('added') == 0, \
            f'pass={ok} missing={cons.get("missing")} added={cons.get("added")} lines={lines}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_epub2md():
    """epub 输入适配器回归：纯 Python 造最小合法 epub → epub2md.py → md 非空、标题与图在、
    引用图片落盘 → typeset --md --render 机检全绿。"""
    pandoc = shutil.which('pandoc')
    if not pandoc:
        return False, 'pandoc not found'
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        make_png(tmp / 'cover.png', 900, 500)
        img_bytes = (tmp / 'cover.png').read_bytes()
        make_epub(tmp / 'book.epub', title='epub回归', chapter_title='测试章',
                  image_bytes=img_bytes)
        md = tmp / 'out.md'
        rc, out, err = run([sys.executable, str(HERE / 'epub2md.py'),
                            '--in', str(tmp / 'book.epub'), '--out', str(md)],
                           cwd=str(tmp))
        if rc != 0:
            return False, f'epub2md rc={rc} err={err[:200]}'
        if not md.exists() or md.stat().st_size == 0:
            return False, 'md empty'
        md_text = md.read_text(encoding='utf-8', errors='replace')
        if '测试章' not in md_text:
            return False, 'chapter title missing in md'
        media_dir = md.parent / 'media'
        media_files = list(media_dir.rglob('*')) if media_dir.exists() else []
        if not media_files:
            return False, 'no media extracted'
        # typeset 端到端
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(md),
                            '--dir', str(tmp), '--md', '--render'])
        ok, _ = check_report(tmp)
        return ok, f'epub2md_ok=True typeset_pass={ok}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_sync_checksums():
    """三区一致性：X 区（改稿处）= S 区（kimi 安装）= Q 区（Qoder 生效）。
    只拷一份 SKILL.md 过去会让 REFERENCE.md / tone.md 静默断链，所以逐文件比字节，
    并查行尾——宿主里被改成 CRLF 会让「同一份引擎」其实不是同一份字节。"""
    installed = [Path(p) for p in (
        'C:/Users/Lenovo/.kimi-code/skills/paiban-yang-028',      # S 区
        'C:/Users/Lenovo/.qoder-cn/skills/paiban-yang-028',       # Q 区
    )]
    files = [
        'scripts/typeset.py', 'scripts/check.py', 'scripts/t1_audit.py',
        'scripts/render.py', 'scripts/gate.py', 'scripts/asr.py',
        'scripts/selftest.py', 'scripts/longdoc.py', 'scripts/epub2md.py',
        'scripts/imgdiag.py', 'scripts/imgredraw.py',
        'templates/page.css', 'SKILL.md', 'REFERENCE.md', 'tone.md',
        'requirements.txt', 'requirements-asr.txt', 'requirements-img.txt',
    ]
    mismatches, crlf_files = [], []
    for root in installed:
        zone = 'S' if '.kimi-code' in str(root) else 'Q'
        if not root.exists():
            mismatches.append(f'{zone}: not found')
            continue
        for f in files:
            src, dst = ROOT / f, root / f
            if not dst.exists():
                mismatches.append(f'{f}@{zone}: missing')
                continue
            data = dst.read_bytes()
            if src.read_bytes() != data:
                mismatches.append(f'{f}@{zone}')
            if b'\r\n' in data:
                crlf_files.append(f'{f}@{zone}')
    ok = not mismatches and not crlf_files
    return ok, f'mismatches={mismatches} crlf={crlf_files}'


def _load_check():
    spec = importlib.util.spec_from_file_location('paiban_selftest_check', str(CHECK))
    ck = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ck)
    return ck


def test_dash_no_split():
    """中文破折号「——」不许被劈成两行。
    ATOM_RE 末位是 `|.`，两个 — 各成一个原子，行宽一满刀口就落在中间。
    SDD 课件 17 份实测：531 对「——」里 345 处被劈（65%），纸面变成
    「上行以 — 收尾 / 下行以 — 开头」。修法=把 `—{2,}` 收成不可拆原子，整对挪到下一行。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        body = ''.join(f'第{i}节讲规范与实现的关系——这就是为什么要先写Spec文档。'
                       for i in range(40))
        (tmp / 't.md').write_text('# 破折号不劈行\n\n' + body + '\n', encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md'])
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace')
        ck = _load_check()
        # extract_lines 返回的是**含嵌套标签的行内 HTML**（它按深度取整行，不走非贪婪正则），
        # 数破折号前必须先脱标签，否则「——」被 </span><span> 隔开，恒等于 0。
        lines = [ck.strip_tags(l) for l in ck.extract_lines(html)]
        src_pairs = body.count('——')
        kept = sum(l.count('——') for l in lines)
        split = sum(1 for a, b in zip(lines, lines[1:])
                    if a.endswith('—') and b.lstrip().startswith('—') and not a.endswith('——'))
        return kept == src_pairs and split == 0, \
            f'源{src_pairs}对 纸面完整{kept} 劈行{split} 行数{len(lines)}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_han_cap_gate():
    """内容闸「每行 ≤36 汉字当量」必须在生成端就守住，且与机检同一把尺子。

    历史坑（2026-09-21 记为未修，2026-10-01 在《高性价比人生指南》41 件里撞爆 21 件）：
    `split_line` 的内容闸吃 `_w`（KEEP_RE 只数汉字/字母/数字，全角标点·空格·%一律不计），
    机检第 5 项吃 `check.em_units`（East Asian Width，W/F/A 记 1、其余记 0.5）。
    实测红行「北京市卫生健康委员会 2019 北京市加强急诊预检分」=36.5 当量：
    生成端数到 35 字判合规，机检按当量数到 36.5 判红 → 整件出不了片。
    修法＝生成端改吃 em_units（与 `paginate()` 那次同一课：**与机检同式记账**），
    `_glue` 并原子时两条闸一起判（并进来的原子不可再拆，超了只能判红）。"""
    tmp = Path(tempfile.mkdtemp(prefix='paiban_self_'))
    try:
        body = ('来源：北京市卫生健康委员会 2019 北京市加强急诊预检分诊工作的实施方案 通知\n\n'
                + ''.join(f'国卫医发 2019 第 {i} 号条款要求 95% CI 0.50 到 0.68，按 12% 折算。\n'
                          for i in range(40)))
        (tmp / 't.md').write_text('# 当量闸\n\n' + body, encoding='utf-8')
        rc, out, err = run([sys.executable, str(TYPESET), '--in', str(tmp / 't.md'),
                            '--dir', str(tmp), '--md'])
        html = (tmp / '排版.html').read_text(encoding='utf-8', errors='replace')
        ck = _load_check()
        lines = [ck.strip_tags(l) for l in ck.extract_lines(html)]
        peak = max([round(ck.em_units(re.sub(r'[\x00\x01]', '', l)), 1) for l in lines] or [0])
        ok, checks = check_report(tmp)
        ll = next((c for c in checks if c['name'] == 'line_length'), {})
        return ok and peak <= 36 and ll.get('pass'), \
            f'行数={len(lines)} 峰值当量={peak}(闸36) line_length={ll.get("pass")} 整体={ok}'
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_code_monospace():
    """代码块必须真的等宽——这条专防「选择器命不中产物类名」。
    历史坑：page.css 只写 `pre, code { font-family: Consolas }`，而 typeset 产出的是
    <div class="code-block"><span class="code-line">，既不是 <pre> 也不是 <code>。
    2026-09-27 实测《Claude Code实战》第 5/6/8/9 章成品 PDF：Consolas 出现 0 次，
    规范「代码：等宽呈现」这条一直没落地。"""
    css = (ROOT / 'templates' / 'page.css').read_text(encoding='utf-8', errors='replace')
    css = re.sub(r'/\*.*?\*/', ' ', css, flags=re.S)      # 注释里也出现类名，先剥掉
    mono = [s.strip() for s, body in re.findall(r'([^{}]+)\{([^{}]*)\}', css)
            if 'font-family' in body and 'monospace' in body]
    ts = (HERE / 'typeset.py').read_text(encoding='utf-8', errors='replace')
    emits = 'class="code-block"' in ts
    covered = any('code-block' in s for s in mono)
    return (not emits) or covered, \
        f'等宽选择器={mono} 产物含.code-block={emits} 命中={covered}'


def test_longdoc_split_no_loss():
    """长件切章不许静默丢块。

    2026-10-06 排《视觉思维精读册》抓到两处：
      1) `len(sub) > max_chars` 之外的 h2 子块没有 append ⇒ 整章被丢，切章对账报 0；
      2) 切点从第一个标题起算 ⇒ 首个标题之前的封面/引言被跳过。
    判据＝各章拼回去与原文逐字相同（忽略空白），既不许少也不许多。
    """
    spec = importlib.util.spec_from_file_location('ld_selftest', HERE / 'longdoc.py')
    ld = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(ld)
    big_h3 = '\n\n'.join(f'### 小节{i}\n\n' + ('内容' * 200) for i in range(6))
    md = ('# 书名\n\n封面语：一句话。\n\n'
          '## 第一章\n\n' + ('甲' * 300) + '\n\n' + big_h3 + '\n\n'
          '## 第二章\n\n' + ('乙' * 120) + '\n')
    chunks = ld.split_md(md, 1000)
    joined = re.sub(r'\s+', '', ''.join(chunks))
    orig = re.sub(r'\s+', '', md)
    head_kept = any('封面语' in c for c in chunks)
    return (joined == orig and head_kept), \
        f'chunks={len(chunks)} 封面留存={head_kept} 拼回{"==" if joined == orig else "!="}原文'


def main():
    tests = [
        ('md+image', test_md_with_image),
        ('md-no-image', test_md_no_image),
        ('prose', test_prose),
        ('missing-image', test_missing_image),
        ('t1-audit-image', test_t1_audit_image),
        ('gate', test_gate),
        ('marks-skip-code', test_marks_skip_code),
        ('long-code-atom', test_long_code_atom),
        ('caption-merge', test_caption_merge),
        ('fig-page-measured', test_fig_page_measured),
        ('imgdiag-table', test_imgdiag_table),
        ('imgdiag-photo', test_imgdiag_photo),
        ('img-ledger-missing', test_img_ledger_missing),
        ('img-ledger-unconfirmed', test_img_ledger_unconfirmed),
        ('figpage-exempt', test_figpage_exempt),
        ('imgredraw-ocr', test_imgredraw_ocr),
        ('imgredraw-text', test_imgredraw_text),
        ('md-marks-colored', test_md_marks_colored),
        ('prose-tint-entry', test_prose_tint_entry),
        ('prose-no-zero-mm', test_prose_no_zero_mm),
        ('long-para-no-loss', test_long_para_split_no_loss),
        ('measure-base-invariant', test_measure_base_invariant),
        ('longdoc-split-no-loss', test_longdoc_split_no_loss),
        ('dash-no-split', test_dash_no_split),
        ('han-cap-gate', test_han_cap_gate),
        ('code-monospace', test_code_monospace),
        ('epub2md', test_epub2md),
        ('sync-checksums', test_sync_checksums),
    ]
    fails = []
    for name, fn in tests:
        try:
            ok, detail = fn()
        except Exception as e:
            ok, detail = False, f'exception: {e}'
        flag = 'OK ' if ok else 'FAIL'
        print(f'[{flag}] {name}: {detail}')
        if not ok:
            fails.append(name)
    total = len(tests)
    passed = total - len(fails)
    if fails:
        print(f'[selftest] FAIL {passed}/{total}: {fails}')
        return 1
    print(f'[selftest] PASS {passed}/{total}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
