---
name: ddl-yang-002
description: "管理任务截止时间，读取Task.txt任务列表，计算剩余时间并按紧急程度分类，生成「墨」风格可视化HTML报告（含进度条与时间轴）。当用户发送DDL、或提到截止日期、deadline、任务到期、剩余时间、任务进度时使用。"
version: "3.1"
---

# DDL Skill - 任务截止时间管理

## 功能特性

- ⏰ **时间比对**：计算任务剩余时间
- 📊 **可视化进度条**：以进度条形式显示各项任务时间
- 🎨 **颜色分类**：A类(墨蓝)、B类(墨绿)、C类(赤墨)、超出范围(淡墨)
- 👁️ **自动监听**：使用skill时自动启动后台监听器，文件修改后实时刷新报告
- 🏮 **东方极简美学**：「墨」风格深色主题，留白、内敛、意蕴丰富
- 🕰️ **时间轴箭头**：水平箭头时间轴，自适应比例尺，脉冲标注当前时刻，按截止时间排列全部任务
- 📐 **开根号节点**：自动计算两个时间标尺节点（√总天数、√剩余天数），量化行动节奏
- 🔍 **时间焦点**：视觉重心转向时间，节点超大号、截止大号、事项常规，一目了然

## 触发场景

用户发送"DDL"（三个字母，不区分大小写）时触发本技能。
以下表达也应触发：提到截止日期、deadline、任务到期、任务进度等。

## 工作流

