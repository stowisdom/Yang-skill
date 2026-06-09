---
name: information-showing-yang-007
description: Collect the text and format it according to the process, without adding to, deleting from, or altering the original content; the goal is simply to reduce visual and cognitive processing strain on the user. Triggered when the user enters "showing<text to be processed>"
---

#work
##Step1
用户输入待处理文本（.txt或.md格式）

##step2可视化
###绝对禁止：对原文进行增删改，只是按以下规则对文本内容进行可视化处理，辅助阅读
Visual Design System · Napkin Dark
参考实现见本 skill 目录下 "reference\cangjingzhi.html"，以下规则是对该实现的语义提炼，生成新页面时须同时满足。

主题与氛围
深色有机主题，背景色取墨绿底黑（#0c0c0a），卡片面与背景仅有微差（#131310），制造悬浮感而非强对比。整体气质：克制、呼吸感、线条感、高级感。禁止使用纯黑 #000000 或纯白 #ffffff。

字体系统
正文使用 Noto Serif SC（weight 300），衬线体，轻盈不厚重。标题与关键词使用 Playfair Display（italic），两者同为衬线但气质有别，形成内部层次。
行高固定为 2em，段间距同为 2em，使行与行之间始终保留约一个空行高度的呼吸空间。

三层概念标注系统
模型输出的每句话都必须用<>，()，，{}进行对重要语义单元的框定强调，减少文字处理的视觉负荷（eg：我们必须明白<无明>是种种困惑的<起始>）

正文中的词语按语义权重分为三层，通过字号、字色、符号共同完成视觉框定：
第一层 「」——中等概念，指理论体系、规律名称、思想流派、书名等抽象概念名。使用 Playfair Display italic 600，字号 1.55rem，铜金色 #b08a4a，「」括号透明度 0.65。它应当明显浮出正文平面。
第二层 <>——细节实体，指人名、地名、具体工具名、章节名等可枚举的具体事物。使用正文同号（1rem），青瓷绿 #7ab8a0，<> 括号透明度 0.45，词本身清晰可读，符号略弱于词。
第三层——正文本身，亚麻白 #c8c3b6，weight 300，承载叙述与逻辑，不加任何符号框定。
三层之间不得混用：抽象概念不用 <>，具体人名不用 「」。

色彩系统
用途	色值	说明
大背景	#0c0c0a	墨绿底黑
卡片面	#131310	与背景微差
正文色	#c8c3b6	亚麻白
「」关键词	#b08a4a	铜金
<>关键词	#7ab8a0	青瓷绿
引言线/脚注线	#8b3a3a	酒红
折痕线	#4a4232	暖米灰，两端渐变透明
辅助弱化文字	#5a5a50	引言块文字色
禁止引入灰色系（如 #999、#aaa）作为任何可读文字的颜色。

餐巾纸（Napkin）布局结构
每张餐巾纸是一个独立的 <article class="napkin"> 卡片，代表一个完整的文意单元（如：起源 / 机制 / 映射）。卡片之间间距 3px，模拟叠放的纸张。
每张卡片内部结构依次为：
	1. 顶部折痕线——横贯全宽、两端渐变透明的暖米灰线（::before 伪元素实现），模拟餐巾纸折叠痕迹
	2. 右上角编号——No. 01 格式，极淡色，不干扰阅读
	3. 斜体标题——Playfair Display，1.5rem，近白色
	4. 正文段落——含三层标注系统
	5. 引言块（可选）——酒红左线，font-style: italic，弱化色
	6. 内部分割线（可选）——同折痕线样式，opacity: 0.7
	7. 底部脚注——酒红顶线，Step 0X · 主题词，极小字号大间距字母
按文意将内容拆分为 3 张餐巾纸，每张对应一个叙述步骤，不得将所有内容堆入单张卡片。

禁止项
	• 禁止使用无衬线字体作为正文
	• 禁止使用纯色直线作为分割线（须两端渐变）
	• 禁止将人名、工具名放入「」，禁止将理论名放入 <>
	• 禁止在同一段落中出现超过 3 个标注词，避免视觉噪声
	• 禁止使用灰色系作为可读文字颜色
	
#step3
输出HTML到指定工作目录，如果没有，向用户确认工作目录路径
