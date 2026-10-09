#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""paiban-yang-028 音频适配器（T1 前置件）：音频批量 → 文字。

必须用 Python 3.12 跑（默认 3.14 无 faster-whisper wheel）：

    py -3.12 asr.py --audio a.m4a b.mp3 c.wav [--out-dir 输出目录] [--model small]
    py -3.12 asr.py --audio 某段.mp3 --truth 某段口播文本.txt      # 算 CER

批量：多份音频共用一次模型加载；每份输出 `<名>.转写.txt` 与 `<名>.segments.json`。

后端优先级：cuda/float16 → cpu/int8。GPU 需要 CUDA 12 运行时（nvidia-cublas-cu12），
本脚本会自动把已装 wheel 的 bin 目录挂进 DLL 搜索路径。

实测（2026-09-19）：small / CPU int8 → 2.96x 实时、中文 CER 8.0%（错误全为同音字替换）。
GPU 通不通、快多少，见 REFERENCE.md 的数字。
"""
import argparse, glob, json, os, sys, time

os.environ.setdefault('HF_ENDPOINT', 'https://hf-mirror.com')
os.environ.setdefault('HF_HUB_DISABLE_SYMLINKS_WARNING', '1')


_DLL_HANDLES = []   # 关键：add_dll_directory 的句柄必须常驻，被 GC 掉后该搜索目录立即失效


def add_cuda_dll_dirs():
    """把 pip 装的 CUDA 12 运行时 bin 目录加入 DLL 搜索路径（ctranslate2 找 cublas 用）。"""
    import site
    roots = []
    for base in list(site.getsitepackages()) + [os.path.join(sys.prefix, 'Lib', 'site-packages')]:
        roots.append(os.path.join(base, 'nvidia'))
    added = []
    for root in roots:
        if not os.path.isdir(root):
            continue
        for pkg in ('cublas', 'cuda_runtime', 'cudnn', 'cuda_nvrtc'):
            bindir = os.path.join(root, pkg, 'bin')
            if not os.path.isdir(bindir):
                continue
            try:
                _DLL_HANDLES.append(os.add_dll_directory(bindir))   # 句柄存住，别丢
                added.append(pkg)
            except Exception:
                added.append(pkg + '(failed)')
            os.environ['PATH'] = bindir + os.pathsep + os.environ.get('PATH', '')   # 双保险
    return added


def collect_audio(patterns):
    """先认实体文件，再认目录，最后才当通配。
    坑：本批文件名带方括号（如 `xx[防断更微]`），若把 `[` 当 glob 字符类会一个都匹配不上。"""
    out = []
    for p in patterns:
        if os.path.isfile(p):
            out.append(p)
        elif os.path.isdir(p):
            out += sorted(glob.glob(os.path.join(p, '*')))
        elif '*' in p or '?' in p:
            out += sorted(glob.glob(p))
        else:
            print(f'[warn] not found: {p}'.encode('utf-8', 'replace').decode('utf-8', 'replace'))
    ext = {'.m4a', '.mp3', '.wav', '.aac', '.ogg', '.flac', '.wma', '.amr', '.mp4'}
    return [f for f in out if os.path.splitext(f)[1].lower() in ext]


def duration(path):
    try:
        import av
        c = av.open(path)
        return c.duration / av.time_base if c.duration else 0
    except Exception:
        return 0


def cer_of(truth_path, hyp):
    import re, unicodedata, difflib
    keep = re.compile(r'[一-鿿A-Za-z0-9]')
    n = lambda s: ''.join(keep.findall(unicodedata.normalize('NFKC', s)))
    t, h = n(open(truth_path, encoding='utf-8').read()), n(hyp)
    ref = t
    if len(t) > len(h) * 1.3:
        best, step = 0, max(1, len(h) // 40)
        for st in range(0, max(1, len(t) - len(h)), step):
            w = t[st:st + len(h)]
            r = difflib.SequenceMatcher(None, w, h).ratio()
            if r > best:
                best, ref = r, w
    sm = difflib.SequenceMatcher(None, ref, h)
    same = sum(b.size for b in sm.get_matching_blocks())
    return (1 - same / max(1, len(ref))), len(ref), same


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--audio', nargs='+', required=True, help='音频文件（可多个）或含音频的目录')
    ap.add_argument('--out-dir', default=None)
    ap.add_argument('--model', default='small')
    ap.add_argument('--lang', default='zh')
    ap.add_argument('--prompt', default=None,
                    help='initial_prompt：喂专有名词与简体用词，压住人名错与繁简混排（实测有效）')
    ap.add_argument('--prompt-file', default=None, help='从文件读 prompt（词表长时用这个）')
    ap.add_argument('--no-repeat', dest='no_repeat', type=int, default=4,
                    help='n-gram 复读抑制窗口，0=关；长课防复读幻觉用 4')
    ap.add_argument('--truth', default=None, help='单文件时给真值算 CER')
    a = ap.parse_args()

    prompt = a.prompt
    if a.prompt_file:
        prompt = open(a.prompt_file, encoding='utf-8').read().strip()
    if prompt:
        print(f'[prompt] {len(prompt)} chars attached')

    files = collect_audio(a.audio)
    if not files:
        print('[ERR] no audio files matched')
        return 2

    dlls = add_cuda_dll_dirs()
    print(f'[dll] cuda dirs attached: {", ".join(dlls) or "none"}')

    from faster_whisper import WhisperModel
    model, backend = None, None
    for dev, ct in (('cuda', 'float16'), ('cpu', 'int8')):
        try:
            model = WhisperModel(a.model, device=dev, compute_type=ct)
            backend, (dev_used, ct_used) = f'{dev}/{ct}', (dev, ct)
            break
        except Exception as e:
            print(f'[model] {dev}/{ct} unavailable: {type(e).__name__}: {str(e)[:90]}')
    if model is None:
        print('[ERR] no backend; run: py -3.12 -m pip install faster-whisper')
        return 2
    print(f'[model] {a.model} @ {backend} ready')

    outdir = a.out_dir or os.path.dirname(os.path.abspath(files[0]))
    os.makedirs(outdir, exist_ok=True)

    total_audio = total_wall = 0.0
    for i, f in enumerate(files, 1):
        t0 = time.time()
        dur = duration(f)
        # condition_on_previous_text=False + no_repeat_ngram_size：治 whisper 在长课里的复读幻觉
        # （实测第01课曾出现「复词呢」连八遍、「这只是一个误会」连六遍）
        segments, info = model.transcribe(f, language=a.lang, beam_size=5, vad_filter=True,
                                          initial_prompt=prompt,
                                          condition_on_previous_text=False,
                                          no_repeat_ngram_size=a.no_repeat,
                                          repetition_penalty=1.15,
                                          compression_ratio_threshold=2.2,
                                          log_prob_threshold=-1.0)
        segs = [{'start': round(s.start, 2), 'end': round(s.end, 2), 'text': s.text.strip()} for s in segments]
        wall = time.time() - t0
        hyp = '\n'.join(s['text'] for s in segs)
        stem = os.path.splitext(os.path.basename(f))[0]
        txt = os.path.join(outdir, stem + '.转写.txt')
        open(txt, 'w', encoding='utf-8').write(hyp + '\n')
        json.dump({'file': f, 'seconds': round(dur, 1), 'lang': info.language, 'segments': segs},
                  open(os.path.join(outdir, stem + '.segments.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        total_audio += dur
        total_wall += wall
        rtf = (dur / wall) if wall and dur else 0
        print(f'[{i}/{len(files)}] {stem[:28].encode("ascii","replace").decode("ascii")} '
              f'audio={dur:.0f}s wall={wall:.1f}s rtf={rtf:.2f}x chars={len(hyp)} -> {os.path.basename(txt)}')
        if a.truth and len(files) == 1:
            e, ref, ok = cer_of(a.truth, hyp)
            print(f'   [CER] {e*100:.1f}%  ref={ref} ok={ok}')

    print(f'[SUM] files={len(files)} audio={total_audio/60:.1f}min wall={total_wall/60:.1f}min '
          f'rtf={(total_audio/total_wall if total_wall else 0):.2f}x backend={backend}')
    print(f'[out] {outdir}')
    return 0


if __name__ == '__main__':
    sys.exit(main())
