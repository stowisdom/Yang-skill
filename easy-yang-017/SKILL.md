---
name: easy-yang-017
description: >-
  将任何任务/想法/目标拆解为「伸手就能碰到」的最小可执行动作，
  输出 Action Card（HTML）。3+3+3式拆解 + 颗粒度评分机制。
  通过选择题引导填补信息，让用户少打字、零返工。
  触发前缀：easy:（硬匹配）
version: 4.0.0
author: User
license: MIT
metadata:
  hermes:
    tags: [task-decomposition, action-cards, productivity, execution]
    related_skills: [foggdesign-yang-001, list-making-yang-009, information-showing-yang-007, ddl-yang-002]
---

# easy: — 任务拆解 → Action Card

触发前缀 `easy:` 为硬匹配，必须以此前缀开头才触发本 skill。

### 设计原则（来自构建过程中的共识）

- **先做最小可用**：砍掉日志、模式库、自动闭环，只保留核心链路
- **人管生死，AI 管拆解**：用户手动维护 todolist.txt，AI 只负责读取和拆解
- **skill 间通过共享文件协作**：ddl/easy/ddltodo 共享 todolist.txt，互不调用
- **先对齐方案再改正文**：讨论阶段对齐思路，确认后才落盘修改

---

## 核心哲学

### 第一原则

> **让任务足够简单，简单到对方能动起来。**

### 五条公理

| # | 公理 | 说明 |
|:--:|:-----|:-----|
| 1 | 得到一个可以伸手就碰到的具体对象 | 步骤指向{一个文件}、{一个按钮}、{一行文字}、{一个人名} |
| 2 | 你无法做一个项目，你只能做一个动作 | <David Allen>：任务不是被执行的，动作才是 |
| 3 | 让启动摩擦降到最低 | 时间单位：5min 或 15min（第一步不超过15min）<br>难度单位：3×3×3 结构（最少3步，最多9步） |
| 4 | 给选项不给空白，给方向不给问题，给步骤不给思考题 | 降维：把「选择题」当「填空题」来出 |
| 5 | 串行式设计 Action Cards：A 的输出 = B 的输入 | 步骤之间有因果链：上一步的产出物 = 下一步的原材料 |

---

## 路由

### 路由1：easy:文本内容

用户输入 `easy:` 后跟文本 → 对该文本执行拆解 Work。

### 路由2：easy:（无文本）

用户输入 `easy:` 后无文本 → 读取 todolist.txt，对**时间最近的 #1 任务**执行拆解。

#### 流程

```
Step A：读取 todolist.txt
        路径：C:\Users\lenovo\Desktop\todolist.txt
        解析每行（格式：任务名--M/D）
        计算剩余天数 = DDL - now
        按剩余天数排序，取 #1（最近的一个）

Step B：对该任务执行拆解 Work（见下方 Work 章节）

Step C：输出 Action Card（HTML）
```

#### 分工

- **你**：手动维护 todolist.txt（写入新任务、标记 ✅ 完成、删除旧任务）
- **AI**：读 todolist → 取 #1 → 拆解 → 输出 Action Card

---

## Work · 3+3+3 式拆解

### Step 1 · 解析输入

理解用户输入（文本 or todolist #1 任务），提取：
- {目标}：想达成什么
- {现状}：已经知道/有什么
- {卡点}：卡在哪里

一句话回显，确认理解。

### Step 2 · 信息补全（选择题引导）

> **原则：让用户少打字，少重复。返工就是最大的效率杀手。**

逐步（one-by-one）提问。选择题 + 「其他（自由输入）」。

| # | 维度 | 选择题模板 |
|:--:|:-----|:----------|
| Q1 | 任务类型 | A. 写/产出 B. 找到/查到 C. 决定/判断 D. 搞定/协调人或事 E. 其他 |
| Q2 | 交付物形态 | A. 文档/报告 B. 决策/结论 C. 可运行的东西 D. 沟通/会议 E. 不确定 |
| Q3 | 当前卡点 | A. 不知道从哪开始 B. 第一步太难 C. 做了一半不知下一步 D. 做完了不知好不好 E. 其他 |

**跳过规则**：已知信息跳过、不适用跳过。**最多问3个**。

### Step 3 · 3+3+3 式拆解

