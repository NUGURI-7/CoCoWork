---
name: docx
description: "制作、读取、修改 Word 文档（.docx / .dotx）。用户要写方案、报告、说明书、通知、函件等 Word 文件，或要改已有的 Word 文档时使用。新建的文档一律套用 CoCoWork 品牌模板（页眉 Logo、页脚页码、品牌色标题、中文字体）。不用于 PDF、表格。"
license: Complete terms in LICENSE.txt
---

# DOCX 制作、修改与读取

`.docx` 是一个装着 XML 文件的 ZIP 包。脚本路径都相对于本 skill 目录，执行时写成绝对路径。

| 任务 | 做法 |
|---|---|
| **新建**文档 | 写一个 Node 脚本，用 `brand/brand.js` 生成 —— 见下方「品牌模板（必须）」 |
| **修改**已有文档 | 解包 → 改 `word/document.xml` → 重新打包（docx-js 打不开已有文件），见「修改已有文档」 |
| **读取**内容 | `pandoc -t markdown file.docx` |

路径里的尖括号是占位符，写成绝对路径：`<本 skill 目录>` 是本说明书所在目录，`<交付区>` 的实际位置见系统提示「文件放哪」那节。写进交付区的文件会自动交给用户。

## 品牌模板（必须）

新建文档**一律**用 `brand/brand.js` 的 `createDocument()`：A4 版面、页眉（Logo + CoCoWork + 文档标题）、页脚（资料密级 + 「第 x 页 / 共 y 页」）、中文字体（标题微软雅黑、正文宋体）和标题样式都已定好，风格与 PPT 一致。不要自己写页眉页脚、改字体或配色。

```js
const brand = require("<本 skill 目录>/brand/brand.js");

const doc = brand.createDocument({
  title: "CoCoWork 产品方案",
  cover: {                                         // 不要封面就不传
    kicker: "PRODUCT PROPOSAL",                    // 标题上方的英文小标签，可省
    subtitle: "企业内部 AI 业务能力门户",
    image: "<工作区>/docx_cover.png",                    // generate_image 生成的封面图，可省
    date: "2026 年 11 月",
  },
  classification: "对外资料",                       // 页脚左侧，如「内部资料」
  children: [
    brand.heading("一、方案概述", 1),
    brand.paragraph("正文段落，首行自动缩进两字。"),
    brand.callout("核心价值", "一段结论或要点摘要，浅绿底提示框。"),
    brand.heading("二、上线效果", 1),
    brand.statRow([{ value: "3 分钟", label: "产出方案初稿" }, { value: "100%", label: "调用可追溯" }]),
    brand.figure("<工作区>/team.png", "图 1  协作方式", { widthRatio: 0.85 }),
    brand.bullets(["要点一", "要点二"]),                 // { numbered: true } 改成 1. 2. 3.
    brand.table([["版本", "说明"], ["标准版", "……"]], [2400, brand.CONTENT_WIDTH - 2400]),
  ],
});
await brand.save(doc, "<交付区>/产品方案.docx");
```

| 函数 | 用途 |
|---|---|
| `heading(text, level)` | 一到三级标题，品牌色，进目录 |
| `paragraph(text, options)` | 正文；`text` 可以是 `[{ text: "加粗前缀：", bold: true }, { text: "说明" }]`；`{ indent: false }` 取消首行缩进 |
| `bullets(items, { numbered })` | 项目符号 / 编号列表 |
| `table(rows, columnWidths)` | 第一行表头（品牌色底白字），隔行浅绿底；列宽单位 DXA，合计等于 `brand.CONTENT_WIDTH`，不传则均分 |
| `callout(title, text)` | 浅绿底提示框，放结论、摘要 |
| `statRow(items)` | 2–4 个大数字卡片，第一个品牌色底（与 PPT 数据页一致） |
| `figure(path, caption, { widthRatio })` | 配图（PNG / JPG），按原比例缩放到版心宽度 |