<work>
	<step0>
	触发skill时，自动执行入口脚本：
	python C:\Users\lenovo\.craft-agent\workspaces\my-workspace\skills\ddl\ddl_main.py
	
	该脚本会自动完成以下操作：
	1. 启动/检查文件监听器（后台运行）
	2. 处理 Task.txt 任务数据
	3. 生成 HTML 报告（东方极简「墨」风格）
	4. 输出统计摘要
	</step0>

	<step1>
	自动获取当前时间：
	通过 Bash 执行 date 命令（或读取系统上下文中的时间信息）获取当前时间
	令 <now> = 系统返回的当前时间
	若用户在消息中明确指定了其他时间，则以用户指定的时间覆盖 <now>
	</step1>
	
	<step2>
	读取理解<"C:\Users\lenovo\Desktop\Task.txt">中内容
	格式：每行一个任务，格式为 <任务名>--<截止时间>

		<读取流程>

		<step2.1>
		双通道读取目标文件
		通道A：使用 Read 工具读取文件，得到<内容A>
		通道B：使用 Bash cat 读取同一文件，得到<内容B>
		通道C：使用 Bash 独立统计，不依赖内容解析
			wc -l → <总行数>
			wc -c → <总字节数>
		</step2.1>

		<step2.2>
		第一层校验：内容一致性
		比对<内容A>与<内容B>
			若一致 → 通过，进入<step2.3>
			若不一致 → ⚠️报警，以<内容B>（cat结果）为准，继续进入<step2.3>
		</step2.2>

		<step2.3>
		第二层校验：条目数断言
		将确认后的内容按格式逐行解析，过滤空行，得到<条目列表>
		令
		<有效行数> = <总行数> 减去 空行数
		<条目数> = <条目列表>的长度

		断言：<条目数> == <有效行数>
			若相等 → 通过，进入<step2.4>
			若不等 → ⚠️存在遗漏或解析错误，回到<step2.1>重新读取
			（最多重试2次，仍失败则中断并报错）
		</step2.3>

		<step2.4>
		第三层校验：去重检测
		提取<条目列表>中每条的<任务名>
		检查所有<任务名>是否唯一
			若有重复 → ⚠️提示重复项，中断流程
			若全部唯一 → ✅ 通过
		</step2.4>

		<step2.5>
		输出校验报告
		格式：
		══════════════════════════════════
		  file-verify 校验报告
		══════════════════════════════════
		  文件：<文件名>
		  总字节：<总字节数>
		  总行数：<总行数>（空行<N>）
		  解析条目：<条目数>
		  重复条目：<重复数>
		──────────────────────────────────
		  第一层（双通道一致性）：✅ 或 ⚠️
		  第二层（条目数 = 行数）：✅ 或 ⚠️
		  第三层（无重复）      ：✅ 或 ⚠️
		──────────────────────────────────
		  结论：数据完整 / 存在问题（详见上方）
		══════════════════════════════════

		仅当三层全部 ✅ 时，<条目列表>才可被后续流程安全使用
		</step2.5>

		</读取流程>

	令
	<任务名>=<job>
	<截止时间>=<ddl>
	</step2>
	
	<step3>
	做减法：用<ddl>减去<now>得到<时差>
	令
	<时差>=<during>
	</step3>

	<step3.5>
	开根号节点计算（时间标尺）
	对每个任务，计算两个关键时间节点：

	■ 当 during ≥ 2天 时，以「日」为单位：
	令 <总天数> = during 的天数（四舍五入取整）

	第一节点：
		<N1天数> = floor(√<总天数>)  （取小不取大，即向下取整）
		<第一节点日期> = <now> + <N1天数>天

	第二节点：
		<剩余天数> = <总天数> - <N1天数>
		<N2天数> = floor(√<剩余天数>)  （取小不取大）
		<第二节点日期> = <第一节点日期> + <N2天数>天

	示例：
		today=4/15, ddl=4/24, 总天数=9
		第一节点：√9 = 3 → 4/18
		第二节点：√(9-3)=√6 ≈ 2.449 → floor=2 → 4/18+2 = 4/20

	■ 当 during < 2天 但 ≥ 2小时 时，以「时」为单位：
	令 <总小时> = during 的小时数（四舍五入取整）

	第一节点：
		<N1小时> = floor(√<总小时>)
		<第一节点时间> = <now> + <N1小时>时

	第二节点：
		<剩余小时> = <总小时> - <N1小时>
		<N2小时> = floor(√<剩余小时>)
		<第二节点时间> = <第一节点时间> + <N2小时>时

	示例：
		now=19:00, ddl=明天07:00, 总小时=12
		第一节点：√12 ≈ 3.46 → floor=3 → 22:00
		第二节点：√(12-3)=√9 = 3 → 22:00+3 = 明天01:00

	节点日期格式：
	- 天级节点：显示「M/D」（如 4/18）
	- 时级节点：同日显示「HH:MM」（如 22:00），跨日显示「M/D HH:MM」（如 4/16 01:00）

	边界处理：
	- during < 2小时 → 不计算节点
	- N1 = 0 → 不显示节点
	- N2 = 0 → 仅显示第一节点
	</step3.5>
	
	<step4>
	将during分类到以下一类中
	（边界值规则：当边界值重叠时，归入更紧急的类）

		<A类>
		9周 < during ≤ 12周  或  4天 < during ≤ 7天
		</A类>

		<B类>
		3周 < during ≤ 9周  或  2天 < during ≤ 4天
		</B类>

		<C类>
		1周 ≤ during ≤ 3周  或  1天 ≤ during ≤ 2天  或  4小时 ≤ during ≤ 24小时
		</C类>

		<超出范围>
		以下情况单独标注：
		- during > 12周 → 标注为"长期任务"
		- during < 4小时 → 标注为"极度紧急"
		- during ≤ 0（已过期）→ 标注为"已过期"
		</超出范围>
	</step4>
	
	<step5>
	整理<step4>排序分类内容为一份完整单文件HTML报告
	应用「墨」风格审美设置（详见下文）
	以进度条的形式显示各项任务时间
	并分配颜色
	<A类>--墨蓝 #4a6fa5
	<B类>--墨绿 #5a7a5a
	<C类>--赤墨 #a55a5a
	<超出范围>--淡墨 #6a6a6a

	视觉焦点转向时间：
	每张任务卡片内，设「时间焦点区」，通过字体大小建立视觉层级：
	- 第一、第二节点日期：超大号（2.8rem / font-weight:700），颜色为该任务对应分类色
	- 截止日期：大号（2rem / font-weight:600），颜色为 --white
	- 任务名称：常规（1.2rem），保持原有样式
	节点区（左侧）与截止日期区（右侧）通过 flex 布局左右对齐，形成视觉对比呼吸感
	无节点的任务（during < 2天）仅显示大号截止日期
	</step5>

	<step6>
	在报告末尾（尾声区之前）生成「时间截」模块——水平箭头时间轴
	应用时间轴审美设置（详见下文「时间轴箭头模块」章节）

		<时间轴构建流程>

		<step6.1>
		数据准备
		将<step4>中所有任务按<ddl>从早到晚排序
		将已过期任务（during ≤ 0）单独抽出，放入<过期列表>
		将未过期任务放入<活跃列表>
		</step6.1>

		<step6.2>
		比例尺计算（自适应/对数压缩）
		令 <时间跨度> = 最晚ddl - now
		对每个活跃任务，计算其相对位置：
			position = log(1 + during_hours) / log(1 + max_during_hours) × 100%
		效果：近期任务间距放大、远期任务间距压缩，突出紧急任务
		当所有任务的ddl集中在同一天时，退化为线性等比例
		</step6.2>

		<step6.3>
		Now标记
		在时间轴最左端（position=0%处）放置「此刻」标记：
		- 墨金色（--ink）竖线，高度贯穿时间轴上下
		- 竖线上方标注「此刻」二字（Noto Serif SC / 0.8rem / --ink）
		- 附加脉冲动画（CSS @keyframes pulse）：
			竖线的box-shadow在 0→50%→100% 周期内
			从 0 0 0px 透明 → 0 0 12px rgba(196,168,124,0.6) → 0 0 0px 透明
			动画周期2s，infinite
		</step6.3>

		<step6.4>
		任务节点渲染
		每个活跃任务在时间轴上的对应position处放置一个节点：
		- 节点圆点：8px实心圆，颜色为该任务所属分类色（墨蓝/墨绿/赤墨/淡墨）
		- 节点上方（奇数位）或下方（偶数位）交替显示信息卡片：
			第一行：<任务名>（Noto Serif SC / 1rem / font-weight:600 / --white）
			第二行：<截止日期>（Noto Sans SC / 0.85rem / --text）
			第三行：分类标签小方块（对应分类色背景 + 分类名文字，如「C类·紧急」）
		- 节点圆点到信息卡片之间用1px细线（--border-light）连接
		- 字体和日期要醒目，确保一眼可辨
		</step6.4>

		<step6.5>
		过期任务折叠区
		若<过期列表>非空，在时间轴左侧（Now标记之前）渲染折叠区域：
		- 区域标题：「已过期」（Noto Sans SC / 0.75rem / --text-dim / letter-spacing:0.2em）
		- 背景：半透明暗红 rgba(165,90,90,0.08)，1px dashed var(--border-light) 边框
		- 内部竖排列出过期任务，每条显示：
			<任务名>（--text-muted / 删除线 text-decoration:line-through）
			<过期时长>（如「已过期2天3小时」/ 0.7rem / 赤墨色 --color-c）
		- 默认折叠，仅显示标题和过期数量，点击可展开
		</step6.5>

		<step6.6>
		水平箭头与自动换行
		- 时间轴主线：2px solid var(--border-light)，水平延伸
		- 末端（最右侧）为箭头形状，用CSS border或SVG三角形，颜色--border-light
		- 当任务节点过多导致单行拥挤时（节点间距 < 80px），自动折行：
			将时间轴分为多段，每段一行
			段与段之间用弧形连接线（或折角箭头）衔接，表达时间连续性
			每行保持独立的Now到箭头方向（左→右）
		- 整体容器最大宽度与报告一致（800px），左右padding:2rem
		</step6.6>

		</时间轴构建流程>

	</step6>