```
┌─────────────────────────────────────────────────────────┐
│                                                         │
│   3 + 3 + 3 式拆解                                       │
│                                                         │
│   第一层：大任务拆解（What）    最多3轮，颗粒度<3即停       │
│   ┌───────────────────────────────────────────────────┐ │
│   │  轮1：任务 → 子任务A + B + C                        │ │
│   │       评分 → 不合格 → 轮2：子任务继续拆              │ │
│   │       评分 → 不合格 → 轮3：再拆                     │ │
│   │       评分 → 合格 → 进入第二层                      │ │
│   └───────────────────────────────────────────────────┘ │
│                                                         │
│   第二层：执行路径拆解（How）   最多3轮，颗粒度<3即停       │
│   ┌───────────────────────────────────────────────────┐ │
│   │  轮1：子任务 → 具体步骤1 → 2 → 3                    │ │
│   │       评分 → 不合格 → 轮2：步骤继续拆                │ │
│   │       评分 → 不合格 → 轮3：再拆                     │ │
│   │       评分 → 合格 → 进入第三层                      │ │
│   └───────────────────────────────────────────────────┘ │
│                                                         │
│   第三层：指标拆解（How well）  最多3轮，颗粒度<3即停       │
│   ┌───────────────────────────────────────────────────┐ │
│   │  轮1：每步定验收指标（2-3条）                        │ │
│   │       评分 → 不合格 → 轮2：指标更具体                │ │
│   │       评分 → 不合格 → 轮3：指标加量化数字             │ │
│   │       评分 → 合格 → 输出 Action Card                │ │
│   └───────────────────────────────────────────────────┘ │
│                                                         │
│   步数约束：最少3步，最多9步                               │
│   时间约束：第一步 ≤ 15min                                │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

#### 颗粒度评分（0-10，越小越好）

```
  0 ──── 1 ──── 2 ──── 3 ──── 4 ──── 5 ──── 6 ──── 7 ──── 8 ──── 9 ──── 10
        ├──────────────────┤
          合格区（< 3）

  0-1  → 一步就能动手，不需要任何思考
  2    → 一步能动手，少量判断
  3    → 勉强能动，需要一点背景知识 ← 合格线边缘
  4-6  → 还需要再拆
  7-10 → 完全不可执行
```

#### 串行设计检查（公理5）

拆解完成后，验证链条完整性：

```
步骤1输出 → 步骤2输入 → 步骤2输出 → 步骤3输入 → ...

  ✅ 完整链：每个输入都能追溯到上一步的输出
  ❌ 断裂：某步的输入来源不明
```

#### 评分记录格式

每轮拆解后输出：

```
第1轮 → 颗粒度：6 → 不合格，继续
第2轮 → 颗粒度：3 → 勉强合格，细化一轮
第3轮 → 颗粒度：1 → 合格 ✓
```

---

## Output · Action Card

### 表达规范：祷言式

```
结构：动词 + 名词（具体对象） + 指标（做到什么程度）

  ✅ 打开文件，写下标题和3个关键词
  ✅ 搜索"XX"，找到2篇相关文章，复制链接到笔记
  ✅ 给张三发一条消息，问他周三下午有没有空
  ✅ 打开模板，把第1-3行填入今天的数据

  ❌ 整理一下思路        ← 没有具体对象，没有指标
  ❌ 准备一下资料        ← 动词太泛
  ❌ 做一下竞品分析      ← 这是项目，不是动作
