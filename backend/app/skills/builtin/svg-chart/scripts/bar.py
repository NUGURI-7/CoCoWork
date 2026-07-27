#!/usr/bin/env python3
"""柱状图：分类对比。多系列并排分组，支持负值。

用法：
    python scripts/bar.py --data sales.json --out sales.svg
    python scripts/bar.py --data sales.csv --out sales.svg --width 960
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

BAR_GAP_RATIO = 0.28  # 组间留白占槽位比例
MIN_BAR_PX = 1.0  # 非零值至少画 1px，否则小值柱子会消失


def main() -> int:
    ap = argparse.ArgumentParser(description="生成柱状图 SVG")
    ap.add_argument("--data", required=True, help="数据文件（.json / .csv）")
    ap.add_argument("--out", required=True, help="输出 .svg 路径")
    ap.add_argument("--width", type=int, default=800)
    ap.add_argument("--height", type=int, default=480)
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

    slot = c.plot_width / len(data.categories)
    group_w = slot * (1 - BAR_GAP_RATIO)
    bar_w = group_w / len(data.series)
    baseline = y_of(c, 0.0, axis_lo, axis_hi)

    for si, series in enumerate(data.series):
        color = color_for(si)
        for ci, value in enumerate(series.values):
            if value is None:  # 缺失值不画柱子（画成 0 会误导）
                continue
            x = c.plot_left + slot * ci + (slot - group_w) / 2 + bar_w * si
            y_val = y_of(c, value, axis_lo, axis_hi)
            top, height = min(y_val, baseline), abs(y_val - baseline)
            if height < MIN_BAR_PX:
                height = MIN_BAR_PX
                top = baseline - MIN_BAR_PX if value > 0 else baseline
            c.add(
                f'<rect x="{x:.2f}" y="{top:.2f}" width="{bar_w:.2f}" height="{height:.2f}" '
                f'fill="{color}" rx="2"><title>{series.name} {data.categories[ci]}: '
                f'{value:g}</title></rect>'
            )

    out = c.write(args.out)
    print(f"已生成 {out}（{len(data.categories)} 类目 × {len(data.series)} 系列）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
