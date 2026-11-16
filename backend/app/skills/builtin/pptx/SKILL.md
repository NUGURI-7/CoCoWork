---
name: pptx
description: "制作、读取、修改 PowerPoint 演示文稿（.pptx / .potx）。用户要做 PPT、幻灯片、演示文稿、汇报材料、产品介绍，或要改已有的 PPT 时使用。新建演示文稿逐页设计成 SVG 再转成原生可编辑的 PPTX，可配 AI 生成的照片，品牌 Logo、页脚、页码自动加上。"
license: Complete terms in LICENSE.txt
---

# PPTX 制作、修改与读取

| 任务 | 做法 |
|---|---|
| **新建**演示文稿 | 每页手写一张 SVG → 一条命令收尾（盖品牌、检查、渲染）→ 看图自查 → 一条命令导出原生 PPTX，见「新建演示文稿」 |
| **修改**已有演示文稿 | 解包 → 改 `ppt/slides/slideN.xml` → 重新打包，见「修改已有演示文稿」 |
| **读取**内容 | `python3 <本 skill 目录>/scripts/slide_text.py deck.pptx`（每页一段，带 `<!-- Slide number: N -->` 标记） |

路径里的尖括号是占位符，执行时写成绝对路径：`<本 skill 目录>` 是本说明书所在目录；`<工作区>` 是沙箱里的工作目录（生图工具也把图存在这里）；`<交付区>` 的实际位置见系统提示「文件放哪」那节，写进交付区的文件会自动交给用户。

## 新建演示文稿

转换引擎取自开源项目 PPT Master（MIT）：SVG 里的矩形、圆、线、文字、图片、图标都会变成 PowerPoint 原生对象，用户拿到后每个元素都能单独编辑。页面完全由你设计，下面的规范只管「转换器认什么」和「品牌是什么样」。

**步数有限，能合并的工具调用一律合并**：多张配图在同一次回复里一起生成；图标一条命令全部复制；几页 SVG 放进一条命令一起写；收尾和导出各只用一条命令。整套流程控制在 15 次工具调用左右。

### 第 1 步：规划（写 SVG 之前定完）

- **页数与每页一句话**：每页只讲一件事，先写出每页的核心信息。产品介绍常见结构：封面 → 痛点 → 能力 → 章节页 → 数据 → 流程 → 对比 → 结尾。
- **每页的版式**：相邻两页不用同一种版式。可选：照片铺满 + 渐变遮罩、左文右图、等宽卡片网格、大数字卡片、横向时间线 / 流程、左右对比、居中大字。
- **哪些页配图**：封面必配；内容页里 1–2 页配图最好看，不要每页都配。

### 第 2 步：建项目

```bash
mkdir -p <工作区>/deck/svg_output <工作区>/deck/images
```

页面放 `deck/svg_output/`，文件名按顺序编号：`01_cover.svg`、`02_why.svg` …… 导出时按文件名顺序成页，目录里不要留别的 SVG。

### 第 3 步：配图（调用 `generate_image` 工具）

```
generate_image(prompt="…", filename="ppt_cover", aspect="16:9")
→ 已生成 /workspace/ppt_cover.png（1280×720）
```

所有配图在同一次回复里一起调用，不要一张一张等。拿到路径后一条命令全部移进项目：`mv /workspace/ppt_cover.png /workspace/ppt_team.png <工作区>/deck/images/`，页面里写 `href="../images/ppt_cover.png"`。**文件名一律以 `ppt_` 开头**：别的成员可能同时在生图，同名会互相覆盖。工具返回失败就不配这张图，用色块和图标排版，不要反复重试。

提示词按下面写，否则容易出卡通风、屏幕上的乱码英文、自带边框：

