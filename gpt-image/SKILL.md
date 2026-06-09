---
name: gpt-image
description: "Use this skill whenever a user asks to generate, create, draw, render, or edit images — posters, typography, Chinese text, UI mockups, diagrams, scientific figures, photography, illustration, and more. This skill outputs crafted prompts ready to paste into any image generation platform. It does NOT call any API — it produces prompts, platform parameters, and brief notes. Analyze the user's request, search the bundled Reference Gallery/craft files for matching design patterns, confer on direction when useful, then output a polished prompt package."
compatibility: "No dependencies. Pure text output. Works with any image generation platform."
metadata: {"openclaw":{"homepage":"https://github.com/wuyoscar/gpt_image_2_skill"}}
---

# gpt-image — Prompt Crafting Skill

Pure prompt-crafting skill. Outputs polished text-to-image prompts plus platform parameters and notes. Does **not** call any API or execute any CLI — the user pastes the output into their tool of choice.

## Operating loop

1. **Classify request**: `generate`, `edit`, or `inpaint`; identify asset type, aspect ratio, exact text, style, reference image count, safety constraints, and target platform (if specified).
2. **Search references first**: open `references/gallery.md`; load the closest `references/gallery-<category>.md` file(s). Read actual `**Prompt**` text before choosing a pattern.
3. **Refine with craft**: load `references/craft.md` for dense text, diagrams, UI, data visualization, multi-panel layouts, weak prompts, or no close gallery match.
4. **Confer when useful**: before ambiguous/high-effort prompt construction, present 1–3 matched directions plus planned aspect ratio/style; ask at most one concise question. Skip discussion for precise "generate now" requests.
5. **Output the prompt package**: see Output Format below.
6. **Suggest**: offer one concise refinement direction if useful (e.g. "try landscape for more breathing room").

Fast path: precise prompt + explicit "generate now" → quick reference/craft check, then output.

## Output format

Every response follows this three-part structure:

```
## 🎨 Prompt

[The full text prompt, ready to copy-paste]

## ⚙️ Platform Parameters

| Platform | Settings |
|----------|----------|
| Midjourney | --ar 16:9 --v 6 --style raw ... |
| DALL·E 3  | 1792x1024, quality: hd ... |
| Stable Diffusion | Steps: 30, Sampler: DPM++ 2M, CFG: 7, Negative: ... |
| 通义万相   | 尺寸: 16:9, 风格: ... |
| 文心一格   | 比例: 16:9, 画质: 高清 ... |

## 📝 Notes

[1–3 sentences explaining why key prompt choices were made, which reference was remixed, and one refinement suggestion]
```

**Platform granularity rule:**
- If the user did NOT specify a platform → output parameters for all five platforms.
- If the user specified a platform → output ONLY that platform's parameters (but still include the universal prompt and notes).

## Mode routing

| Mode | Trigger | Prompt focus |
|---|---|---|
| Text-to-image | User wants a new image from scratch | Full scene description, style anchors, composition, exact text in quotes |
| Reference edit | User provides reference image(s) to modify | Describe target transformation first, then explicitly list what must stay unchanged (identity, layout, text, positions) |
| Inpaint | User wants localized changes on an existing image | Describe the region to change + the desired result; specify what outside the region must remain identical |

### Edit mode invariants (critical)

When constructing an edit prompt, always include:
- The target transformation first
- What must be preserved: "keep everything else the same", "maintain original composition", "preserve all text exactly"
- If multiple references: identify each by role ("Image 1: subject photo, Image 2: style reference")

### Inpaint mode specifics

- Describe the masked region boundaries
- Specify the desired fill content
- State what outside the mask must be untouched

## Platform format reference

### Midjourney

```
[prompt] --ar <ratio> --v 6 --style raw --s <0-1000> --c <0-100>
```

Key parameters: `--ar` (aspect ratio), `--v` (version), `--style raw` (photorealism), `--s` (stylize), `--c` (chaos), `--no` (negative), `--iw` (image weight for edits).

### DALL·E 3 (via ChatGPT / API)

```
[prompt]

Size: 1024x1024 | 1792x1024 | 1024x1792
Quality: standard | hd
Style: vivid | natural
```

DALL·E 3 understands natural language well. Put layout instructions at the start. Wrap exact text in quotes.

### Stable Diffusion (SDXL / ComfyUI / AUTOMATIC1111)

```
Positive: [prompt]
Negative: [negative prompt]
Steps: 20-40 | Sampler: DPM++ 2M Karras | CFG: 5-9 | Size: 1024x1024
```

SD needs explicit negatives (deformed anatomy, extra limbs, blurry, text artifacts). Photorealism needs quality tags like `8k, highly detailed, sharp focus`.

### 通义万相 (Tongyi Wanxiang)

```
提示词：[Chinese prompt works well]
尺寸：1:1 | 16:9 | 9:16
风格：<风格名称>
```

Chinese prompts often perform better than translated English. Supports built-in style presets.

### 文心一格 (Wenxin Yige)

```
画面描述：[Chinese prompt]
比例：1:1 | 16:9 | 9:16
画质：标清 | 高清 | 超清
风格：<风格名称>
```

Chinese-native. Best results with Chinese prompts. Has style library for quick selection.

## Quality & size guidance

Embed these in the prompt itself — they inform prompt construction, not API parameters:

**Quality tiers for prompt writing:**
- **Draft/exploration**: shorter prompts, relaxed constraints, good for brainstorming variants
- **Standard**: balanced detail, normal style anchoring
- **High/Presentation**: maximum detail, multi-clause structure, exact text requirements, explicit avoid-lists, required for Chinese text, diagrams, posters, UI, paper figures

**Aspect ratio guidance:**

| Use case | Ratio | Orientation |
|---|---|---|
| Social media | 1:1 | Square |
| Poster/portrait/mobile | 2:3 / 9:16 | Portrait / Tall |
| Landscape/photo/widescreen | 16:9 | Landscape / Wide |
| Print/paper figure | 3:2 | 2K |
| Story/banner | 9:16 | Tall |

## Reference loading

- `references/gallery.md`: routing index for the 162-prompt Reference Gallery Atlas. Load first.
- `references/gallery-*.md`: concrete prompts, previews, paths, metadata, attribution. Load 1 category for normal requests; 2–3 for hybrids.
- `references/craft.md`: prompt-craft checklist. Load for prompt repair, exact text, UI/data/diagram grammar, edit invariants, and multi-panel consistency.
- `references/openai-cookbook.md`: model capability reference. Load for platform behavior questions.

Reference loading policy: load the smallest useful slice; never load all category files by default.

## Verification

- Confirm mode (generate / edit / inpaint) before constructing prompt.
- For edit/inpaint: remind the user which reference images they'll need to upload.
- Output is complete when all three sections (Prompt, Platform Parameters, Notes) are present.
- All Chinese text in prompts must be wrapped in quotes and labeled as exact required copy.
- If the user specified a platform, verify parameters match that platform's supported ranges.

Preserve `Curated` vs `Author + Source` metadata when adapting examples.
