---
name: jiantu-tuijian-yang-014
description: "当用户提到简图、图画模板、视觉化工具、Graphic Template、画什么图、推荐图表时触发。通过逐步提问了解用户场景，从44种简图模板中推荐最匹配的3个。"
---

# 简图推荐 Skill

> 从44种视觉会议简图模板中，为你找到最适合当前场景的那一个。

## 触发条件

用户提到以下关键词时触发：
- 简图、图画模板、visual template、graphic template
- 画什么图、用什么图、推荐图表、选个图
- 思维图、分析图、规划图

## 资源文件

本 skill 的数据资源位于 skill 目录下的 `resource/diagrams.json`，包含：
- `categories` — 5大应用场景分类
- `templates` — 44个简图模板（含难度、受欢迎度、适用场景等）
- `questions` — 5道引导式选择题
- `recommendation_rules` — 推荐评分规则

**首次使用前必须读取资源文件。**

## 工作流

<work>

### Step 0 · 加载资源

读取 `resource/diagrams.json`，解析为工作数据。
令 `<categories>` = JSON.categories
令 `<templates>` = JSON.templates
令 `<questions>` = JSON.questions
令 `<rules>` = JSON.recommendation_rules

### Step 1 · 逐题引导（one-by-one）

按 `<questions>` 中的 `order` 顺序，**逐题**向用户提问。

**交互规则：**
- 每次只问**一道题**
- 展示选项列表，选项用编号标注（1, 2, 3...）
- 用户可以回复编号，也可以自由描述
- 如果用户自由描述，将描述映射到最接近的选项值
- 如果 `<questions[i].trigger>` 存在，仅当前置条件满足时才问此题（如 `scenario=multiple`）
- 按顺序收集以下用户回答，存入 `<answers>` 对象：
  - `scenario` — 使用场景
  - `multi_scenario` — 多场景选择（条件触发）
  - `difficulty_preference` — 难度偏好
  - `team_context` — 团队规模
  - `specific_need` — 具体需求

**语气：** 简洁友好，每题一句话 + 选项列表，不啰嗦。

### Step 2 · 计算推荐

收集完所有答案后，对每个模板计算匹配分：

```
score = 0

# 1. 场景匹配（权重 ×3）
if answers.scenario in template.categories:
    score += 3
elif answers.scenario == "multiple":
    for s in answers.multi_scenario:
        if s in template.categories:
            score += 3
            break

# 2. 难度匹配（权重 ×2）
range = rules.difficulty_ranges[answers.difficulty_preference]
if range.min <= template.difficulty <= range.max:
    score += 2
elif answers.difficulty_preference == "any":
    score += 1

# 3. 团队规模匹配（权重 ×1）
# 根据 team_size 字段判断是否匹配
if template.team_size 与 answers.team_context 匹配:
    score += 1

# 4. 需求匹配（权重 ×3）
keywords = rules.need_to_best_for_keywords[answers.specific_need]
for kw in keywords:
    if kw in template.best_for 或 kw in template.description:
        score += 3
        break

# 5. 受欢迎度加成（×0.1）
score += template.popularity * 0.1

# 6. 常见模板加成
if template.is_common:
    score += 0.5
```

### Step 3 · 输出推荐

取 **score 最高的 3 个模板**，按分数从高到低排列。

每个推荐包含：

```
🏆 推荐 #1：{name_cn}（{name_en}）

📊 匹配度：⭐⭐⭐⭐⭐（5星制，基于score映射）
📂 场景：{categories}
🎯 难度：{difficulty}/10
📈 受欢迎度：{popularity}/10

💡 为什么推荐你用这个：
基于你的回答（{场景} + {需求} + {难度偏好}），这个模板最匹配。

📋 适用场景：
{best_for 列表}

🏗️ 结构特征：
{structure}

👥 推荐团队规模：
{team_size}
```

**输出格式要求：**
- 3个推荐用编号 #1、#2、#3 标注
- #1 是最匹配的，给出最详细的说明
- #2、#3 给出简要说明 + 与 #1 的差异点
- 如果有并列分数，优先推荐更常见的（is_common=true）
- 最后附一句总结，引导用户做出选择

### Step 4 · 确认与深入

询问用户：
1. 是否选择了某个推荐？
2. 想深入了解哪个模板的使用方法？
3. 是否需要我为你画出这个简图的结构草图？

如果用户选择了某个模板，输出该模板的完整信息（description + structure + best_for）。
如果用户想看结构草图，用 Mermaid 或文字描述画出模板的基本结构。

</work>

## 推荐评分规则速查

| 维度 | 权重 | 来源 |
|------|------|------|
| 场景匹配 | ×3 | answers.scenario ↔ template.categories |
| 难度匹配 | ×2 | answers.difficulty_preference ↔ template.difficulty |
| 团队匹配 | ×1 | answers.team_context ↔ template.team_size |
| 需求匹配 | ×3 | answers.specific_need ↔ template.best_for |
| 受欢迎度 | ×0.1 | template.popularity |
| 常见加成 | +0.5 | template.is_common |

## 难度范围映射

| 偏好 | 难度范围 |
|------|----------|
| 简单 simple | 1-4 |
| 中等 moderate | 4-7 |
| 专业 complex | 7-10 |
| 都可以 any | 1-10（给+1分鼓励分） |

## 注意事项

- 读取 resource 文件路径：与 SKILL.md 同级的 `resource/diagrams.json`
- JSON 解析失败时，告知用户并建议检查资源文件
- 如果没有任何模板得分 > 3，说明匹配度较低，建议用户放宽条件或描述更多需求
- 推荐结果中避免重复推荐同一类别（如3个都是分析类），优先覆盖不同类别
