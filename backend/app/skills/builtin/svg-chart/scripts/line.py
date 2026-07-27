#!/usr/bin/env python3
"""折线图：趋势变化。多系列叠加，缺失值处断线（不插值 —— 猜数据比留白更坏）。

用法：
    python scripts/line.py --data trend.json --out trend.svg
    python scripts/line.py --data trend.csv --out trend.svg --no-dots
"""

from __future__ import annotations

import argparse
import sys

from _svgbase import (
    Canvas,
    ChartDataError,
    color_for,
    draw_category_axis,
    draw_legend,
    draw_title,
    draw_value_axis,
    load_chart_data,
    nice_ticks,
    y_of,
)

DOT_RADIUS = 3.2
MAX_DOTS = 40  # 点太多会糊成一条带，超过此数自动不画点


def main() -> int:
    ap = argparse.ArgumentParser(description="生成折线图 SVG")
    ap.add_argument("--data", required=True, help="数据文件（.json / .csv）")
    ap.add_argument("--out", required=True, help="输出 .svg 路径")
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--height", type=int, default=480)
    ap.add_argument("--no-dots", action="store_true", help="不画数据点标记")
    args = ap.parse_args()

    try:
        data = load_chart_data(args.data)
        lo, hi = data.numeric_range()
    except ChartDataError as exc:
        print(f"数据有问题：{exc}", file=sys.stderr)
        return 1

    axis_lo, axis_hi, ticks = nice_ticks(lo, hi)
    c = Canvas(width=args.width, height=args.height)

    draw_title(c, data)
    draw_legend(c, [s.name for s in data.series], [color_for(i) for i in range(len(data.series))])
    draw_value_axis(c, axis_lo, axis_hi, ticks, data.y_label)
    draw_category_axis(c, data.categories, data.x_label)

    n = len(data.categories)
    slot = c.plot_width / n
    show_dots = not args.no_dots and n <= MAX_DOTS

    def x_of(i: int) -> float:
        return c.plot_left + slot * (i + 0.5)

    for si, series in enumerate(data.series):
        color = color_for(si)
        # 缺失值把折线切成多段，各段单独画 —— 跨空洞连线等于凭空造数据
        segment: list[tuple[float, float]] = []
        segments: list[list[tuple[float, float]]] = []
        for ci, value in enumerate(series.values):
            if value is None:
                if segment:
                    segments.append(segment)
                    segment = []
                continue
            segment.append((x_of(ci), y_of(c, value, axis_lo, axis_hi)))
        if segment:
            segments.append(segment)

        for seg in segments:
            if len(seg) == 1:  # 孤立点：没有线可画，强制画点
                x, y = seg[0]
                c.add(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{DOT_RADIUS:.1f}" fill="{color}"/>')
                continue
            pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in seg)
            c.add(
                f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2" '
                f'stroke-linejoin="round" stroke-linecap="round"/>'
            )

        if show_dots:
            for ci, value in enumerate(series.values):
                if value is None:
                    continue
                x, y = x_of(ci), y_of(c, value, axis_lo, axis_hi)
                c.add(
                    f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{DOT_RADIUS:.1f}" fill="#ffffff" '
                    f'stroke="{color}" stroke-width="2"><title>{series.name} '
                    f'{data.categories[ci]}: {value:g}</title></circle>'
                )

    out = c.write(args.out)
    print(f"已生成 {out}（{n} 个点 × {len(data.series)} 系列）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
