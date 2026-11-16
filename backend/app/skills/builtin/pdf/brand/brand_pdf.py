"""CoCoWork 品牌 PDF 模块：中文字体、段落样式、每页页眉（Logo + 公司名 + 品牌色横线）与页脚（资料密级 + 页码）。

新建 PDF 一律通过 build_pdf() 生成：

    import sys
    sys.path.insert(0, "<本 skill 目录>/brand")
    from brand_pdf import styles, build_pdf, bullets, table, hero, stat_row, callout, figure
    from reportlab.platypus import Paragraph, Spacer

    st = styles()
    story = [Paragraph("CoCoWork 产品单页", st["Title"]), Paragraph("正文……", st["Body"])]
    build_pdf("<交付区>/产品单页.pdf", story, title="CoCoWork 产品单页")
"""

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as pdfcanvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Flowable, Image, ListFlowable, ListItem, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

COMPANY = "CoCoWork"
BRAND = colors.HexColor("#2F6B53")
BRAND_DARK = colors.HexColor("#1F4A39")
BRAND_DEEP = colors.HexColor("#163828")
BRAND_LIGHT = colors.HexColor("#E3EEE8")
BRAND_TINT = colors.HexColor("#F1F6F3")
BRAND_PALE = colors.HexColor("#CFE3D8")
LINE = colors.HexColor("#DCE7E1")
ACCENT = colors.HexColor("#C9A86A")
TEXT = colors.HexColor("#1E2622")
MUTED = colors.HexColor("#5F6B65")

PAGE_WIDTH, PAGE_HEIGHT = A4
MARGIN_X = 20 * mm
MARGIN_TOP = 26 * mm
MARGIN_BOTTOM = 20 * mm
CONTENT_WIDTH = PAGE_WIDTH - 2 * MARGIN_X

_LOGO = str(Path(__file__).with_name("logo.png"))

# 可嵌入的 TrueType 中文字体（按顺序找第一个存在的）；都没有时退回 PDF 标准中文字体 STSong-Light（不嵌入）
_FONT_CANDIDATES = (
    ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc", 0),
    ("/usr/share/fonts/truetype/wqy/wqy-microhei.ttc", 0),
)
_FONT_NAME = "BrandCJK"
_font: str | None = None


def font() -> str:
    """注册并返回中文字体名。reportlab 自带的 Helvetica 等字体不含中文，直接用会显示成方块。"""
    global _font
    if _font is not None:
        return _font
    for path, index in _FONT_CANDIDATES:
        if Path(path).is_file():
            pdfmetrics.registerFont(TTFont(_FONT_NAME, path, subfontIndex=index))
            _font = _FONT_NAME
            return _font
    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _font = "STSong-Light"
    return _font


def styles() -> dict[str, ParagraphStyle]:
    """品牌段落样式：Title、Subtitle、H1、H2、Body、Small、TableHead、TableCell。中文按字断行。"""
    f = font()
    base = dict(fontName=f, textColor=TEXT, wordWrap="CJK")

    def style(name: str, **overrides) -> ParagraphStyle:
        return ParagraphStyle(name, **{**base, **overrides})

    return {
        "Title": style("Title", fontSize=24, leading=32, textColor=BRAND_DARK, spaceAfter=6),
        "Subtitle": style("Subtitle", fontSize=13, leading=20, textColor=MUTED, spaceAfter=14),
        "H1": style("H1", fontSize=16, leading=24, textColor=BRAND, spaceBefore=12, spaceAfter=6),
        "H2": style("H2", fontSize=13, leading=20, textColor=BRAND_DARK, spaceBefore=8, spaceAfter=4),
        "Body": style("Body", fontSize=10.5, leading=17, spaceAfter=6),
        "Small": style("Small", fontSize=9, leading=14, textColor=MUTED),
        "TableHead": style("TableHead", fontSize=10, leading=14, textColor=colors.white),
        "TableCell": style("TableCell", fontSize=9.5, leading=14),
        "Center": style("Center", fontSize=10.5, leading=17, alignment=TA_CENTER),
    }


def bullets(items: list[str], style: ParagraphStyle | None = None) -> ListFlowable:
    """项目符号列表，符号用品牌色。items 里的字符串支持 <b>、<font color> 等 reportlab 段落标记。"""
    st = style or styles()["Body"]
    return ListFlowable(
        [ListItem(Paragraph(text, st), leftIndent=12) for text in items],
        bulletType="bullet", start="•", bulletColor=BRAND, leftIndent=12, bulletFontSize=10,
    )


