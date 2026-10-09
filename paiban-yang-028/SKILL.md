---
name: "paiban-yang-028"
description: "Task: Reformat content provided in the following file formats {url, pdf, epub, word, .txt, .md, .png 截图}. Strictly forbidden: adding, deleting, or altering the original content; missing pages or omitting content; display errors in symbols or text. Exception: obvious typos, homophone errors, or contextually inappropriate words/phrases (caused by speech-to-text conversion or OCR scanning of documents) may be adjusted to fit the overall context. 触发：/paiban 硬前缀，仅手动（disable-model-invocation 已锁）。Use when: /paiban 开头, 排版, 重排版, 版式, 生成 PDF 前的排版"
disable-model-invocation: true
---

# paiban-yang-028 重排版

def：{user-input} = 待重排版原件（/paiban 后接的路径 / URL / 粘贴文本 / 截图附件，正文以 `$ARGUMENTS` 接收）

# 重排版共识

## 以终为始
目的只有两个：① 尽可能降低视觉的认知负荷；② 打印出来。
介质前提：**A4 竖版（210×297mm）**——一切尺寸常数以此为锚，不做多纸张抽象。

## 重排版的定义（五段式）
1. **标注聚焦**：重点内容加符号——「」人物/作品 ｜ <>理论/方法 ｜ {}概念/术语 ｜ ()注释 ｜ →因果 ｜ ⇨推进 ｜ ∵因为。
2. **语义分块**：按语义块用空格隔离，降低视觉负荷。
3. **半页留白**：上半印内容（华文楷体），下半整块空白供手写。装不下就换页，不许压缩字号行距硬塞。
4. **代码隔离**：代码块用等宽字体（Consolas）+ 底纹，与正文楷体区分；行内代码用等宽字体。
5. **公式渲染**：数学公式/符号用 KaTeX 渲染，不作为纯文本处理。

## 禁令与例外
- 严禁：增删改原文内容；缺页漏页；符号、文字显示有误。
- 唯一例外：语音转文字 / OCR 产生的错别字、同音字、不合语境的词句，可调为符合语境——每条修改进 `纠字词表.json`，拿不准标〔待确认〕，不猜字。
- 语病、逻辑不顺、风格问题不动——那是 rbook / lbook 的活。

## 六条铁律（机检执法，不靠自觉）
1. **不改句**：基准 = `原文.txt`（T1 冻结）；判据 = 字词级语义守恒，纠字词表内替换合法。两道闸：`t1_audit.py` 管「源文件 → 原文.txt」，`check.py` 第 1 项管「原文.txt → 成品」。
2. **不混符号**：符号语义见上；层级只由缩进表达，`---` 只做同级硬断。
3. **不超密度**：正文每行 ≤36 汉字当量（ASCII 折半）且 ≤37.8em 物理宽；同段标注 ≤3 个；标注 ≤12 字。
4. **不占写区**：每页内容区 ≤140mm，下半页整块空白。
5. **图不占文**：宽 ≥80mm 或高 ≥60mm 的图独占一页，文字紧随其后另起一页；小图仍混排。
6. **语义完整行**（仅散文）：切行优先在语义边界断行，宁可当前行后半留空也不腰斩语义块；代码/公式/表格不适用。

# llm-work（判断层——机器做了会出事的部分）

分工总原则：**确定性操作进代码，判断留 AI。**

- **L1 取文路由**：识别输入格式 → 选适配器；抓不到就明说「拿不全」，不凭记忆补。
- **L2 容错纠错**：唯一的动字权（字词级，语病不动），按语义纠 + 词表有据 + 〔待确认〕兜底。
- **L3 排骨架**：定逻辑层级、顺序、关系（因果 → / 推进 ⇨ / 前提 ∵）。
- **L4 内容类型识别**：排骨架之前先识别内容类型（散文/代码块/公式/参数表/图文耦合），不同类型走不同排版通道。→ REFERENCE.md「内容类型识别」
- **L5 定语义块**：空格落点——主谓之间、标注块前后、句读之后；jieba 只做参考，刀口由 AI 定。
- **L6 图片拍板**：按尺寸阈值自动判定独占页；OCR 重绘结果逐张确认（台账 `confirmed=true`）后才上纸。
- **L7 冲突裁决**：表层要求撞铁律时 → 指出冲突，不默默执行。
- **L8 公式处理**：识别数学公式/符号，标记为 KaTeX 渲染对象。→ REFERENCE.md「公式处理」
- **L9 交付前自查**：T4 机检通过后，过 `checklist.md` 逐项确认，签字才进 T5。

# code-work（机械层——确定性操作 + 执法）