</work>

## 东方极简「墨」风格审美设置

### 风格定位
东方极简「墨」——深色、留白、内敛、意蕴丰富

### 颜色系统（CSS变量）
```css
--bg: #0a0a0a           /* 近黑背景 */
--surface: #111         /* 表面色 */
--border: #1e1e1e       /* 边线 */
--border-light: #2a2a2a /* 浅边线 */
--text: #a09888         /* 正文暖灰 */
--text-muted: #605848   /* 次要文字 */
--text-dim: #383028     /* 最淡文字 */
--white: #e8e0d4        /* 亮色文字 */
--cream: #d4c8b4        /* 奶油白 */
--ink: #c4a87c          /* 墨金强调 */
--ink-dim: #7a6848      /* 淡墨金 */

/* 任务分类色（墨色调和） */
--color-a: #4a6fa5      /* A类-墨蓝 */
--color-b: #5a7a5a      /* B类-墨绿 */
--color-c: #a55a5a      /* C类-赤墨 */
--color-gray: #6a6a6a   /* 超出范围-淡墨 */
```

### 字体系统（Google Fonts）
- 中文正文/标题：Noto Serif SC（宋体衬线）
- 中文标签/小字：Noto Sans SC（无衬线）
- 英文点缀：Cormorant Garamond（斜体衬线）

### 字号层级
- 装饰大字：7rem / font-weight:900 / 颜色接近背景色(--border-light)，半隐半现
- 卡片标题：1.2rem / font-weight:600 / --white
- 正文：0.88rem / font-weight:400 / --text / line-height:2.2 / text-indent:2em
- 标签小字：0.55-0.7rem / font-weight:300 / --text-dim / letter-spacing:0.3em+