```

### HTML 模板

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Action Card</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body {
    font-family: -apple-system, "Noto Sans SC", sans-serif;
    background: #0c0c0a;
    color: #c8c3b6;
    display: flex;
    justify-content: center;
    align-items: center;
    min-height: 100vh;
    padding: 2rem;
  }
  .card {
    background: #1a1a18;
    border: 1px solid #2a2a25;
    border-radius: 16px;
    padding: 2.5rem;
    max-width: 480px;
    width: 100%;
  }
  .card-tag {
    display: inline-block;
    background: #b08a4a;
    color: #0c0c0a;
    font-size: 0.7rem;
    font-weight: 700;
    letter-spacing: 0.08em;
    padding: 3px 10px;
    border-radius: 4px;
    margin-bottom: 1.5rem;
  }
  .action {
    font-size: 1.6rem;
    font-weight: 700;
    color: #f0ece0;
    line-height: 1.5;
    margin-bottom: 1.5rem;
    border-left: 3px solid #b08a4a;
    padding-left: 1rem;
  }
  .divider {
    border: none;
    border-top: 1px solid #2a2a25;
    margin: 1.2rem 0;
  }
  .section-label {
    font-size: 0.7rem;
    color: #5a5a50;
    letter-spacing: 0.1em;
    text-transform: uppercase;
    margin-bottom: 0.4rem;
  }
  .pipeline {
    font-size: 0.85rem;
    color: #9a9688;
    line-height: 1.8;
    margin-bottom: 0.8rem;
  }
  .pipeline .now {
    color: #f0ece0;
    font-weight: 600;
  }
  .pipeline .arrow {
    color: #b08a4a;
    margin: 0 0.3rem;
  }
  .checklist {
    list-style: none;
    padding: 0;
  }
  .checklist li {
    font-size: 0.9rem;
    color: #7ab8a0;
    padding: 0.3rem 0;
    padding-left: 1.4rem;
    position: relative;
  }
  .checklist li::before {
    content: "□";
    position: absolute;
    left: 0;
  }
  .badges {
    margin-top: 1rem;
    display: flex;
    gap: 0.6rem;
    flex-wrap: wrap;
  }
  .badge {
    font-size: 0.75rem;
    padding: 3px 10px;
    border-radius: 4px;
    font-weight: 600;
  }
  .badge-pass {
    background: rgba(122, 184, 160, 0.15);
    color: #7ab8a0;
  }
  .badge-time {
    background: rgba(176, 138, 74, 0.15);
    color: #b08a4a;
  }
  .badge-step {
    background: rgba(154, 150, 136, 0.15);
    color: #9a9688;
  }
</style>
</head>
<body>
  <div class="card">
    <span class="card-tag">NEXT ACTION</span>

    <!-- 行动指令：祷言式 -->
    <div class="action">
      {动词} {具体对象} {指标}
    </div>

    <hr class="divider">

    <!-- 串行管线 -->
    <div class="section-label">PIPELINE</div>
    <div class="pipeline">
      {上一步输出} <span class="arrow">→</span>
      <span class="now">本步输入</span> <span class="arrow">→</span>
      {本步输出}
    </div>

    <hr class="divider">

    <!-- 验收标准 -->
    <div class="section-label">DONE WHEN</div>
    <ul class="checklist">
      <li>{验收标准1}</li>
      <li>{验收标准2}</li>
    </ul>

    <!-- 徽章区 -->
    <div class="badges">
      <span class="badge badge-pass">颗粒度 {N}/10 ✓</span>
      <span class="badge badge-time">≈ {预估时间}</span>
      <span class="badge badge-step">STEP {X}/{总步数}</span>
    </div>
  </div>
</body>
</html>
```

---

## 交互约束

1. 一次只问一个问题
2. 选择题优先，半开放式（选项 + 其他）
3. 最多问3个问题
4. 不返工——理解偏差用选择题纠正
5. 语言跟随用户

## 输出约束

1. Action Card 以 HTML 文件输出，文件名 `action-card-{YYYYMMDD}-{序号}.html`
2. 保存路径：用户当前工作目录
3. 祷言式表达——动词+名词+指标

---

## Common Pitfalls

1. **名词当动作** → ❌「报告」 ✅「打开报告模板，填入标题」
2. **颗粒度放水** → 3秒内不能动手 = 颗粒度 ≥ 4，继续拆
3. **串行断裂** → 每步输入必须能追溯到上一步输出
4. **拆太多步** → 最多9步。超过 → 每步还是太大
5. **第一步太重** → 第一步 ≤ 15min。超过 → 继续拆

---

## Verification Checklist

- [ ] 祷言式表达（动词 + 具体对象 + 指标）
- [ ] 颗粒度 < 3（合格线）
- [ ] 步数 3~9 步
- [ ] 第一步 ≤ 15min
- [ ] 串行管线完整
- [ ] 有 DONE WHEN
- [ ] 选择题 ≤ 3 个
- [ ] HTML 已保存

---

## References

- `references/philosophy.md` — 拆解力的哲学基础（理论来源：BJ Fogg、David Allen、Daniel Pink、Bandura）
- `references/integration.md` — easy × ddl × ddltodo 三 skill 协作地图

## 外部 Skill 依赖

- `ddl-yang-002` — 任务截止时间管理，todolist.txt 位于 `C:\Users\lenovo\Desktop\todolist.txt`