- **C1 取文机械**：`scripts/epub2md.py`｜ `scripts/asr.py`（py -3.12，GPU 约 14x 实时）｜ `scripts/t1_audit.py`（对账）。
- **C2 冻结基准**：`原文.txt` 写定即冻结，是下游一切校验的唯一基准。
- **C3 切行排版**：`scripts/typeset.py`——散文按语义完整行（语义边界优先，宽度兜底）；代码/公式/表格按宽度优先；禁则仅对散文生效。
- **C4 量高分页**：每块高度不估算，无头浏览器实测（写进 `data-mm`），按实测值装页。
- **C5 渲染闭环**：`scripts/render.py`（无头 Chromium 印 PDF）→ 量真品墨点 → 超界收紧上限重排（≤4 轮）。
- **C6 机检执法**：`scripts/check.py` 十项（字数守恒 / 符号闭合 / 标注密度 / 标注长度 / 行长双闸 / 每页内容高 / 真品墨迹边界 / PDF 回读 / 图源完整 / 图片台账）。**未过机检不出 PDF。**
- **C7 图片机械**：`scripts/imgdiag.py`（分流 + 尺寸阈值判定）｜ `scripts/imgredraw.py`（OCR 重绘）。
- **C8 公式渲染**：KaTeX 集成（本地 `assets/katex/` 优先，CDN fallback，再 fallback 等宽纯文本）。

# 执行流程

```
T1 取文（含 T1b 图片分流）→ T1c 内容类型识别 → T2 排骨架 → T3 落版 → T4 机检 → T4b checklist 自查 → T5 渲染交付
                                                                                    ↑________|（发现问题回去修）
长件：L0 量规模 → L1 split → L2 子 agent 定标注 → L3 逐章排检 → L4 assemble → L5 交付
```

## P1 触发
- **手动（唯一入口）**：`/paiban {输入}`。裸 `/paiban` → 问要排什么，不猜。
- **交棒**：其他 skill 内容已定稿、只要排版 → 直接进 T2。
- **放行**：帆说「不用排版直接出」，或命令带 `--paiban-ok`。
- **不触发**：只在 chat 里看内容不出文件；内容还没定稿（那是 rbook / lbook 的活）。
- **长件自动判定**：输入 >6 万字符、或 >100 个顶层块、或多份音频需合并时，自动宣告进长件模式，一句话告诉帆。

## P2 步骤路由

### T1 取文
- 产出 `原文.txt` 并立刻对账（`t1_audit.py`）；粘贴/转写件先存 `原始粘贴.txt` 底稿再对账。
- 保留结构线索另记 `来源.md`。
- 扫描件 PDF / 需登录页面：抓不到就明说，不凭图猜字。
- 输入适配器 → REFERENCE.md「输入适配器」；图片分流 → REFERENCE.md「图片处理（T1b）」。

### T1c 内容类型识别
- 识别散文/代码块/公式/参数表/图文耦合，标记排版通道。→ REFERENCE.md「内容类型识别」

### T2 排骨架（llm-work L3+L4+L5）
- 定层级、定标注、定语义块；过 `typography.md` 十条自检后进 T3。表层要求与铁律冲突 → L7 指出。

### T3 落版
- 机械部分交 `typeset.py`。关键纪律 → REFERENCE.md「落版纪律」。

### T4 机检
```
py -3.12 scripts/check.py --orig 原文.txt --html 排版.html --out 机检.json [--injected 标注清单.json] [--pdf 排版.pdf]
```
任一红 → 定向修后重跑，不进 T5。`机检.json` 的 `pass: true` 是 hook 放行凭据。

### T4b checklist 自查
- 过 `checklist.md` 逐项确认，发现问题回去修，全部通过才进 T5。

### T5 渲染交付
```
py -3.14 scripts/render.py --html 排版.html --pdf 排版.pdf
```
交付报告一行制：页数 / 字数守恒 / 每页峰值行 / 超限项 / 图片处置 / 公式渲染数 / checklist 结果。提醒帆打印实测。

## P3 状态外化
任务目录 `E:\yufan\yufan-reading\排版\{日期}-{短名}\`：原文.txt、来源.md、images/、图片台账.json、redraw/、结构台账.json 与 chunks/（长件）、标注清单.json、排版.html、机检.json、排版.pdf。多轮改动加 `进度.md`，只增不删。

## P4 产出契约
- 交付物：`排版.pdf`（主）+ 中间件留任务目录可回溯。
- 合格：`check.py` 全绿 **且** checklist 自查通过 **且** 帆打印实测「下半页够写」。
- 禁止：未过 T4 出 PDF；为塞进半页删字；重绘图片未经帆确认上纸。

# 边界
- 不改内容一句（例外见「禁令与例外」）、不回写源码。
- 不做屏幕深色阅读档（007）、不做内容提炼（rbook / lbook / rnovel）。
- 规范真源是 `typography.md`（v0.7，字体定版华文楷体 STKaiti），本 skill 不自建规范。
- 写操作只在本 skill 目录与任务目录内；改宿主配置需帆逐次授权。

# 变量说明
- `{user-input}` / `$ARGUMENTS`：/paiban 后接的路径、URL 或粘贴文本。
- `{短名}`：任务目录名（≤8 字）；`{日期}`：YYYYMMDD。
- `--paiban-ok`：白名单记号，渲染命令带它即绕过 hook。
- `{真源}`：`E:\yufan\yufan-find\references\typography.md` 与宿主插件目录两处同步。
- 完整变量表 → REFERENCE.md「变量说明」节。