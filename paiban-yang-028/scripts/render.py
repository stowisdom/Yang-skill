#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 渲染器：排版.html → 排版.pdf（Chromium 系无头浏览器）。

用法：
    py -3.14 render.py --html 排版.html --pdf 排版.pdf [--css page.css]

约束：
    - 先有机检凭据再渲染（本脚本自身不查，交给 gate.py / 流程 T4；但会提示缺失）。
    - 中文路径下浏览器易出乱名 → 本脚本先在英文临时目录渲染，成功后再改名到目标。
    - 浏览器不是「存在即可用」：见 find_browser() 的实测探针。
      可用覆盖：环境变量 PAIBAN_BROWSER=绝对路径（跳过探针）。
stdout 全 ASCII。退出码 0=成功 2=失败。
"""
import argparse, glob, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

EDGE_CANDIDATES = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
]
CHROME_CANDIDATES = [
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
    r'C:\Program Files (x86)\Google\Chrome\Application\chrome.exe',
]
# Playwright 自带的独立无头内核：不共用用户配置，所以不受「桌面浏览器已开着」的劫持。
HEADLESS_SHELL_GLOBS = [
    str(Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) /
        'ms-playwright' / 'chromium_headless_shell-*' / 'chrome-headless-shell-*' / 'chrome-headless-shell.exe'),
    str(Path(os.environ.get('LOCALAPPDATA', str(Path.home()))) /
        'ms-playwright' / 'chromium-*' / 'chrome-win*' / 'chrome.exe'),
]

PROBE_HTML = ('<!doctype html><html><head><meta charset="utf-8"></head><body><pre id="p"></pre>'
              '<script>document.getElementById("p").textContent="PAIBAN_PROBE_OK";</script></body></html>')
_PROBED = {}         # 同一次运行内不重复探针（measure 每轮都调 find_browser）


def _probe(browser, tmp):
    """真跑一次 --dump-dom：只有吐回脚本写的标记才算可用。
    为什么必须探：桌面 Edge 正在运行时（帆开着浏览器），msedge.exe 的启动器会把调用
    交给已在跑的浏览器进程再立即退出——rc=0、stdout 空、PDF 也不生成，实测四种 flag 组合全中招。
    宁可选慢一点的独立无头内核，也不要一个「静默什么都不做」的浏览器。"""
    if browser in _PROBED:
        return _PROBED[browser]
    ok = False
    try:
        d = Path(tempfile.mkdtemp(prefix='paiban_probe_', dir=str(tmp)))
        (d / 'index.html').write_text(PROBE_HTML, encoding='utf-8')
        r = subprocess.run([browser, '--headless=new', '--disable-gpu', '--no-sandbox',
                            '--virtual-time-budget=5000', f'--user-data-dir={d / "profile"}',
                            '--dump-dom', (d / 'index.html').as_uri()],
                           capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=40)
        ok = 'PAIBAN_PROBE_OK' in (r.stdout or '')
        shutil.rmtree(d, ignore_errors=True)
    except (OSError, subprocess.SubprocessError):
        ok = False
    _PROBED[browser] = ok
    print(f"[browser] probe {'ok  ' if ok else 'FAIL'} {Path(browser).name} {Path(browser).parent}")
    return ok


def candidates():
    env = os.environ.get('PAIBAN_BROWSER')
    out = []
    if env:
        out.append(env)
    out += EDGE_CANDIDATES + CHROME_CANDIDATES
    for g in HEADLESS_SHELL_GLOBS:
        out += sorted(glob.glob(g))
    for name in ('msedge', 'chrome'):
        w = shutil.which(name)
        if w:
            out.append(w)
    seen, uniq = set(), []
    for p in out:
        if p and p not in seen and Path(p).exists():
            seen.add(p)
            uniq.append(p)
    return uniq


def find_browser(probe=True):
    """挑一个「实测能干活」的无头浏览器。探针不过一律不选。"""
    tmp = Path(tempfile.gettempdir())
    for b in candidates():
        if not probe or _probe(b, tmp):
            return b
    return None


def inline_css(html_text, css_path):
    if re.search(r'<link[^>]+rel=["\']stylesheet', html_text, re.I):
        return html_text
    css = Path(css_path).read_text(encoding='utf-8')
    style = f'<style>\n{css}\n</style>'
    if re.search(r'<head[^>]*>', html_text, re.I):
        return re.sub(r'(<head[^>]*>)', r'\1' + style, html_text, count=1, flags=re.I)
    return style + html_text


def page_count(pdf_bytes):
    return max(0, pdf_bytes.count(b'/Type /Page') - pdf_bytes.count(b'/Type /Pages'))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--html', required=True)
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--css', default=None)
    ap.add_argument('--budget', default='15000')
    a = ap.parse_args()

    src = Path(a.html)
    dst = Path(a.pdf)
    if not src.exists():
        print('[ERR] html missing:', str(src).encode('ascii', 'replace').decode('ascii'))
        return 2

    browser = find_browser()
    if not browser:
        print("[ERR] no working headless browser (probe failed on every candidate;"
              " set PAIBAN_BROWSER=<path to chrome.exe/chrome-headless-shell.exe>)")
        return 2

    # 机检凭据提示（不硬拦，硬拦是 gate.py 的活）
    jf = src.parent / '机检.json'
    if jf.exists():
        try:
            ok = json.loads(jf.read_text(encoding='utf-8')).get('pass')
            print(f'[gate] check-report pass={ok}')
        except Exception:
            print('[gate] check-report unreadable')
    else:
        print('[gate] WARN no check-report beside html (T4 skipped?)')

    raw = src.read_text(encoding='utf-8', errors='replace')
    css = a.css or str(Path(__file__).resolve().parent.parent / 'templates' / 'page.css')
    if Path(css).exists():
        raw = inline_css(raw, css)

    tmp = Path(tempfile.mkdtemp(prefix='paiban_'))
    work_html = tmp / 'index.html'          # 全英文路径，避开中文路径坑
    # 图资源：临时目录里相对 src（images/…）解析不到会裂图——副本里改写为绝对 file URI，
    # 原件保持相对路径不动（排版.html 可随 images/ 整体搬移，img_integrity 也按相对路径查）。
    def _abs_img(m):
        u = m.group(2)
        if re.match(r'^(?:https?|data|file):', u):
            return m.group(0)
        return m.group(1) + (src.parent / u).resolve().as_uri() + m.group(3)
    raw = re.sub(r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'])', _abs_img, raw)
    work_pdf = tmp / 'out.pdf'
    work_html.write_text(raw, encoding='utf-8')

    cmd = [browser, '--headless=new', '--disable-gpu', '--no-sandbox',
           '--no-pdf-header-footer', f'--virtual-time-budget={a.budget}',
           f'--user-data-dir={tmp / "profile"}',
           f'--print-to-pdf={work_pdf}', work_html.as_uri()]
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=180)

    ok = work_pdf.exists() and work_pdf.stat().st_size > 1200
    if ok:
        dst.parent.mkdir(parents=True, exist_ok=True)
        data = work_pdf.read_bytes()
        dst.write_bytes(data)
        print(f'[ok] pages={page_count(data)} size={len(data)} -> ' +
              dst.name.encode('ascii', 'replace').decode('ascii'))
    else:
        print('[ERR] render failed rc=%s' % r.returncode)
        print((r.stderr or '')[:300].encode('ascii', 'replace').decode('ascii'))

    shutil.rmtree(tmp, ignore_errors=True)
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
