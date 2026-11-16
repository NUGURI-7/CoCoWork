---
name: pdf
description: "制作和处理 PDF 文件。用户要做产品单页、宣传页、报告等 PDF，或要读取、提取文字和表格、合并、拆分已有 PDF 时使用。新建的 PDF 一律套用 CoCoWork 品牌页面（页眉 Logo、页脚页码、品牌色、中文字体）。"
license: Complete terms in LICENSE.txt
---

# PDF 制作与处理

| 任务 | 做法 |
|---|---|
| **新建** PDF | 写一个 Python 脚本，用 `brand/brand_pdf.py` 生成 —— 见下方「品牌页面（必须）」 |
| **读取**文字和表格 | `pdfplumber` |
| **合并 / 拆分 / 旋转** | `pypdf` |

路径里的尖括号是占位符，写成绝对路径：`<本 skill 目录>` 是本说明书所在目录，`<交付区>` 的实际位置见系统提示「文件放哪」那节。写进交付区的文件会自动交给用户。

## 品牌页面（必须）

新建 PDF **一律**用 `brand/brand_pdf.py` 的 `build_pdf()`：A4 版面，每页自动带页眉（Logo + CoCoWork）和页脚（资料密级 + 「第 x 页 / 共 y 页」），中文字体已注册（嵌入文泉驿正黑，环境里没有时退回 STSong-Light），风格与 PPT 一致。不要自己画页眉页脚，也不要用 reportlab 自带的 Helvetica 等字体 —— 它们不含中文，会显示成方块。

```python
import sys
sys.path.insert(0, "<本 skill 目录>/brand")
from brand_pdf import CONTENT_WIDTH, build_pdf, bullets, callout, figure, hero, stat_row, styles, table
from reportlab.platypus import KeepTogether, Paragraph, Spacer

st = styles()
story = [
    *hero("CoCoWork 产品单页", "企业内部 AI 业务能力门户……", kicker="PRODUCT OVERVIEW", image="<工作区>/pdf_cover.png"),
    stat_row([{"value": "3 分钟", "label": "产出方案初稿"}, {"value": "100%", "label": "调用全程可追溯"}]),
    Spacer(1, 16),
    KeepTogether([Paragraph("核心能力", st["H1"]), bullets(["<b>合同初审：</b>逐项核对签约对象、报价与条款"])]),
    KeepTogether([Paragraph("版本与价格", st["H1"]), table([["版本", "价格（元/年）"], ["标准版", "48,000"]])]),
    Spacer(1, 16),
    callout("联系我们", "预约演示或试用……"),
]
build_pdf("<交付区>/产品单页.pdf", story, title="CoCoWork 产品单页", classification="对外资料")
```

| 函数 | 用途 |
|---|---|
| `hero(title, subtitle, kicker, image)` | 首屏横幅：深绿底，左侧标题，`image` 给图片路径时右半边放配图并自动渐变衔接；返回列表，用 `*hero(...)` 展开 |
| `stat_row(items)` | 2–4 个大数字卡片，第一个品牌色底 |
| `callout(title, text)` | 浅绿底提示框 |
| `figure(path, caption, width)` | 配图，按原比例缩放，`width` 单位 pt，默认版心宽度；返回列表 |
| `table(rows, col_widths)` | 第一行表头（品牌色底白字），隔行浅绿底，单元格自动换行，跨页重复表头；`col_widths` 单位 pt，合计不超过 `CONTENT_WIDTH` |
| `bullets(items)` | 品牌色项目符号列表 |
| `styles()` | `Title`、`Subtitle`、`H1`、`H2`、`Body`、`Small`、`Center`、`TableHead`、`TableCell`；需要变体时 `ParagraphStyle("X", parent=st["Body"], ...)` 派生，不要另指定字体 |

- **配图**：调用 `generate_image(prompt, filename, aspect)` 工具生成，返回路径直接传给 `hero(image=…)` 或 `figure()`。**`filename` 一律以 `pdf_` 开头**（如 `pdf_cover`）：别的成员可能同时在生图，同名会互相覆盖。提示词开头写「真实摄影照片，商业杂志质感」，人物放在画面右侧（左边要叠标题），结尾写「满版构图，无边框，画面中不要出现任何文字、logo 或水印」，有屏幕时加「屏幕背对镜头」。生成失败就不传 `image`，横幅会改用同心圆装饰。
- **数字只能来自用户给的资料或资料员的简报**：示例代码里的数字只是演示，不要照抄；手里没有可靠数字时，不要用数据卡片，改用图标列表或要点。
- 段落文字里的 `&`、`<`、`>` 要写成 `&amp;`、`&lt;`、`&gt;`，加粗用 `<b>`，换色用 `<font color="#2F6B53">`。
- 上下标用 `<sub>`、`<super>` 标记，不要用 ₂、² 这类 Unicode 上下标字符（字体里没有，会显示成黑块）。
- 一页纸的单页要控制内容量：放不下就精简文字，不要缩小到 9pt 以下。用 `KeepTogether([...])` 避免小标题和它下面的内容被分到两页。

## 检查（必须）

生成后先用 pdfplumber 核对页数和文字：

```python
import pdfplumber
with pdfplumber.open("<交付区>/产品单页.pdf") as pdf:
    print(len(pdf.pages))
    for page in pdf.pages:
        print(page.extract_text())
```

确认页数符合预期（单页就是 1 页）、内容没有缺失、没有乱码。

再看排版：把每页渲染成 PNG，路径传给 `review_pages(image_paths=[…])` 工具（一次最多 12 页），它逐页返回问题清单。只改属实的问题（压字、遮挡、空得失衡）。

```python
import pdfplumber
with pdfplumber.open("<交付区>/产品单页.pdf") as pdf:
    for i, page in enumerate(pdf.pages, 1):
        page.to_image(resolution=110).save(f"<工作区>/pdf_preview_{i}.png")
```

预览图放在工作区，不要放进交付区。

**什么时候算做完**（步数有限，做完就交付，不要继续打磨）：

- 页数、文字核对无误，看图那一轮改完重新生成，就交付。
- 看图只用 `review_pages` 工具，**只看一轮**，只改它指出的明显问题，改完重新生成就交付，不再看第二遍。
- 不要用 `read_file` 读图片，不要翻依赖库的源码、不要解压生成的文件查内部结构。
- 不影响阅读的小瑕疵（列表编号样式、几像素的偏差、措辞润色）不追。

## 读取已有 PDF

```python
import pdfplumber

with pdfplumber.open("input.pdf") as pdf:
    for page in pdf.pages:
        print(page.extract_text())
        for t in page.extract_tables():
            print(t)
```

扫描件（整页是图片）提取不到文字，如实告诉用户需要文字版 PDF。

## 合并、拆分、旋转

```python
from pypdf import PdfReader, PdfWriter

writer = PdfWriter()
for path in ["a.pdf", "b.pdf"]:
    for page in PdfReader(path).pages:
        writer.add_page(page)
with open("merged.pdf", "wb") as f:
    writer.write(f)

reader = PdfReader("input.pdf")            # 拆分：每页单独存
for i, page in enumerate(reader.pages, 1):
    w = PdfWriter()
    w.add_page(page)   # 需要旋转时先 page.rotate(90)
    with open(f"page_{i}.pdf", "wb") as f:
        w.write(f)
```

## 依赖

`reportlab`、`pypdf`、`pdfplumber`（pip）· 中文字体 `fonts-wqy-zenhei`（系统包，缺失时自动退回 PDF 标准中文字体）