### 时间焦点区（卡片内组件）
卡片内视觉焦点转向时间，通过字号差异建立三级时间层级：
- **节点日期**（第一、第二节点）：2.8rem / font-weight:700 / 分类色（最醒目，一眼可见）
- **截止日期**：2rem / font-weight:600 / --white（次醒目）
- **任务名称**：1.2rem / font-weight:600 / --white（常规层级）

布局：节点区左对齐，截止日期右对齐，形成左右呼吸对比
节点下方标注小字标签（「第一节点」「第二节点」/ 0.55rem / --text-dim / letter-spacing:0.3em）
节点下方附开根号公式（Cormorant Garamond / italic / 0.75rem / --text-muted），如「√9 = 3日」
无节点任务（during < 2天）仅显示 2.2rem 截止日期，左对齐

### 布局规则
- 最大宽度800px，居中
- 充足的padding（3-4rem），用留白制造呼吸感
- 用1px solid var(--border) 做段落间隔离线，制造层级
- 竖排文字（writing-mode:vertical-rl）做侧边装饰

### 卡片样式（核心组件）
- 外框：1px solid var(--border-light) 细边框
- 顶部装饰：左侧40px短线，用::before伪元素，背景色--ink-dim
- 内部结构：标题(1.2rem/600) → 正文(0.88rem/行高2.2/缩进2em) → 24px分割短线 → 注释(Noto Sans SC/0.7rem/--text-dim)
- 卡片之间用充足间距隔开，不紧贴

### 页面结构组件
1. **呼吸条**——页面顶部，细横线连接日期/期号等信息碎片
2. **标题区**——居中：超大装饰汉字 + 主标题 + 英文副标题 + 小圆点
3. **竖排侧边+正文区**——左侧竖排小字 + 1px分隔线 + 右侧正文
4. **间奏区**——居中大字+诗句，用作大段落之间的视觉呼吸
5. **方框卡片**——任务卡片的主要载体（上述卡片样式）
6. **三栏网格**——三等分+竖线分隔，适合展示并列概念（统计摘要）
7. **时间截（时间轴箭头）**——水平箭头时间轴，自适应比例尺，脉冲Now标记，上下交替任务卡片（详见「时间轴箭头模块」章节）
8. **尾声**——居中引文 + 底部装饰短线
9. **版权行**——居中小字，letter-spacing宽松

### 任务进度条样式
- 背景：var(--border)
- 填充：对应分类色（墨蓝/墨绿/赤墨/淡墨）
- 高度：6px
- 圆角：3px
- 微光效果：box-shadow: 0 0 8px rgba(颜色, 0.3)

### 整体气质
安静、克制、有呼吸感，深色中文字如夜空星辰被点亮

## 时间轴箭头模块（「时间截」）

### 模块定位
报告末尾的全局纵览组件——用一条水平箭头将所有任务的截止时间按序铺开，一目了然

### 整体布局
- 位置：在报告「尾声」区之前，作为独立区块插入
- 区块标题：居中大字「时间截」（Noto Serif SC / 2.5rem / font-weight:700 / --white），下方英文副标题「Timeline」（Cormorant Garamond / italic / 1rem / --text-dim）
- 标题与时间轴之间留 3rem 呼吸间距

### 时间轴主线样式
```css
.timeline-axis {
    height: 2px;
    background: var(--border-light);  /* #2a2a2a */
    position: relative;
    margin: 2rem 0;
}
.timeline-axis::after {
    /* 右端箭头 */
    content: '';
    position: absolute;
    right: -8px;
    top: -5px;
    border-left: 12px solid var(--border-light);
    border-top: 6px solid transparent;
    border-bottom: 6px solid transparent;
}
```

### Now 标记样式
```css
.now-marker {
    position: absolute;
    left: 0;  /* position=0% */
    top: -20px;
    bottom: -20px;
    width: 2px;
    background: var(--ink);  /* #c4a87c 墨金 */
    animation: pulse 2s ease-in-out infinite;
}
.now-marker::before {
    content: '此刻';
    position: absolute;
    top: -28px;
    left: 50%;
    transform: translateX(-50%);
    font-family: 'Noto Serif SC', serif;
    font-size: 0.8rem;
    color: var(--ink);
    white-space: nowrap;
}
@keyframes pulse {
    0%, 100% { box-shadow: 0 0 0px transparent; }
    50% { box-shadow: 0 0 12px rgba(196,168,124,0.6); }
}
```

