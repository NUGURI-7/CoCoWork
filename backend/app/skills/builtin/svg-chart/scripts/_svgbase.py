"""SVG 图表公共层：数据加载、刻度、坐标映射、轴、配色、转义。

bar.py / line.py / pie.py 共用本模块。刻意不引第三方库 —— SVG 是纯文本 XML，
手工拼装是常规做法（与「手写 PDF 解析器」那类残缺方案不同性质）。

输出是确定性的：同样输入必得同样字节，便于测试与 diff。
"""

from __future__ import annotations

import csv
import json
import math
from dataclasses import dataclass, field
from pathlib import Path

# 配色：首色取项目品牌绿，其余为手挑的定性配色（白底可读、相邻色相拉开）
PALETTE = (
    "#2f6b53",  # 品牌绿
    "#c9772f",  # 暖橙
    "#3d6a9b",  # 蓝
    "#8b5a8c",  # 紫
    "#a34a3f",  # 砖红
    "#5c7a4a",  # 橄榄
    "#b8963f",  # 金
    "#6b6b6b",  # 灰
)

# 字体栈覆盖 macOS / Windows / 通用，中文无需嵌字体（浏览器渲染时解析）
FONT_STACK = '-apple-system, "PingFang SC", "Microsoft YaHei", "Helvetica Neue", Arial, sans-serif'

INK = "#1f2328"  # 正文
MUTED = "#6b7280"  # 次要文字 / 刻度
GRID = "#e5e7eb"  # 网格线


class ChartDataError(ValueError):
    """数据文件不合法 —— 消息面向调用者（LLM），说清哪里不对、该怎么改。"""


@dataclass(slots=True)
class Series:
    """一条数据系列。`values` 与 `ChartData.categories` 等长，缺失值用 None。"""

    name: str
    values: list[float | None]


@dataclass(slots=True)
class ChartData:
    """一份图表数据。"""

    categories: list[str]
    series: list[Series]
    title: str = ""
    x_label: str = ""
    y_label: str = ""

    def numeric_range(self) -> tuple[float, float]:
        """所有系列的数值范围；基线 0 始终纳入（柱状图不能悬空）。"""
        vals = [v for s in self.series for v in s.values if v is not None]
        if not vals:
            raise ChartDataError("所有数据点都是空值，无法作图")
        return min(min(vals), 0.0), max(max(vals), 0.0)


# ---------- 数据加载 ----------

def load_chart_data(path: str | Path) -> ChartData:
    """按扩展名加载 `.json` / `.csv` / `.tsv`。"""
    p = Path(path)
    if not p.is_file():
        raise ChartDataError(f"数据文件不存在：{p}")
    suffix = p.suffix.lower()
    if suffix == ".json":
        return _load_json(p)
    if suffix in {".csv", ".tsv", ".txt"}:
        return _load_table(p)
    raise ChartDataError(f"不支持的数据格式 {suffix!r}，请用 .json 或 .csv")


def _load_json(p: Path) -> ChartData:
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ChartDataError(f"JSON 解析失败：{exc}") from exc
    if not isinstance(raw, dict):
        raise ChartDataError("JSON 顶层必须是对象，含 categories 与 series 两个键")

    categories = raw.get("categories")
    if not isinstance(categories, list) or not categories:
        raise ChartDataError("categories 必须是非空数组，例如 [\"1月\", \"2月\"]")
    categories = [str(c) for c in categories]

    raw_series = raw.get("series")
    if not isinstance(raw_series, list) or not raw_series:
        raise ChartDataError(
            'series 必须是非空数组，例如 [{"name": "华东", "values": [120, 135]}]'
        )

    series: list[Series] = []
    for i, item in enumerate(raw_series):
        if not isinstance(item, dict):
            raise ChartDataError(f"series[{i}] 必须是对象，含 name 与 values")
        name = str(item.get("name") or f"系列{i + 1}")
        values = item.get("values")
        if not isinstance(values, list):
            raise ChartDataError(f"series[{i}].values 必须是数组")
        if len(values) != len(categories):
            raise ChartDataError(
                f"series[{i}] ({name}) 有 {len(values)} 个值，"
                f"但 categories 有 {len(categories)} 项 —— 两者必须等长"
            )
        series.append(Series(name=name, values=[_coerce(v, f"series[{i}]") for v in values]))

    return ChartData(
        categories=categories,
        series=series,
        title=str(raw.get("title") or ""),
        x_label=str(raw.get("x_label") or ""),
        y_label=str(raw.get("y_label") or ""),
    )


