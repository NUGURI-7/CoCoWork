#!/usr/bin/env python3
"""给 svg_output/ 里每一页盖上 CoCoWork 品牌元素：Logo、页脚品牌名、页码。

页面 SVG 由模型逐页手写，品牌元素不靠模型记得，统一在导出前由本脚本注入：

    python3 brand_stamp.py <project_path>

按根节点 data-pptx-page-role 决定盖什么：
    cover    左上角 Logo + 「CoCoWork」字标
    section  右上角 Logo + 右下角页码
    content  右上角 Logo + 左下角「COCOWORK」+ 右下角页码
    toc      同 content
    ending   正中偏上 Logo

根节点 data-brand-tone="dark" 表示深色底（品牌绿或照片），品牌元素用白色；缺省按浅色底用品牌绿。
重复执行是安全的：先删掉上一次注入的 brand-* 分组再重盖。
另外检查字体：页面里出现非「微软雅黑 / 宋体」的 font-family 时报错退出。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

CANVAS_W, CANVAS_H = 1280, 720
BRAND = "#2F6B53"
MUTED = "#5F6B65"
WHITE = "#FFFFFF"
LIGHT = "#CFE3D8"
ALLOWED_FONTS = {"Microsoft YaHei", "微软雅黑", "SimSun", "宋体"}

# 品牌区：模型画的内容不能进入这两块（右上角 Logo、底部页脚）
RESERVED_TOP_RIGHT = (1160, 24, 96, 72)
FOOTER_Y = 668

_INJECTED = re.compile(r'\s*<g id="brand-[a-z-]+"[^>]*>.*?</g><!--/brand-->', re.S)


def logo(x: float, y: float, size: float, color: str) -> str:
    """CoCoWork Logo（frontend/public/logo.svg 的 32×32 图形）按 size 缩放到 (x, y)。"""
    k = size / 32
    p = lambda v: round(v * k, 2)  # noqa: E731
    lines = [((16, 14), (16, 6)), ((16, 18), (9, 23)), ((16, 18), (23, 23))]
    circles = [(16, 16, 4.6), (16, 4.6, 3), (7.4, 24.6, 3), (24.6, 24.6, 3)]
    parts = [
        f'<line x1="{x + p(a[0])}" y1="{y + p(a[1])}" x2="{x + p(b[0])}" y2="{y + p(b[1])}" '
        f'stroke="{color}" stroke-width="{p(2)}" stroke-opacity="0.45"/>'
        for a, b in lines
    ]
    parts += [f'<circle cx="{x + p(cx)}" cy="{y + p(cy)}" r="{p(r)}" fill="{color}"/>' for cx, cy, r in circles]
    return "".join(parts)


def _group(gid: str, role: str, bounds: tuple[float, float, float, float], body: str) -> str:
    b = " ".join(str(round(v, 2)) for v in bounds)
    return f'\n  <g id="{gid}" data-pptx-role="{role}" data-pptx-bounds="{b}">{body}</g><!--/brand-->'


def chrome(role: str, dark: bool, page_no: int) -> str:
    mark = WHITE if dark else BRAND
    soft = LIGHT if dark else MUTED
    corner_logo = _group("brand-logo", "logo", (1184, 36, 40, 40), logo(1184, 36, 40, mark))
    number = _group(
        "brand-page-number", "page-number", (1136, 676, 80, 24),
        f'<text x="1216" y="694" font-size="14" text-anchor="end" fill="{soft}">{page_no:02d}</text>',
    )
    if role == "cover":
        return _group(
            "brand-logo", "logo", (64, 48, 220, 44),
            logo(64, 48, 44, mark)
            + f'<text x="120" y="80" font-size="24" font-weight="bold" fill="{mark}">CoCoWork</text>',
        )
    if role == "ending":
        return _group("brand-logo", "logo", (604, 150, 72, 72), logo(604, 150, 72, mark))
    if role == "section":
        return corner_logo + number
    footer = _group(
        "brand-footer", "footer", (64, 676, 300, 24),
        f'<text x="64" y="694" font-size="13" font-weight="bold" letter-spacing="3" fill="{mark}">COCOWORK</text>',
    )
    return corner_logo + footer + number


def stamp(svg: str, page_no: int, name: str) -> str:
    root = re.search(r"<svg\b[^>]*>", svg)
    if not root:
        raise SystemExit(f"{name}: 找不到 <svg> 根节点")
    role_m = re.search(r'data-pptx-page-role="([a-z]+)"', root.group(0))
    if not role_m:
        raise SystemExit(f'{name}: 根节点缺少 data-pptx-page-role（cover / toc / section / content / ending）')
    dark = 'data-brand-tone="dark"' in root.group(0)

    fonts = {f.strip().strip("'\"") for fam in re.findall(r'font-family="([^"]+)"', svg) for f in fam.split(",")}
    bad = fonts - ALLOWED_FONTS
    if bad:
        raise SystemExit(f"{name}: 字体只能用 微软雅黑（Microsoft YaHei）或 宋体（SimSun），发现 {', '.join(sorted(bad))}")

    body = _INJECTED.sub("", svg)
    end = body.rstrip().rfind("</svg>")
    return body[:end].rstrip() + chrome(role_m.group(1), dark, page_no) + "\n</svg>\n"


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    out_dir = Path(argv[1]) / "svg_output"
    pages = sorted(out_dir.glob("*.svg"))
    if not pages:
        raise SystemExit(f"{out_dir} 里没有 SVG 页面")
    for i, page in enumerate(pages, start=1):
        page.write_text(stamp(page.read_text(encoding="utf-8"), i, page.name), encoding="utf-8")
    print(f"已为 {len(pages)} 页加上品牌元素")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