### 任务节点样式
```css
.timeline-node {
    position: absolute;
    transform: translateX(-50%);
}
.timeline-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    /* background 由分类色决定 */
}
.timeline-card {
    position: absolute;
    white-space: nowrap;
}
.timeline-card .task-name {
    font-family: 'Noto Serif SC', serif;
    font-size: 1rem;
    font-weight: 600;
    color: var(--white);  /* #e8e0d4 */
}
.timeline-card .task-date {
    font-family: 'Noto Sans SC', sans-serif;
    font-size: 0.85rem;
    color: var(--text);  /* #a09888 */
}
.timeline-card .task-tag {
    display: inline-block;
    padding: 2px 8px;
    font-family: 'Noto Sans SC', sans-serif;
    font-size: 0.65rem;
    letter-spacing: 0.1em;
    border-radius: 2px;
    /* background 由分类色决定，opacity:0.8 */
    color: var(--white);
}
/* 连接细线（节点到卡片） */
.timeline-stem {
    width: 1px;
    background: var(--border-light);
    /* 高度根据上方/下方交替调整 */
}
```

### 上下交替规则
- 奇数位节点（第1、3、5…个）：信息卡片在时间轴**上方**，连接线向上
- 偶数位节点（第2、4、6…个）：信息卡片在时间轴**下方**，连接线向下
- 交替展示避免视觉拥挤，形成锯齿韵律感

### 自适应比例尺算法
```
对于每个活跃任务 i：
  during_hours_i = (ddl_i - now) 转换为小时数
  max_hours = max(所有 during_hours)
  position_i = log(1 + during_hours_i) / log(1 + max_hours) × 100%
```
- 近期任务间距天然放大，远期任务间距压缩
- 当所有任务集中在同一天内时，退化为近似线性分布
- position 范围 0%~100%，映射到时间轴长度

### 自动换行机制
- 当相邻两个节点的像素间距 < 80px 时，判定为拥挤
- 将时间轴分为多行，每行容纳若干节点
- 行与行之间用弧形连接线（半圆弧，stroke:var(--border-light), stroke-dasharray:4,4）衔接
- 每行均保持从左到右的时间递增方向

### 过期任务折叠区
```css
.expired-zone {
    background: rgba(165,90,90,0.08);
    border: 1px dashed var(--border-light);
    padding: 0.8rem 1.2rem;
    margin-right: 1.5rem;
    cursor: pointer;
}
.expired-zone .zone-title {
    font-family: 'Noto Sans SC', sans-serif;
    font-size: 0.75rem;
    color: var(--text-dim);
    letter-spacing: 0.2em;
}
.expired-task-name {
    color: var(--text-muted);
    text-decoration: line-through;
}
.expired-duration {
    font-size: 0.7rem;
    color: var(--color-c);  /* 赤墨 */
}
```
- 位于时间轴最左侧（Now标记之前）
- 默认折叠：仅显示「已过期 ×N」标题，点击展开查看详情
- 展开后竖排列出各过期任务，附删除线和过期时长

## 文件监听模式（自动启动）

### 自动启动机制

触发 skill 时，系统会自动：
1. 检查是否已有监听器在运行
2. 若无，在后台启动监听器
3. 若有，复用现有监听器

### 监听行为

- ✅ **自动检测**：Task.txt 被保存时自动触发重新生成
- 🔄 **防抖处理**：1秒内多次修改只触发一次
- 📄 **报告位置**：`C:\Users\lenovo\.craft-agent\workspaces\my-workspace\sessions\{日期}\data\DDL_Report.html`

### 停止监听

监听器会在后台持续运行，如需停止：
1. 打开任务管理器
2. 找到 python.exe 进程（运行 ddl_watcher.py）
3. 结束进程

或重启电脑后不会自动重启，直到下次触发 skill。

## 文件格式

任务文件位置：`C:\Users\lenovo\Desktop\Task.txt`

格式：
```
<任务名>--<月/日>
```

示例：
```
机械原理作业--4/8
计算机绘图&autocad--4/9
互换性实验报告--4/8
```

## 分类颜色说明

| 分类 | 时间范围 | 颜色 | 紧急程度 |
|------|----------|------|----------|
| A类 | 9-12周 或 4-7天 | 墨蓝 #4a6fa5 | 宽松 |
| B类 | 3-9周 或 2-4天 | 墨绿 #5a7a5a | 中等 |
| C类 | 1-3周 或 1-2天 或 4-24小时 | 赤墨 #a55a5a | 紧急 |
| 超出范围 | >12周 / <4小时 / 已过期 | 淡墨 #6a6a6a | 特殊 |

## 输出文件

- **数据文件**：`data/tasks_data.json` - 结构化任务数据
- **HTML报告**：`data/DDL_Report.html` - 「墨」风格可视化进度报告

## 依赖

- Python 3.x
- watchdog (文件监听，可选)
