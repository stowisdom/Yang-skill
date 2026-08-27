# REFERENCE.md — codeloop-yang-021 细则（按需读取，不常驻）

## 1. P2 遗留物 grep 清单（起点，非全集——现场语言栈自行增补）

| 类别 | 模式 | 说明 |
|---|---|---|
| debug 输出 | `print(` `console.log(` `console.debug(` `logger.debug(` `dd(` `var_dump(` `System.out.print` | 报告时排除 tests/ 下的合法打印；一行内多个命中算一条 |
| 未完标记 | `TODO` `FIXME` `XXX` `HACK` `WIP` | 带上下文一行；tests 里也报 |
| 注释掉的代码 | 连续 ≥3 行以 `//` `#` 开头且含代码特征（`=` `(` `return` `def` `function`） | 人写注释不算——只抓像代码的 |
| 临时/备份文件 | `*.bak` `*.tmp` `*~` `*.orig` `.DS_Store` `Thumbs.db` | 文件级发现 |
| 空捕获 | `except:` + `pass`（py）；`catch` + 空 `{}`（js/ts） | 静默吞错 |

取证纪律：每条 `文件:行号 + 原文摘录`，无证据不报（skill 体检医生同款铁律）。同类命中爆量（>10 条）时报告折叠成计数 + 最严重 3 例，全量进台账。

## 2. 巡检报告模板

存 `codeloop/巡检报告/YYYYMMDD-HHMM.md`：

```markdown
# 巡检 · {时间} · {项目名}

## 需要你看的（≤3 件）
1. {是什么 · 在哪 · 严重吗}
（第 4 件起：另有 N 件同类，见台账）

## 面板
- 机器判据：{verdict}（build={…} test={…}）
- 发现：新 {X} · 消 {Y} · 仍 {Z}
- 约定：{M} 条，违 {K} / 全守
- 改动面：{git diff 文件数 或 最近 mtime 改动 N 文件}

## 证据附录（全量，报告正文之外）
{发现逐条：id · 文件:行号 · 原文 · 类别}
```

降噪红线内化于此：报告正文一屏放得下；超了先砍证据细节（进附录），不砍「需要你看的」条数上限。长日志/长 diff 要单独压成摘要的，那是主会话顺手的事，不归本环。

## 3. 回声判据表方法

声称 → 判据的转换套路：

| 声称类型 | 可查判据 | 查法 |
|---|---|---|
| 「加了功能 X」 | 入口存在且可跑 | 读文件 + 跑最小验证（函数调用/测试） |
| 「测试都过了」 | verify verdict=pass | verify.py |
| 「修好了 Y」 | 复现路径走一遍 | 按声称的复现路径实际执行 |
| 「改了 Z 文件」 | 文件真的动了 | git diff / mtime |
| 「性能/数字提升了 N」 | 数字可复现 | 重跑测量；复现不了标存疑 |

三档结论：✓（证据在手）/ ✗（反证在手）/ 存疑（查不实——工具够不着或条件不足，写明缺什么）。**存疑不是 ✗**，不替人定罪。

## 4. 台账命令（巡检的内部引擎，scripts/ledger.py）

```bash
python <skill>/scripts/ledger.py init --project .                    # 首巡建 codeloop/
python <skill>/scripts/ledger.py add --project . --type 发现 --title "calc.py 残留 debug print" --detail "L12 print('debug')" --evidence "calc.py:12" --tag 遗留物
python <skill>/scripts/ledger.py sight --project . --id L004        # 又见到了：仍在上次发现时间线
python <skill>/scripts/ledger.py resolve --project . --id L004      # 消失了：标已消
python <skill>/scripts/ledger.py add --project . --type 约定 --title "不留 debug 输出" --detail "提交前删净 print/console.log"
python <skill>/scripts/ledger.py query --project . "print 遗留" --open --limit 5   # P5 取未消发现
```

条目三型：〔发现〕（带状态：待处理→仍在→已消）/〔坑〕/〔约定〕。只增不删，状态可更。
升约定通道：同一〔发现〕仍在 ≥2 次巡检 → 报告里主动提议「升约定？」，用户点头才 add 约定——规则长出来靠用户拍板，不靠环自作主。

## 5. 定时巡检（可选，用户明说才挂）

用户说「每 N 分钟巡一次」→ CronCreate（本会话工具）：`intervalUnit=minute`、`interval=N`、prompt 写自包含指令（「在当前项目跑 /cl 巡检，报告存 codeloop/巡检报告/，只报告不动手」）。用户没明说永不自挂；跨会话定时需用户确认过再说。

## 6. verify verdict 字段（P1 用）

| 字段 | 取值 | 含义 |
|---|---|---|
| verdict | pass / pass-notests / fail / unknown-stack | 只报告不拦截 |
| build.status | pass / fail / skip / timeout | skip=该栈无独立编译命令 |
| test.status | pass / fail / none / skip / timeout | none=无测试（如实报，不催用户补测试） |
| *.log_tail | 文本 | fail 时进报告「需要你看的」，pass 时丢弃 |

栈探测认七类：npm / python / go / cargo / maven / gradle / make。unknown-stack → 报告里问用户一次，答案记台账〔约定〕（本项目怎么编译/测试），下巡生效。

## 7. 分工表（不抢场景的边界对照）

| 场景 | 归谁 |
|---|---|
| 需求翻译、推导链 | 需求翻译官（prompt002/004） |
| 写码、修 bug、技术选型 | 主会话 coding agent + 用户 |
| 架构级大改 | 控制变量 coding（用户在 Qoder 上的创作） |
| skill/prompt 创作物体检 | skill 体检医生 |
| 创作态流程 | prompt-yang-014 / skill-yang-015 |
| **干完活之后的细节检查、回声核对、差分记忆** | **本环（仅此一块）** |

## 8. 多项目

环只在当前 workspace 跑，台账（codeloop/）是纯文件：ZCode 巡检完，Qoder/kimi-code 会话照样能读 `codeloop/巡检报告/` 与 `工程台账.md`——巡检记忆跨 agent，无需装任何东西。