def table(rows: list[list[str]], col_widths: list[float] | None = None) -> Table:
    """品牌表格：rows[0] 为表头（品牌色底、白字），隔行浅绿底；单元格内自动换行。col_widths 缺省时均分版心宽度。"""
    st = styles()
    widths = col_widths or [CONTENT_WIDTH / len(rows[0])] * len(rows[0])
    data = [
        [Paragraph(str(v), st["TableHead"] if r == 0 else st["TableCell"]) for v in row]
        for r, row in enumerate(rows)
    ]
    t = Table(data, colWidths=widths, repeatRows=1)
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), BRAND),
        ("GRID", (0, 0), (-1, -1), 0.5, LINE),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]
    commands += [("BACKGROUND", (0, r), (-1, r), BRAND_TINT) for r in range(2, len(rows), 2)]
    t.setStyle(TableStyle(commands))
    return t


def _cover_crop(path: str, ratio: float, fade: float = 0.0) -> ImageReader:
    """按目标宽高比居中裁切（等同 CSS cover），图片不会被拉伸。
    fade > 0 时把左侧 fade 比例的宽度渐变融进品牌深绿，用来和左边的深绿底无缝衔接。"""
    from PIL import Image as PILImage

    im = PILImage.open(path).convert("RGB")
    w, h = im.size
    if w / h > ratio:
        nw = int(h * ratio)
        im = im.crop(((w - nw) // 2, 0, (w - nw) // 2 + nw, h))
    else:
        nh = int(w / ratio)
        im = im.crop((0, (h - nh) // 2, w, (h - nh) // 2 + nh))
    if fade > 0:
        w, h = im.size
        span = max(1, int(w * fade))
        mask = PILImage.new("L", (w, h), 0)
        mask.paste(PILImage.linear_gradient("L").rotate(-90).resize((span, h)), (0, 0))  # 左 255 → 右 0
        im = PILImage.composite(PILImage.new("RGB", (w, h), (0x16, 0x38, 0x28)), im, mask)
    return ImageReader(im)


class Hero(Flowable):
    """首屏横幅：深绿底通栏，左侧标题，右侧可放 generate_image 生成的配图（与 PPT 封面同一风格）。"""

    def __init__(self, title: str, subtitle: str = "", kicker: str = "", image: str = "", height: float = 72 * mm):
        super().__init__()
        self.title, self.subtitle, self.kicker, self.image, self.height = title, subtitle, kicker, image, height

    def wrap(self, avail_width, avail_height):
        self.width = avail_width
        return self.width, self.height

    def draw(self):
        c, w, h = self.canv, self.width, self.height
        c.saveState()
        path = c.beginPath()
        path.roundRect(0, 0, w, h, 4 * mm)
        c.clipPath(path, stroke=0, fill=0)
        c.setFillColor(BRAND_DEEP)
        c.rect(0, 0, w, h, stroke=0, fill=1)
        text_w = w * 0.6
        if self.image:
            img_w = w * 0.56
            c.drawImage(_cover_crop(self.image, img_w / h, fade=0.4), w - img_w, 0, img_w, h)
        else:
            c.setStrokeColor(colors.HexColor("#3F7C63"))
            c.setLineWidth(1)
            for r in (28 * mm, 44 * mm):
                c.circle(w - 26 * mm, h * 0.35, r, stroke=1, fill=0)
            text_w = w * 0.7
        f = font()
        x, y = 10 * mm, h - 14 * mm
        if self.kicker:
            c.setFont(f, 8.5)
            c.setFillColor(ACCENT)
            c.drawString(x, y, self.kicker)
            y -= 4 * mm
        title = Paragraph(self.title, ParagraphStyle("HeroTitle", fontName=f, fontSize=22, leading=29, textColor=colors.white, wordWrap="CJK"))
        _, th = title.wrap(text_w - x - 4 * mm, h)
        y -= th
        title.drawOn(c, x, y)
        c.setFillColor(ACCENT)
        c.rect(x, y - 5 * mm, 10 * mm, 0.9 * mm, stroke=0, fill=1)
        if self.subtitle:
            sub = Paragraph(self.subtitle, ParagraphStyle("HeroSub", fontName=f, fontSize=11, leading=17, textColor=BRAND_PALE, wordWrap="CJK"))
            _, sh = sub.wrap(w * 0.5 - x, h)
            sub.drawOn(c, x, y - 9 * mm - sh)
        c.restoreState()


def hero(title: str, subtitle: str = "", kicker: str = "", image: str = "") -> list:
    """首屏横幅 + 下方留白。image 传图片路径时右半边放配图。"""
    return [Hero(title, subtitle, kicker, image), Spacer(1, 8 * mm)]


def stat_row(items: list[dict]) -> Table:
    """数据卡片行：2–4 个大数字 + 说明，第一个用品牌色底。items: [{"value": "3 分钟", "label": "产出方案初稿"}]"""
    if not 2 <= len(items) <= 4:
        raise ValueError(f"stat_row 需要 2–4 项，现在是 {len(items)} 项")
    f = font()
    gap = 4 * mm
    w = (CONTENT_WIDTH - gap * (len(items) - 1)) / len(items)
    row, widths, cmds = [], [], [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 10),
                                   ("TOPPADDING", (0, 0), (-1, -1), 10), ("BOTTOMPADDING", (0, 0), (-1, -1), 10)]
    for i, it in enumerate(items):
        if i:
            row.append("")
            widths.append(gap)
        col = len(row)
        hot = i == 0
        value = ParagraphStyle("StatV", fontName=f, fontSize=22, leading=28, textColor=colors.white if hot else BRAND)
        label = ParagraphStyle("StatL", fontName=f, fontSize=9, leading=13, textColor=BRAND_PALE if hot else MUTED, wordWrap="CJK")
        row.append([Paragraph(it["value"], value), Paragraph(it["label"], label)])
        widths.append(w)
        cmds.append(("BACKGROUND", (col, 0), (col, 0), BRAND) if hot else ("BOX", (col, 0), (col, 0), 0.6, LINE))
    t = Table([row], colWidths=widths)
    t.setStyle(TableStyle(cmds))
    return t


def callout(title: str, text: str) -> Table:
    """提示框：浅绿底，标题加粗品牌色，适合放结论或要点摘要。"""
    st = styles()
    t = Table([[[Paragraph(title, st["H2"]), Paragraph(text, st["Body"])]]], colWidths=[CONTENT_WIDTH])
    t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BRAND_TINT), ("LEFTPADDING", (0, 0), (-1, -1), 12),
                           ("RIGHTPADDING", (0, 0), (-1, -1), 12), ("TOPPADDING", (0, 0), (-1, -1), 8), ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
    return t


def figure(path: str, caption: str = "", width: float | None = None) -> list:
    """配图：按原比例缩放到 width（默认版心宽度），下方居中图注。"""
    w = width or CONTENT_WIDTH
    iw, ih = ImageReader(path).getSize()
    out = [Image(path, width=w, height=w * ih / iw)]
    if caption:
        out += [Spacer(1, 2 * mm), Paragraph(caption, ParagraphStyle("Caption", parent=styles()["Small"], alignment=TA_CENTER))]
    return out


def _numbered_canvas(classification: str):
    """两遍绘制拿到总页数，在每页画页眉页脚（reportlab 官方「第 x 页 / 共 y 页」做法）。"""

    class BrandCanvas(pdfcanvas.Canvas):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self._pages: list[dict] = []

        def showPage(self):
            self._pages.append(dict(self.__dict__))
            self._startPage()

        def save(self):
            total = len(self._pages)
            for state in self._pages:
                self.__dict__.update(state)
                self._draw_frame(total)
                super().showPage()
            super().save()

        def _draw_frame(self, total: int):
            f = font()
            top = PAGE_HEIGHT - 14 * mm
            self.drawImage(_LOGO, MARGIN_X, top - 1.2 * mm, width=5 * mm, height=5 * mm, mask="auto")
            self.setFont(f, 10)
            self.setFillColor(BRAND)
            self.drawString(MARGIN_X + 6.5 * mm, top, COMPANY)
            self.setStrokeColor(LINE)
            self.setLineWidth(0.6)
            self.line(MARGIN_X, top - 3 * mm, PAGE_WIDTH - MARGIN_X, top - 3 * mm)

            self.setFont(f, 8.5)
            self.setFillColor(MUTED)
            self.drawString(MARGIN_X, 11 * mm, classification)
            self.drawRightString(PAGE_WIDTH - MARGIN_X, 11 * mm, f"第 {self._pageNumber} 页 / 共 {total} 页")

    return BrandCanvas


def build_pdf(path: str, story: list, *, title: str, classification: str = "对外资料", author: str = COMPANY) -> str:
    """生成 A4 品牌 PDF：每页自动带页眉页脚，story 为 reportlab flowable 列表。返回输出路径。"""
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        path, pagesize=A4,
        leftMargin=MARGIN_X, rightMargin=MARGIN_X, topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
        title=title, author=author, creator=COMPANY,
    )
    doc.build(story, canvasmaker=_numbered_canvas(classification))
    return path
