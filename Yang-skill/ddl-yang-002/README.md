# DDL Watcher - 任务截止时间管理工具

## 📦 功能

- 📊 **任务进度可视化**：以进度条形式展示所有任务的截止时间
- 🎨 **颜色分类提醒**：红/绿/蓝/灰四色区分紧急程度
- 👁️ **自动实时监听**：触发skill时自动启动监听器，文件修改后实时刷新报告

## 📁 文件说明

```
ddl/
├── SKILL.md              # Skill 指令文件
├── ddl_main.py           # Skill入口（自动启动完整流程）
├── ddl_watcher.py        # 文件监听器（后台运行）
├── auto_start_watcher.py # 监听器启动器
├── process_tasks.py      # 任务数据处理（在data目录）
├── generate_pdf.py       # PDF生成（在data目录）
├── start_watcher.bat     # 手动启动监听器（可选）
└── README.md             # 本文件
```

## 🚀 快速开始

### 1. 准备工作

确保任务文件存在：`C:\Users\lenovo\Desktop\Task.txt`

格式示例：
```
机械原理作业--4/8
计算机绘图&autocad--4/9
互换性实验报告--4/8
```

### 2. 触发 Skill（自动完成）

使用触发词：
```
now 2026年4月7日
```

或：
```
now 2026/4/7 23:44
```

### 3. 自动流程

触发skill后，系统会自动完成：

```
1. 启动文件监听器（后台运行）
   ↓
2. 处理 Task.txt 任务数据
   ↓
3. 生成 PDF 报告
   ↓
4. 显示当前任务统计摘要
```

### 4. 实时更新

监听器在后台运行期间：

```
编辑 Task.txt → 保存文件 → 自动刷新 PDF 报告
```

无需再次触发skill，报告会自动更新！

## 📊 输出文件

| 文件 | 路径 | 说明 |
|------|------|------|
| PDF报告 | `C:\Users\lenovo\.craft-agent\workspaces\my-workspace\sessions\{日期}\data\DDL_Report.pdf` | 可视化进度报告 |
| 数据文件 | `...\data\tasks_data.json` | 结构化数据 |
| 状态文件 | `...\data\.ddl_watcher_state.json` | 监听状态 |

## 🎨 颜色说明

| 颜色 | 分类 | 时间范围 | 紧急程度 |
|------|------|----------|----------|
| 🔴 红色 | C类 | 1-3周 / 1-2天 / 4-24小时 | 紧急 |
| 🟢 绿色 | B类 | 3-9周 / 2-4天 | 中等 |
| 🔵 蓝色 | A类 | 9-12周 / 4-7天 | 宽松 |
| ⚪ 灰色 | 超出范围 | 已过期 / >12周 | 特殊 |

## ⚙️ 高级用法

### 手动单次运行（不启动监听）

如果只需要生成一次报告，不使用实时监听：

```bash
# 1. 处理数据
python data/process_tasks.py data/tasks_data.json

# 2. 生成PDF
python data/generate_pdf.py data/tasks_data.json data/DDL_Report.pdf
```

### 检查监听状态

```bash
ddl_watcher.py --status
```

或双击 `check_status.bat`

## 🔧 故障排除

### 问题：双击 start_watcher.bat 后闪退

**解决**：
1. 检查 Python 是否安装：`python --version`
2. 检查 Task.txt 是否存在：`dir C:\Users\lenovo\Desktop\Task.txt`

### 问题：无法自动刷新

**解决**：
1. 确认监听器正在运行（窗口未关闭）
2. 检查是否有保存文件（仅修改不保存不会触发）
3. 查看控制台是否有错误信息

### 问题：中文显示乱码

**解决**：
- Windows 10/11 默认支持 UTF-8，如遇到乱码请确保文件保存为 UTF-8 编码

## 📝 更新日志

### v2.0 (2026-04-08)
- ✨ 新增文件监听自动刷新功能
- ✨ 新增启动脚本和状态检查
- 📝 完善文档和错误处理

### v1.0 (2026-04-07)
- 🎉 初始版本：时间比对、分类、PDF生成