def _load_table(p: Path) -> ChartData:
    """表格格式：首行表头（首格忽略，其余为系列名），其后每行首格为类目名。"""
    text = p.read_text(encoding="utf-8-sig")  # BOM 常见于 Excel 导出
    if not text.strip():
        raise ChartDataError(f"{p.name} 是空文件")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",\t;")
    except csv.Error:
        dialect = csv.excel  # 单列文件嗅探会失败，退回逗号
    rows = [r for r in csv.reader(text.splitlines(), dialect) if any(c.strip() for c in r)]
    if len(rows) < 2:
        raise ChartDataError(f"{p.name} 至少需要表头 + 1 行数据")

    header = rows[0]
    if len(header) < 2:
        raise ChartDataError("表格至少要两列：第一列类目名，其后每列一个系列")
    series_names = [c.strip() or f"系列{i}" for i, c in enumerate(header[1:], start=1)]

    categories: list[str] = []
    columns: list[list[float | None]] = [[] for _ in series_names]
    for line_no, row in enumerate(rows[1:], start=2):
        categories.append(row[0].strip())
        for i in range(len(series_names)):
            cell = row[i + 1].strip() if i + 1 < len(row) else ""
            columns[i].append(_coerce(cell, f"第 {line_no} 行"))

    return ChartData(
        categories=categories,
        series=[Series(name=n, values=v) for n, v in zip(series_names, columns, strict=True)],
        y_label=header[0].strip(),
    )


def _coerce(v: object, where: str) -> float | None:
    """空串 / None / 常见缺失标记 → None；其余必须能转 float。"""
    if v is None:
        return None
    if isinstance(v, bool):  # bool 是 int 子类，先挡掉
        raise ChartDataError(f"{where} 含布尔值，数值列不接受 true/false")
    if isinstance(v, (int, float)):
        if isinstance(v, float) and not math.isfinite(v):
            return None
        return float(v)
    s = str(v).strip()
    if s == "" or s.upper() in {"NA", "N/A", "NULL", "NAN", "-"}:
        return None
    try:
        return float(s.replace(",", ""))  # 容忍千分位
    except ValueError as exc:
        raise ChartDataError(f"{where} 的值 {s!r} 不是数字") from exc


# ---------- 刻度 ----------

def nice_ticks(vmin: float, vmax: float, target: int = 5) -> tuple[float, float, list[float]]:
    """把区间扩到「好看」的整数刻度，返回 (轴下界, 轴上界, 刻度列表)。

    直接拿 min/max 当轴范围会得到 3.7 / 11.4 这类刻度，不可读。
    此处取 1 / 2 / 2.5 / 5 / 10 的十进制倍数作步长（业界通用的 nice-number 算法）。
    """
    if not math.isfinite(vmin) or not math.isfinite(vmax):
        raise ChartDataError("数值范围含无穷或 NaN")
    if vmin == vmax:  # 全等值（含全 0）：造一个对称区间，避免零高度
        pad = abs(vmin) * 0.5 or 1.0
        vmin, vmax = vmin - pad, vmax + pad

    raw_step = (vmax - vmin) / max(target, 1)
    magnitude = 10.0 ** math.floor(math.log10(raw_step))
    for mult in (1, 2, 2.5, 5, 10):
        step = mult * magnitude
        if raw_step <= step:
            break

    lo = math.floor(vmin / step) * step
    hi = math.ceil(vmax / step) * step
    ticks: list[float] = []
    t = lo
    while t <= hi + step * 1e-9:
        ticks.append(0.0 if abs(t) < step * 1e-9 else t)  # 消掉 -0.0
        t += step
    return lo, hi, ticks


def fmt_tick(v: float) -> str:
    """刻度文本：整数不带小数点，小数按需保留，大数用 k / M 缩写。"""
    a = abs(v)
    if a >= 1_000_000:
        return f"{v / 1_000_000:g}M"
    if a >= 10_000:
        return f"{v / 1000:g}k"
    if a == int(a):
        return str(int(v))
    return f"{v:.6g}"


# ---------- SVG 画布 ----------

