---
name: "file-storage-yang-010"
description: "Set up file hierarchies, organize files into categories, and perform file operations"
alwaysAllow:
  - "Bash"
  - "Read"
  - "Write"
---

# file-storage-yang-010

## Background

用户需要处理文件类型如下：
- 视频
- 音频
- 文字（.md, .pdf, .docx, .txt 等）

## 文件处理方式

允许使用终端指令进行文件操作。

## User Input

- 文件路径
- 直接上传文件

## Workflow

### Step 1

识别文件类型（视频 / 音频 / 文字）。

If
User input：为大段 txt 文本
Model：将 txt → .md 文件，并纳入到 Step 3.1 中的表格中待处理

### Step 2

识别 `<user input>` 的输出为文件路径还是直接上传文件。

### Step 3

**绝对禁止：进行删除操作、更改操作。**

#### Step 3.1

用（序号 -- 文件名 -- 文件当前路径 -- C（分层）/ M（移动））格式，表格呈现 `<user input>`。

#### Step 3.2

等待用户选择文件操作：
- **C** 选项指代分层
- **M** 选项指代移动

#### Step 3.3

**交互核心：**
- 让用户少打字，模型多引导，少重复，返工就是最大的效率杀手
- 模型可以主动给出文件操作建议

**If 用户选择 C：**
- 用半开放式选择式交互引导用户完成文件夹的层级结构设置

**Else if 用户选择 M：**
- 用半开放式选择式交互引导用户完成当前路径移动到何处