- 开头写 **「真实摄影照片，商业杂志质感」**，再写场景、人物、光线；色调写「偏墨绿与暖白」以贴合品牌色。
- 结尾固定写 **「满版构图，无边框，画面中不要出现任何文字、logo 或水印」**；有电脑、平板、大屏时加「屏幕背对镜头」。
- 要叠标题的图（封面、章节页）写明留白方向，如「人物位于画面右侧三分之一，左侧大面积虚化背景，适合叠加标题文字」。
- 比例：铺满整页用 `16:9`；左文右图的竖幅图用 `3:4`；方形卡片用 `1:1`。

### 第 4 步：图标

图标库是 Tabler 实心图标（1055 个）。规划时就把整套要用的图标定下来，一条命令全部复制进项目；拿不准名字时用 `--search` 查一次，不要逐个试。页面里用 `<use data-icon>` 引用：

```bash
python3 <本 skill 目录>/scripts/add_icons.py --search chart
python3 <本 skill 目录>/scripts/add_icons.py <工作区>/deck message-chatbot file-text database shield-check
```

```xml
<use data-icon="tabler-filled/database" x="108" y="240" width="32" height="32" fill="#2F6B53"/>
```

### 第 5 步：逐页写 SVG

`<本 skill 目录>/brand/examples/` 里有 8 页示例（就是一套产品介绍）：`01_cover` 封面照片 + 遮罩、`02_why` 左文右图、`03_capabilities` 图标卡片网格、`04_section` 章节页、`05_results` 大数字、`06_workflow` 流程、`07_compare` 左右对比、`08_ending` 结尾。只读和你要用的版式对应的两三页，照它的写法和配色来，不要全部读一遍。

写页面时用一条命令写多页，每条命令写 3–4 页：

```bash
cat > <工作区>/deck/svg_output/01_cover.svg <<'EOF'
<svg …>…</svg>
EOF
cat > <工作区>/deck/svg_output/02_why.svg <<'EOF'
<svg …>…</svg>
EOF
```

**数字只能来自用户给的资料或资料员的简报**：样例里的「3 分钟」「100%」只是演示排版用的，不要照抄；手里没有可靠数字时，不要用数据卡片，改用图标列表或要点。

**根节点**（每页一样，`data-pptx-page-role` 按页填 `cover` / `toc` / `section` / `content` / `ending`；深色底的页加 `data-brand-tone="dark"`）：

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" width="1280" height="720"
     font-family="Microsoft YaHei" lang="zh-CN" data-pptx-page-role="content">
  <rect id="bg" data-pptx-role="background" x="0" y="0" width="1280" height="720" fill="#F4F7F5"/>
  …
</svg>
```

**品牌**

| 用途 | 颜色 |
|---|---|
| 品牌绿：标题强调、主色块、图标 | `#2F6B53` |
| 深绿：深色页底、遮罩 | `#1F4A39` / `#163828` |
| 浅绿：深色底上的次要文字 | `#CFE3D8` |
| 图标底圆、浅色块 | `#E3EEE8` |
| 内容页底色 | `#F4F7F5` |
| 正文 / 次要文字 | `#1E2622` / `#5F6B65` |
| 卡片描边 | `#DCE7E1` |
| 点缀金（短横线、最后一个节点，少量用） | `#C9A86A` |

- 字体只用 `Microsoft YaHei`（微软雅黑），正式文书风格可用 `SimSun`（宋体），写在根节点上，别处不再写。
- **Logo、页脚品牌名、页码不要自己画**，第 6 步的脚本会加。为它们留出位置：右上角 `x 1160–1256, y 24–96` 不放内容（封面左上角 `x 64–290, y 48–92` 不放内容）；内容页所有内容在 `y ≤ 652` 以内。

**字号**（1280×720 画布，单位 px）

| 元素 | 字号 |
|---|---|
| 封面标题 | 56–64 粗体 |
| 页面标题 | 36–40 粗体，标题上方可加 15px 英文小标签（`letter-spacing="3"`） |
| 大数字 | 64–80 粗体 |
| 卡片 / 要点标题 | 22–24 粗体 |
| 正文 | 16–18，不小于 15 |
| 注释 | 13–15 |

汉字宽度约等于字号：18px 的一行 20 个字约占 360px。先写好文字，再按「字数 × 字号」定区块宽度。

