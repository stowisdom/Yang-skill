#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ledger.py — codeloop 巡检台账：巡检记忆的存取引擎。

条目三型：
  〔发现〕巡检产出，带生命周期：待处理 → 仍在 → 已消（sight/resolve 更新）
  〔坑〕确认过的坑，供人和 agent 检索
  〔约定〕巡检规则库（现场该长什么样），P4 逐条验
只增不删；〔发现〕状态可更新。

子命令：
  init    --project DIR                       首巡初始化 codeloop/
  add     --project DIR --type T --title T --detail D [--evidence E] [--tag a,b] [--files f1,f2]
  sight   --project DIR --id L00X             巡检又见到：仍在，刷新 last_seen
  resolve --project DIR --id L00X [--note N]  消失了：已消
  query   --project DIR "关键词" [--type T] [--limit N] [--open]  只看未消发现加 --open
  show    --project DIR [--last N]
  render  --project DIR                       由 JSONL 重渲染 工程台账.md

仅用标准库。所有输出 JSON（ensure_ascii=False）。
"""
import argparse
import datetime
import json
import os
import sys

TYPES = ('发现', '坑', '约定')
TYPE_ORDER = {'发现': 1, '坑': 2, '约定': 3}
STATUS_OPEN = ('待处理', '仍在')


def now():
    return datetime.datetime.now().strftime('%Y-%m-%d %H:%M')


def paths(project):
    cld = os.path.join(project, 'codeloop')
    return cld, os.path.join(cld, 'ledger.jsonl'), os.path.join(cld, '工程台账.md')


def load(jl):
    if not os.path.exists(jl):
        return []
    with open(jl, encoding='utf-8') as f:
        return [json.loads(line) for line in f if line.strip()]


def save_all(jl, entries):
    with open(jl, 'w', encoding='utf-8') as f:
        for e in entries:
            f.write(json.dumps(e, ensure_ascii=False) + '\n')


def render(project):
    cld, jl, md = paths(project)
    entries = load(jl)
    lines = ['# 工程台账（巡检记忆）', '',
             '> codeloop 巡检产出。只增不删；本文件由 render 生成，手改会被覆盖——要改用 add/resolve。', '']
    if not entries:
        lines.append('（空——还没巡过）')
    groups = [(t, [e for e in entries if e['type'] == t]) for t in TYPES]
    others = [e for e in entries if e['type'] not in TYPES]
    if others:
        groups.append(('其他（历史条目）', others))
    for t, group in groups:
        if not group:
            continue
        lines.append('## 〔%s〕%d 条' % (t, len(group)))
        lines.append('')
        for e in reversed(group):  # 新的在前
            badge = ''
            if t == '发现':
                badge = ' · 状态：%s' % e.get('status', '?')
                if e.get('last_seen') and e.get('last_seen') != e.get('first_seen'):
                    badge += '（首见 %s，近见 %s）' % (e.get('first_seen', '?'), e['last_seen'])
            lines.append('- **%s %s** · %s%s%s' % (
                e['id'], e['title'], e['ts'], badge,
                (' · `' + '`,`'.join(e['tags']) + '`') if e.get('tags') else ''))
            lines.append('  ' + e['detail'].replace('\n', '\n  '))
            if e.get('evidence'):
                lines.append('  证据：`%s`' % e['evidence'])
            if e.get('files'):
                lines.append('  涉及：`%s`' % '`,`'.join(e['files']))
        lines.append('')
    os.makedirs(cld, exist_ok=True)
    with open(md, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')


def get_project(args):
    return os.path.abspath(args.project)


def cmd_init(args):
    project = get_project(args)
    cld, jl, md = paths(project)
    os.makedirs(os.path.join(cld, '巡检报告'), exist_ok=True)
    if not os.path.exists(jl):
        open(jl, 'a', encoding='utf-8').close()
    render(project)
    print(json.dumps({'ok': True, 'codeloop_dir': cld, 'ledger': jl,
                      'ledger_md': md, 'report_dir': os.path.join(cld, '巡检报告')},
                     ensure_ascii=False, indent=2))


def cmd_add(args):
    if args.type not in TYPES:
        print(json.dumps({'ok': False, 'error': 'type 必须是 %s 之一' % '/'.join(TYPES)},
                         ensure_ascii=False))
        sys.exit(2)
    project = get_project(args)
    cld, jl, md = paths(project)
    if not os.path.exists(jl):
        print(json.dumps({'ok': False, 'error': 'codeloop 未初始化，先跑 init'}, ensure_ascii=False))
        sys.exit(2)
    entries = load(jl)
    ts = now()
    entry = {
        'id': 'L%03d' % (len(entries) + 1),
        'ts': ts,
        'type': args.type,
        'title': args.title,
        'detail': args.detail,
        'tags': [t.strip() for t in args.tag.split(',') if t.strip()] if args.tag else [],
        'files': [f.strip() for f in args.files.split(',') if f.strip()] if args.files else [],
    }
    if args.evidence:
        entry['evidence'] = args.evidence
    if args.type == '发现':
        entry.update({'status': '待处理', 'first_seen': ts, 'last_seen': ts})
    entries.append(entry)
    save_all(jl, entries)
    render(project)
    print(json.dumps({'ok': True, 'entry': entry}, ensure_ascii=False, indent=2))


def _find(entries, eid):
    for i, e in enumerate(entries):
        if e['id'] == eid:
            return i
    return -1


def cmd_sight(args):
    project = get_project(args)
    cld, jl, md = paths(project)
    entries = load(jl)
    i = _find(entries, args.id)
    if i < 0:
        print(json.dumps({'ok': False, 'error': '找不到 %s' % args.id}, ensure_ascii=False))
        sys.exit(2)
    e = entries[i]
    if e['type'] != '发现':
        print(json.dumps({'ok': False, 'error': '%s 不是〔发现〕，sight 只用于发现' % args.id},
                         ensure_ascii=False))
        sys.exit(2)
    e['status'] = '仍在'
    e['last_seen'] = now()
    save_all(jl, entries)
    render(project)
    print(json.dumps({'ok': True, 'entry': e}, ensure_ascii=False, indent=2))


def cmd_resolve(args):
    project = get_project(args)
    cld, jl, md = paths(project)
    entries = load(jl)
    i = _find(entries, args.id)
    if i < 0:
        print(json.dumps({'ok': False, 'error': '找不到 %s' % args.id}, ensure_ascii=False))
        sys.exit(2)
    e = entries[i]
    if e['type'] != '发现':
        print(json.dumps({'ok': False, 'error': '%s 不是〔发现〕，resolve 只用于发现' % args.id},
                         ensure_ascii=False))
        sys.exit(2)
    e['status'] = '已消'
    e['last_seen'] = now()
    if args.note:
        e['detail'] += ' ｜已消备注：' + args.note
    save_all(jl, entries)
    render(project)
    print(json.dumps({'ok': True, 'entry': e}, ensure_ascii=False, indent=2))


def cmd_query(args):
    project = get_project(args)
    cld, jl, md = paths(project)
    entries = load(jl)
    if args.type:
        entries = [e for e in entries if e['type'] == args.type]
    if args.open:
        entries = [e for e in entries if e.get('status') in STATUS_OPEN]
    kws = []
    for chunk in args.keywords:
        kws.extend(k for k in chunk.replace('，', ' ').replace(',', ' ').split() if k)
    scored = []
    for e in entries:
        hay = e['title'] + ' ' + e['detail'] + ' ' + ' '.join(e.get('tags', []))
        score = sum(1 for k in kws if k in hay)
        if score > 0:
            scored.append((score, e))
    scored.sort(key=lambda x: -x[0])
    hits = [e for _, e in scored[:args.limit]]
    print(json.dumps({'ok': True, 'total': len(entries), 'hits': len(hits),
                      'entries': hits}, ensure_ascii=False, indent=2))


def cmd_show(args):
    project = get_project(args)
    cld, jl, md = paths(project)
    entries = load(jl)
    tail = entries[-args.last:] if args.last else entries
    print(json.dumps({'ok': True, 'total': len(entries), 'entries': tail},
                     ensure_ascii=False, indent=2))


def cmd_render(args):
    render(get_project(args))
    print(json.dumps({'ok': True, 'msg': '工程台账.md 已按 ledger.jsonl 重渲染'}, ensure_ascii=False))


def main():
    ap = argparse.ArgumentParser(description='codeloop 巡检台账')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('init'); p.add_argument('--project', default='.'); p.set_defaults(func=cmd_init)

    p = sub.add_parser('add'); p.add_argument('--project', default='.')
    p.add_argument('--type', required=True); p.add_argument('--title', required=True)
    p.add_argument('--detail', required=True); p.add_argument('--evidence', default='')
    p.add_argument('--tag', default=''); p.add_argument('--files', default='')
    p.set_defaults(func=cmd_add)

    p = sub.add_parser('sight'); p.add_argument('--project', default='.')
    p.add_argument('--id', required=True); p.set_defaults(func=cmd_sight)

    p = sub.add_parser('resolve'); p.add_argument('--project', default='.')
    p.add_argument('--id', required=True); p.add_argument('--note', default='')
    p.set_defaults(func=cmd_resolve)

    p = sub.add_parser('query'); p.add_argument('--project', default='.')
    p.add_argument('keywords', nargs='+'); p.add_argument('--type', default=None)
    p.add_argument('--limit', type=int, default=5)
    p.add_argument('--open', action='store_true'); p.set_defaults(func=cmd_query)

    p = sub.add_parser('show'); p.add_argument('--project', default='.')
    p.add_argument('--last', type=int, default=5); p.set_defaults(func=cmd_show)

    p = sub.add_parser('render'); p.add_argument('--project', default='.'); p.set_defaults(func=cmd_render)

    args = ap.parse_args()
    args.func(args)


if __name__ == '__main__':
    main()
