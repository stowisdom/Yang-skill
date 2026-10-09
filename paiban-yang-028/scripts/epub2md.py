#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 · epub 输入适配器：epub → md + media/，只调 pandoc，不装 ebooklib/bs4。

边界（帆定）：
- 脚注 `[^1]` 原样进 md，typeset 不特殊处理，脚注文字会印成正文字符，可接受。
- epub 内嵌字体/样式丢弃，呈现层本来不归它管。
- 长书出来后接 `longdoc.py --split`。
- DRM 或解析失败 → 标〔不可排〕，不猜字。
"""
import argparse, re, shutil, subprocess, sys
from pathlib import Path


def count_md_imgs(md_text):
    """统计 md 里引用的图片路径数（独立行与行内都算）。"""
    return len(re.findall(r'!\[[^\]]*\]\(([^)]+)\)', md_text))


def extract_img_paths(md_text):
    return re.findall(r'!\[[^\]]*\]\(([^)]+)\)', md_text)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True, help='输入 epub 路径')
    ap.add_argument('--out', required=True, help='输出 md 路径')
    ap.add_argument('--media-dir', default=None, help='图片提取目录，默认 = out 同目录/media')
    a = ap.parse_args()

    src = Path(a.src)
    out = Path(a.out)
    if not src.exists():
        print(f'[epub2md] FAIL 输入不存在：{src}')
        return 2

    pandoc = shutil.which('pandoc')
    if not pandoc:
        print('[epub2md] FAIL 未找到 pandoc，请先安装 pandoc（https://pandoc.org）')
        return 2

    media_dir = Path(a.media_dir) if a.media_dir else (out.parent / 'media')
    media_dir.mkdir(parents=True, exist_ok=True)
    out.parent.mkdir(parents=True, exist_ok=True)

    cmd = [pandoc, '-f', 'epub', '-t', 'gfm', '--wrap=none',
           f'--extract-media={media_dir}', str(src), '-o', str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', errors='replace')
    if r.returncode != 0:
        err = (r.stderr or '')[:400]
        print(f'[epub2md] 〔不可排：DRM 或解析失败〕pandoc exit={r.returncode}')
        if err:
            print(f'  stderr: {err}')
        return 2

    if not out.exists() or out.stat().st_size == 0:
        print('[epub2md] 〔不可排：DRM 或解析失败〕pandoc 输出 0 字')
        return 2

    md_text = out.read_text(encoding='utf-8', errors='replace')
    n_chars = len(md_text)
    n_imgs = count_md_imgs(md_text)
    # 自检：md 里引用的图片是否都落盘（路径相对 md 文件所在目录）
    missing = []
    for p in extract_img_paths(md_text):
        if Path(p).is_absolute():
            continue
        if not (out.parent / p).exists():
            missing.append(p)
    if missing:
        print(f'[epub2md] WARN md 引用但 media/ 缺失：{missing[:5]}')

    n_media_files = len([x for x in media_dir.rglob('*') if x.is_file()])
    print(f'[epub2md] chars={n_chars} imgs={n_imgs}/{n_media_files} -> {out}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