**转换器的硬规则**（违反了检查会报错）

- 每个内容单元（标题区、一张卡片、一个流程节点）包一个顶层 `<g id="唯一名字" data-pptx-bounds="x y 宽 高">`，bounds 是这个单元占的区域。**各顶层分组的区域不能重叠，不能超出画布**；装饰性的分组加 `data-pptx-role="decoration"`。
- 多行文字用一个 `<text>`，第一行直接写，后面每行一个 `<tspan x="同一个 x" dy="行距">`；行距取字号的 1.5 倍左右。
- 颜色用大写 `#RRGGBB`；透明度用 `opacity` / `fill-opacity`；渐变只用两到三个色标的 `linearGradient`（照片上的渐变遮罩就是这样做的）。
- 图片：`<image href="../images/x.png" x y width height preserveAspectRatio="xMidYMid slice"/>`。要圆角就在 `<defs>` 里放一个和图片框一样大的 `<clipPath><rect rx="24"/></clipPath>`，图片上写 `clip-path="url(#…)"`；`clip-path` 只能用在图片上。
- 禁止：`<style>`、`class`、`mask`、`<foreignObject>`、`textPath`、`@font-face`、动画、脚本；`&` `<` `>` 写成 `&amp;` `&lt;` `&gt;`，其他符号（—、·、→）直接写字符，不写 HTML 实体。

**设计要点**

- 每页都要有视觉元素（照片、图标、色块、大数字），不做纯文字页。
- 同类页面的标题位置、字号保持一致；正文左对齐，只有封面 / 结尾 / 时间线节点可以居中。
- 留白比塞满好：区块之间留 24–40px，页面四周留 64px。
- 不要在标题下面加装饰横线，不要沿页面边缘或卡片一侧加装饰色条——这两种是 AI 生成页面最常见的廉价感来源；要突出一张卡片，用品牌绿整卡填充或加深底色。
- 不要每页都用同一种卡片网格；数据页、流程页、对比页、配图页交替出现。

### 第 6 步：收尾并看图（调用 `review_pages` 工具）

```bash
python3 <本 skill 目录>/scripts/finalize.py <工作区>/deck
```

这条命令依次盖品牌（Logo、页脚、页码，同时检查字体）、整理样式、检查、把每页渲染成 PNG，最后打印预览图路径。

- 检查报错时命令停下，输出里每条 `[ERROR]` 写明哪一页、哪个分组越界或重叠、超出多少。改对应 SVG，重新执行这条命令。
- 通过后把打印出的路径一次全部传给 `review_pages(image_paths=[…])`（一次最多 12 页），它逐页返回「第 N 页：……」的问题清单。只改清单里属实的问题（压字、遮挡、空得失衡、对齐）。
- **看图只做一轮**，改完不再重新看图，直接导出。
- 不要用 `read_file` 读预览图（看图只用 `review_pages`），不要翻引擎源码；不影响阅读的小瑕疵（几像素偏差、措辞润色）不追。渲染用的是沙箱里的替代字体，字形和微软雅黑略有出入，差几像素的问题不用管。

### 第 7 步：导出

```bash
python3 <本 skill 目录>/scripts/finalize.py <工作区>/deck -o <交付区>/产品介绍.pptx
```

重新盖品牌、检查后导出原生 PPTX 并校验，打印「已导出 …」就完成了。报错时按输出改页面后重新执行；不要手改打包后的 XML。

## 修改已有演示文稿

先用 `python3 <本 skill 目录>/scripts/slide_text.py template.pptx` 看清每页有什么，把要放的内容逐段对到模板页上；版式要换着用，不要每段都用同一种「标题 + 要点」页。

