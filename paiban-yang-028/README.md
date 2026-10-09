# paiban-yang-028 重排版

一个 Kimi Code skill：把任意内容（URL / PDF / EPUB / Word / TXT / Markdown / 截图）**重排版**成适合打印的 A4 文档。

## 它做什么

目的只有两个：① 尽可能降低视觉的认知负荷；② 打印出来。

- **标注聚焦**：「」人物/作品 ｜ <>理论/方法 ｜ {}概念/术语 ｜ →因果 ｜ ⇨推进 ｜ ∵因为
- **语义分块**：按语义块用空格隔离，降低视觉负荷
- **半页留白**：上半页印内容（华文楷体），下半页整块空白供手写笔记
- **代码隔离**：等宽字体 + 底纹，与正文区分
- **公式渲染**：数学公式用 KaTeX 渲染
- **不改原文**：字词级语义守恒，机检执法——未过机检不出 PDF

## 触发方式

```
/paiban {路径 / URL / 粘贴文本}
```

## 目录结构

```
SKILL.md            技能主文件（触发规则、铁律、流程）
REFERENCE.md        详细参考（输入适配器、图片处理、公式处理等）
checklist.md        交付前自查清单
tone.md             语气规则
templates/page.css  页面样式
scripts/            机械层脚本
  ├── epub2md.py    EPUB 取文
  ├── asr.py        语音转文字
  ├── t1_audit.py   源文件 → 原文.txt 对账
  ├── typeset.py    切行排版
  ├── render.py     无头 Chromium 渲染 PDF
  ├── check.py      机检十项（字数守恒 / 行长 / 页高等）
  ├── imgdiag.py    图片分流
  └── imgredraw.py  OCR 重绘
assets/katex/       本地 KaTeX 资源
requirements*.txt   Python 依赖
```

## 安装

把整个目录放到 Kimi Code 的 skills 目录下即可，例如：

```
C:\Users\<你>\.kimi-code\skills\paiban-yang-028\
```

依赖安装：

```bash
pip install -r requirements.txt        # 基础
pip install -r requirements-asr.txt    # 语音转写（可选）
pip install -r requirements-img.txt    # 图片处理（可选）
```