def esc(s: object) -> str:
    """XML 文本转义。中文无需处理，但 & < > 必须转，否则产出的 SVG 不合法。"""
    return (
        str(s)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


@dataclass(slots=True)
class Canvas:
    """收集 SVG 片段并输出完整文档。

    坐标系沿用 SVG 原生的「左上角为原点、y 向下」，绘图代码里统一用
    `y_of()` 把数据值映射成屏幕 y，不在各处重复算翻转。
    """

    width: int = 800
    height: int = 480
    margin_top: int = 56
    margin_right: int = 24
    margin_bottom: int = 64
    margin_left: int = 72
    parts: list[str] = field(default_factory=list)

    # 绘图区（不含边距）
    @property
    def plot_left(self) -> float:
        return float(self.margin_left)

    @property
    def plot_right(self) -> float:
        return float(self.width - self.margin_right)

    @property
    def plot_top(self) -> float:
        return float(self.margin_top)

    @property
    def plot_bottom(self) -> float:
        return float(self.height - self.margin_bottom)

    @property
    def plot_width(self) -> float:
        return self.plot_right - self.plot_left

    @property
    def plot_height(self) -> float:
        return self.plot_bottom - self.plot_top

    def add(self, fragment: str) -> None:
        self.parts.append(fragment)

    def text(
        self,
        x: float,
        y: float,
        content: object,
        *,
        size: float = 12,
        fill: str = INK,
        anchor: str = "start",
        weight: str = "normal",
        rotate: float | None = None,
    ) -> None:
        transform = f' transform="rotate({rotate:.1f} {x:.2f} {y:.2f})"' if rotate else ""
        self.add(
            f'<text x="{x:.2f}" y="{y:.2f}" font-size="{size:g}" fill="{fill}" '
            f'text-anchor="{anchor}" font-weight="{weight}"{transform}>{esc(content)}</text>'
        )

    def render(self) -> str:
        body = "\n  ".join(self.parts)
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{self.width}" '
            f'height="{self.height}" viewBox="0 0 {self.width} {self.height}" '
            f'font-family=\'{FONT_STACK}\'>\n'
            f'  <rect width="{self.width}" height="{self.height}" fill="#ffffff"/>\n'
            f"  {body}\n"
            f"</svg>\n"
        )

    def write(self, out_path: str | Path) -> Path:
        p = Path(out_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(self.render(), encoding="utf-8")
        return p


# ---------- 常用绘制块 ----------

def draw_title(c: Canvas, data: ChartData) -> None:
    if data.title:
        c.text(c.width / 2, 30, data.title, size=17, weight="600", anchor="middle")


def draw_value_axis(
    c: Canvas, lo: float, hi: float, ticks: list[float], y_label: str
) -> None:
    """纵轴：水平网格线 + 刻度文本 + 轴标题；0 线加深。"""
    for t in ticks:
        y = y_of(c, t, lo, hi)
        is_zero = abs(t) < 1e-12
        c.add(
            f'<line x1="{c.plot_left:.2f}" y1="{y:.2f}" x2="{c.plot_right:.2f}" y2="{y:.2f}" '
            f'stroke="{MUTED if is_zero else GRID}" stroke-width="{1.2 if is_zero else 1}"/>'
        )
        c.text(c.plot_left - 10, y + 4, fmt_tick(t), size=11, fill=MUTED, anchor="end")
    if y_label:
        c.text(18, c.plot_top + c.plot_height / 2, y_label, size=12, fill=MUTED,
               anchor="middle", rotate=-90)


def draw_category_axis(c: Canvas, categories: list[str], x_label: str) -> None:
    """横轴：类目标签（过密时倾斜 30°）+ 轴标题。"""
    n = len(categories)
    slot = c.plot_width / n
    rotate = slot < 52 and max((len(s) for s in categories), default=0) > 3
    for i, name in enumerate(categories):
        cx = c.plot_left + slot * (i + 0.5)
        if rotate:
            c.text(cx, c.plot_bottom + 18, name, size=11, fill=MUTED, anchor="end", rotate=-30)
        else:
            c.text(cx, c.plot_bottom + 20, name, size=11, fill=MUTED, anchor="middle")
    if x_label:
        c.text(c.plot_left + c.plot_width / 2, c.height - 14, x_label, size=12,
               fill=MUTED, anchor="middle")


def draw_legend(c: Canvas, labels: list[str], colors: list[str]) -> None:
    """图例横排在标题下方，居中。单系列不画。"""
    if len(labels) < 2:
        return
    item_w = [len(str(s)) * 7.5 + 26 for s in labels]
    x = c.width / 2 - sum(item_w) / 2
    y = 46
    for label, color, w in zip(labels, colors, item_w, strict=True):
        c.add(f'<rect x="{x:.2f}" y="{y - 8:.2f}" width="10" height="10" rx="2" fill="{color}"/>')
        c.text(x + 15, y + 1, label, size=11, fill=MUTED)
        x += w


def y_of(c: Canvas, value: float, lo: float, hi: float) -> float:
    """数据值 → 屏幕 y（含 y 轴翻转）。"""
    span = hi - lo or 1.0
    return c.plot_bottom - (value - lo) / span * c.plot_height


def color_for(i: int) -> str:
    return PALETTE[i % len(PALETTE)]