```bash
python3 -c "import sys,zipfile; zipfile.ZipFile(sys.argv[1]).extractall('unpacked')" deck.pptx
python3 <本 skill 目录>/scripts/add_slide.py unpacked/ slide2.xml --after slide2.xml   # duplicate a slide (or slideLayoutN.xml); prints the new slide's path
# reorder / delete slides = edit <p:sldIdLst> in ppt/presentation.xml
python3 <本 skill 目录>/scripts/clean.py unpacked/                                     # after deletions: removes orphaned slides, media, rels
# edit slide content in ppt/slides/slideN.xml
(cd unpacked && rm -f ../out.pptx && zip -XrD ../out.pptx .)          # zip from INSIDE the dir; rm first or deleted parts survive
python3 <本 skill 目录>/scripts/office/validate.py out.pptx --original deck.pptx
```

- **Do all structural work — add, delete, reorder — before editing any slide's content.** `add_slide.py` copies a slide file verbatim, so duplicating after you edit clones the edited content; and `clean.py` deletes any slide missing from `<p:sldIdLst>`, including one you just wrote.
- **Never copy a slide file by hand** — `add_slide.py` does every registration a new slide needs and reports what it made (`Created ppt/slides/slide17.xml from slide2.xml`). It also works directly on a file: `add_slide.py deck.pptx slide2.xml -o out.pptx` — **pass `-o`, or it rewrites the input deck in place.** A duplicated slide still *references* its source's chart/SmartArt/embedded-object parts rather than cloning them, so editing one slide's chart changes the other's.
- **If you use `python-pptx`**, three things it won't do: duplicate a slide (its only entry point is `add_slide(layout)`), preserve formatting through `text_frame.text = "..."` (that collapses the paragraph to a single unstyled run — assign `run.text` instead), or read the SVG/EMF most template art uses (`add_picture` raises `UnidentifiedImageError`).
- 不支持旧版 `.ppt`，请用户另存为 `.pptx` 后再发。`.potx` 模板的解包和打包方式与 `.pptx` 相同，输出时保留 `.potx` 扩展名。
- To reuse a template icon or image, duplicate a slide or layout that already contains it.

When filling in a template:

- If you script an XML transform, parse with `defusedxml.minidom` — round-tripping OOXML through `xml.etree.ElementTree` rewrites namespace prefixes and corrupts the deck.
- **Template slots ≠ source items.** If the template shows 4 team members and you have 3, delete the 4th member's entire group (image + text boxes), not just its text — then check for orphaned visuals in QA.
- One `<a:p>` per list item — never concatenate items into a single paragraph. Copy the sibling `<a:pPr>` to preserve spacing, and put `b="1"` on the `<a:rPr>` of titles, section headers, and inline labels (`Status:`, `Owner:`).
- Let bullets inherit from the layout; only add `<a:buChar>`, `<a:buAutoNum>` (numbered), or `<a:buNone>` to override — never a literal `•` in the text.
- Text with leading or trailing spaces needs `xml:space="preserve"` on its `<a:t>`.

修改后检查：

```bash
python3 <本 skill 目录>/scripts/slide_text.py out.pptx | grep -iE "\bx{3,}\b|lorem|ipsum|\bTODO|\[insert|单击此处"
python3 <本 skill 目录>/scripts/office/validate.py out.pptx --original deck.pptx
```

基于模板修改的一定要传 `--original`：模板本身可能就有校验不过的地方，`--original` 以模板为基准，只报你改出来的问题。

## 依赖

已预装，直接用：`python-pptx`、`lxml`、`defusedxml`、`pyyaml`、`skia-pathops`、`uharfbuzz`、`openpyxl`、`xlsxwriter`、`pillow`、`cairosvg`（pip），`libcairo2`、`fonts-wqy-zenhei`（apt）。

## 来源

- `engine/`：PPT Master 的 SVG → PPTX 转换引擎与检查器（MIT），改动见 `engine/NOTICE.md`。
- `icons/tabler-filled/`：Tabler Icons（MIT），见 `icons/THIRD_PARTY_NOTICES.md`。
- `scripts/`（除 `render_pages.py`、`add_icons.py`、`finalize.py`）与本说明书的修改部分：Anthropic skills（Apache 2.0），见 `LICENSE.txt`。