- **配图**：调用 `generate_image(prompt, filename, aspect)` 工具生成，返回图片路径后直接传给 `cover.image` 或 `figure()`。**`filename` 一律以 `docx_` 开头**（如 `docx_cover`）：别的成员可能同时在生图，同名会互相覆盖。封面图用 `16:9`；提示词开头写「真实摄影照片，商业杂志质感」，结尾写「满版构图，无边框，画面中不要出现任何文字、logo 或水印」，有屏幕时加「屏幕背对镜头」。方案类文档配 1–2 张图即可，生成失败就不配。
- **数字只能来自用户给的资料或资料员的简报**：示例代码里的数字只是演示，不要照抄；手里没有可靠数字时，不要用数据卡片，改用图标列表或要点。
- `children` 里可以混放 `bullets()`、`figure()` 返回的数组、`table()` 和自己用 docx-js 写的 `Paragraph`。
- 自己写 `TextRun` 时不要指定字体，跟随文档默认字体。

## 用 docx-js 补充内容时的注意事项

品牌模块没覆盖的元素（目录、分页等）直接用 docx-js 写，`docx` 已预装，直接 `require`。容易出错的地方：

- **Tables need dual widths:** set `columnWidths` on the table AND `width` on every cell, both in `WidthType.DXA` (PERCENTAGE breaks in Google Docs). Column widths must sum to the table width.
- **Table shading:** use `ShadingType.CLEAR`, never `SOLID` (renders black).
- **Lists:** 用 `brand.bullets()`；不要直接写 `•` 字符。
- **`ImageRun` requires `type:`** (`"png"`, `"jpg"`, …).
- **`PageBreak` must be inside a `Paragraph`.**
- **Never use `\n`** — use separate `Paragraph` elements.
- **TOC:** headings must use built-in `HeadingLevel.*`; custom heading styles need `outlineLevel` set or they won't appear.
- **Don't use a table as a horizontal rule** — use a paragraph bottom border instead.
- **Dot-leader / right-aligned-on-same-line:** use `PositionalTab` (`alignment: PositionalTabAlignment.RIGHT`, `leader: PositionalTabLeader.DOT`) inside a `TextRun`, not literal `.` or space padding.

## 检查（必须）

不要把文件渲染成图片检查，这个环境里看不了图。写完跑一遍官方校验：

```bash
python scripts/office/validate.py output.docx
```

再用 `pandoc -t markdown output.docx` 核对内容有没有缺、顺序对不对。校验报错就改生成脚本重新生成。

**什么时候算做完**（步数有限，做完就交付，不要继续打磨）：

- 校验通过、内容核对无缺漏，就交付。
- 不要用 `read_file` 读图片，不要翻依赖库的源码、不要解压生成的文件查内部结构。
- 不影响阅读的小瑕疵（列表编号样式、几像素的偏差、措辞润色）不追。


## 修改已有文档

不支持旧版 `.doc`，请用户另存为 `.docx` 后再发。

```bash
unzip -q doc.docx -d unpacked/
find unpacked -type l -delete   # 删掉符号链接 —— 外部来的 docx 不可信
python scripts/merge_runs.py unpacked/   # 合并碎片化的文本片段，否则看得见的句子在 XML 里搜不到
# 原地改 unpacked/word/document.xml —— 不要格式化或美化 XML
(cd unpacked && rm -f ../out.docx && zip -XrD ../out.docx .)
python scripts/office/validate.py out.docx --original doc.docx   # XSD 校验；--auto-repair 可修常见问题
```

Word 会把一段文字拆成很多个 `<w:r>`（修订号、拼写检查标记），所以文档里看得到的一句话，在 XML 里常常不是连续的字符串。`merge_runs.py` 把相邻、格式相同的片段合并，不改内容和显示效果；也可以直接处理 `.docx`（`python scripts/merge_runs.py doc.docx -o merged.docx`）。

修改时保留原文档的页眉页脚和样式；新增段落复制相邻段落的 `<w:pPr>`，保持格式一致。

## 依赖

`docx`（npm，已预装）· `pandoc` · `lxml`、`defusedxml`（pip，供 validate / merge_runs 使用）
