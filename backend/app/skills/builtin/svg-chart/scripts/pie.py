#!/usr/bin/env python3
"""饼图：占比构成。只吃单系列、只吃非负值 —— 负数在饼图里没有意义。

用法：
    python scripts/pie.py --data share.json --out share.svg
    python scripts/pie.py --data share.csv --out share.svg --donut
"""

from __future__ import annotations

import argparse
import math
import sys

from _svgbase import (
    INK,
    MUTED,
    Canvas,
    ChartDataError,
    color_for,
    draw_title,
    esc,
    load_chart_data,
)

LABEL_MIN_PCT = 3.0  # 占比低于此值不在扇区上标字（挤不下），只出现在图例


def main() -> int:
    ap = argparse.ArgumentParser(description="生成饼图 SVG")
    ap.add_argument("--data", required=True, help="数据文件（.json / .csv）")
    ap.add_argument("--out", required=True, help="输出 .svg 路径")
    ap.add_argument("--width", type=int, default=760)
    ap.add_argument("--height", type=int, default=460)
    ap.add_argument("--donut", action="store_true", help="画成环形图")
    args = ap.parse_args()

    try:
        data = load_chart_data(args.data)
        values = _single_series(data)
    except ChartDataError as exc:
        print(f"数据有问题：{exc}", file=sys.stderr)
        return 1

    total = sum(values)
    c = Canvas(width=args.width, height=args.height, margin_bottom=24)
    draw_title(c, data)

    # 饼图占左侧，图例占右侧 —— 扇区外挂标签容易互相压字，图例更稳
    legend_w = 200.0
    cx = (c.width - legend_w) / 2
    cy = c.height / 2 + 12
    radius = min(cx, c.height / 2 - 40) * 0.86
    inner = radius * 0.55 if args.donut else 0.0

    start = -math.pi / 2  # 12 点方向起笔，顺时针
    for i, (name, value) in enumerate(zip(data.categories, values, strict=True)):
        pct = value / total * 100
        sweep = value / total * math.tau
        end = start + sweep
        color = color_for(i)
        c.add(
            f'<path d="{_sector_path(cx, cy, radius, inner, start, end)}" fill="{color}" '
            f'stroke="#ffffff" stroke-width="1.5"><title>{esc(name)}: {value:g} '
            f'({pct:.1f}%)</title></path>'
        )
        if pct >= LABEL_MIN_PCT:
            mid = start + sweep / 2
            lr = radius * (0.72 if not args.donut else 0.78)
            c.text(cx + math.cos(mid) * lr, cy + math.sin(mid) * lr + 4,
                   f"{pct:.1f}%", size=11, fill="#ffffff", anchor="middle", weight="600")
        start = end

    _draw_side_legend(c, data.categories, values, total, c.width - legend_w + 8, cy)

    out = c.write(args.out)
    print(f"已生成 {out}（{len(values)} 个扇区，合计 {total:g}）")
    return 0


def _single_series(data) -> list[float]:
    """饼图只接受一个系列且值非负；不满足就报清楚，别硬画。"""
    if len(data.series) > 1:
        names = "、".join(s.name for s in data.series)
        raise ChartDataError(
            f"饼图只能画一个系列，但数据里有 {len(data.series)} 个（{names}）。"
            "请只保留一个系列，或改用 bar.py"
        )
    raw = data.series[0].values
    if any(v is not None and v < 0 for v in raw):
        raise ChartDataError("饼图不接受负值 —— 占比图里负数没有意义，请改用 bar.py")
    values = [0.0 if v is None else v for v in raw]  # 饼图里缺失等价于 0 占比
    if sum(values) <= 0:
        raise ChartDataError("所有值都是 0 或空，无法计算占比")
    return values


def _sector_path(cx: float, cy: float, r: float, inner: float, a0: float, a1: float) -> str:
    """扇区（或环形段）路径。整圆走两段弧 —— 单段 A 命令画不出 360°。"""
    if a1 - a0 >= math.tau - 1e-9:
        if inner <= 0:
            return f"M {cx - r:.2f} {cy:.2f} A {r:.2f} {r:.2f} 0 1 1 {cx + r:.2f} {cy:.2f} A {r:.2f} {r:.2f} 0 1 1 {cx - r:.2f} {cy:.2f} Z"
        a1 = a0 + math.tau - 1e-6  # 环形整圆：留一丝缝，避免路径退化

    large = 1 if (a1 - a0) > math.pi else 0
    x0, y0 = cx + math.cos(a0) * r, cy + math.sin(a0) * r
    x1, y1 = cx + math.cos(a1) * r, cy + math.sin(a1) * r
    if inner <= 0:
        return (f"M {cx:.2f} {cy:.2f} L {x0:.2f} {y0:.2f} "
                f"A {r:.2f} {r:.2f} 0 {large} 1 {x1:.2f} {y1:.2f} Z")
    xi0, yi0 = cx + math.cos(a0) * inner, cy + math.sin(a0) * inner
    xi1, yi1 = cx + math.cos(a1) * inner, cy + math.sin(a1) * inner
    return (f"M {x0:.2f} {y0:.2f} A {r:.2f} {r:.2f} 0 {large} 1 {x1:.2f} {y1:.2f} "
            f"L {xi1:.2f} {yi1:.2f} A {inner:.2f} {inner:.2f} 0 {large} 0 {xi0:.2f} {yi0:.2f} Z")


def _draw_side_legend(
    c: Canvas, names: list[str], values: list[float], total: float, x: float, cy: float
) -> None:
    """右侧竖排图例：色块 + 名称 + 数值 + 占比。"""
    row_h = 22.0
    y = cy - row_h * len(names) / 2 + 8
    for i, (name, value) in enumerate(zip(names, values, strict=True)):
        c.add(f'<rect x="{x:.2f}" y="{y - 9:.2f}" width="11" height="11" rx="2" '
              f'fill="{color_for(i)}"/>')
        c.text(x + 17, y, name, size=11.5, fill=INK)
        c.text(c.width - 16, y, f"{value:g}  {value / total * 100:.1f}%", size=11,
               fill=MUTED, anchor="end")
        y += row_h


if __name__ == "__main__":
    raise SystemExit(main())
