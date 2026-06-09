---
name: "skill-flow-yang-000"
description: "用户输入 yang:内容。列出可用技能并创建可点击的交互式HTML界面，用户可点击复制技能名称。触发前缀：yang:（硬匹配）"
---

# Skill Flow Yang 000

通过 `yang:` 前缀触发。触发前缀 `yang:` 为硬匹配，必须以此前缀开头才触发本 skill。

List the available skills. Create a clickable, interactive HTML interface where users can click to copy the skill name.

Triggered when a user requests a list of currently available skills.

## Steps

### Step 1
Scan `C:\Users\lenovo\.qoderworkcn\skills` and list all folder names (i.e., skill names).

### Step 2
List all available skills. Output a clickable interactive HTML interface where clicking copies the skill name.and explicitly specify the path to the output HTML file

## HTML Aesthetic Reference
See `C:\Users\lenovo\.craft-agent\workspaces\my-workspace\skills\skill-flow-yang-000\reference` for HTML style reference.

## Guarantees
1. Ensure scanning is not duplicated or missed.
2. Ensure scanning is quick and concise, with no unnecessary actions.
