#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""verify.py — codeloop 的机器判据。

自动探测项目栈 → 跑编译命令与测试命令 → 输出 JSON verdict。

verdict 取值：
  pass          编译过 + 测试过（全绿，H3 可过闸）
  pass-notests  编译过 + 无测试（触发降级：黑盒不变量抽查单）
  fail          编译或测试有红（回施工步，禁止带病过闸）
  unknown-stack 没认出的栈（停下问用户）

退出码：0=pass/pass-notests；1=fail；3=unknown-stack。仅用标准库。
"""
import argparse
import json
import os
import re
import subprocess
import sys

BUILD_TIMEOUT = 300   # 秒
TEST_TIMEOUT = 600    # 秒
LOG_TAIL = 4000       # 日志截尾字符数


def detect(project):
    """返回 (stack_name, build_cmd|None, test_cmd|None)。"""
    p = lambda *a: os.path.join(project, *a)

    if os.path.exists(p('package.json')):
        try:
            with open(p('package.json'), encoding='utf-8') as f:
                pkg = json.load(f)
        except Exception:
            pkg = {}
        scripts = pkg.get('scripts') or {}
        build = 'npm run build' if 'build' in scripts else None
        t = (scripts.get('test') or '').strip()
        is_placeholder = t in ('', 'echo "Error: no test specified" && exit 1')
        test = None if is_placeholder else 'npm test'
        return 'node', build, test

    py_markers = ('pyproject.toml', 'setup.py', 'requirements.txt')
    if any(os.path.exists(p(m)) for m in py_markers):
        cfg = ''
        for m in py_markers:
            if os.path.exists(p(m)):
                try:
                    with open(p(m), encoding='utf-8', errors='replace') as f:
                        cfg += f.read()
                except Exception:
                    pass
        has_pytest = 'pytest' in cfg
        has_test_files = False
        if os.path.isdir(p('tests')):
            has_test_files = any(n.startswith('test_') and n.endswith('.py')
                                 for n in os.listdir(p('tests')))
        else:
            try:
                has_test_files = any(n.startswith('test_') and n.endswith('.py')
                                     for n in os.listdir(project))
            except OSError:
                pass
        test = '"%s" -m pytest' % sys.executable if (has_pytest or has_test_files) else None
        return 'python', None, test

    if os.path.exists(p('go.mod')):
        return 'go', 'go build ./...', 'go test ./...'
    if os.path.exists(p('Cargo.toml')):
        return 'rust', 'cargo build', 'cargo test'
    if os.path.exists(p('pom.xml')):
        return 'maven', 'mvn -q -DskipTests compile', 'mvn -q test'
    if os.path.exists(p('build.gradle')) or os.path.exists(p('build.gradle.kts')):
        return 'gradle', 'gradle build -x test', 'gradle test'
    if os.path.exists(p('Makefile')):
        try:
            with open(p('Makefile'), encoding='utf-8', errors='replace') as f:
                mk = f.read()
        except Exception:
            mk = ''
        build = 'make build' if re.search(r'^build\s*:', mk, re.M) else None
        test = 'make test' if re.search(r'^test\s*:', mk, re.M) else None
        return 'make', build, test
    return 'unknown', None, None


def run_cmd(cmd, cwd, timeout):
    """跑一条命令，返回 (status, log_tail)。status: pass/fail/skip/timeout。"""
    if not cmd:
        return 'skip', ''
    try:
        r = subprocess.run(cmd, cwd=cwd, shell=True, capture_output=True,
                           text=True, encoding='utf-8', errors='replace',
                           timeout=timeout)
    except subprocess.TimeoutExpired:
        return 'timeout', ('[超时] %ds： %s' % (timeout, cmd))
    out = ((r.stdout or '') + '\n' + (r.stderr or '')).strip()
    return ('pass' if r.returncode == 0 else 'fail'), out[-LOG_TAIL:]


def main():
    ap = argparse.ArgumentParser(description='codeloop verify：编译+测试的机器判据')
    ap.add_argument('--project', default='.', help='项目根目录')
    args = ap.parse_args()
    project = os.path.abspath(args.project)

    if not os.path.isdir(project):
        print(json.dumps({'verdict': 'fail', 'error': '项目目录不存在: %s' % project},
                         ensure_ascii=False))
        sys.exit(2)

    stack, build_cmd, test_cmd = detect(project)
    if stack == 'unknown':
        print(json.dumps({'verdict': 'unknown-stack', 'stack': 'unknown',
                          'hint': '未认出的栈，停下问用户：本项目怎么编译、怎么跑测试'},
                         ensure_ascii=False))
        sys.exit(3)

    b_status, b_log = run_cmd(build_cmd, project, BUILD_TIMEOUT)
    t_status, t_log = run_cmd(test_cmd, project, TEST_TIMEOUT)

    red = lambda s: s in ('fail', 'timeout')
    if red(b_status) or red(t_status):
        verdict = 'fail'
    elif t_status == 'pass':
        verdict = 'pass'
    else:  # 测试 skip 或 none，编译 pass/skip
        verdict = 'pass-notests'

    result = {
        'verdict': verdict,
        'stack': stack,
        'build': {'cmd': build_cmd, 'status': b_status, 'log_tail': b_log},
        'test': {'cmd': test_cmd, 'status': t_status, 'log_tail': t_log},
        'hint': {'pass': '全绿，H3 可过闸',
                 'pass-notests': '无测试降级：从评估标准生成黑盒不变量抽查单',
                 'fail': '有红，回施工步修，禁止带病过闸'}[verdict],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if verdict in ('pass', 'pass-notests') else 1)


if __name__ == '__main__':
    main()
