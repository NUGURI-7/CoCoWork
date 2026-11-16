#!/usr/bin/env python3
"""把 <project>/svg_output/ 的每一页渲染成 PNG，供看图工具检查排版。

    python3 render_pages.py <project_path>

输出到 <project>/preview/<页面名>.png（1280×720），打印每张图的绝对路径。
页面里的 <use data-icon> 先按 <project>/icons/ 展开再渲染，与导出 PPTX 时一致；
中文字体由系统字体兜底（沙箱里是文泉驿正黑），和用户电脑上的微软雅黑字形略有不同，只用于看排版。
"""

from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ENGINE = Path(__file__).resolve().parent.parent / "engine"
sys.path.insert(0, str(ENGINE))

from svg_to_pptx.use_expander import expand_use_data_icons  # noqa: E402

SVG_NS = "http://www.w3.org/2000/svg"


def render(project: Path) -> list[Path]:
    import cairosvg

    pages = sorted((project / "svg_output").glob("*.svg"))
    if not pages:
        raise SystemExit(f"{project / 'svg_output'} 里没有 SVG 页面")
    out_dir = project / "preview"
    out_dir.mkdir(exist_ok=True)
    ET.register_namespace("", SVG_NS)
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    outputs = []
    for page in pages:
        root = ET.parse(page).getroot()
        expand_use_data_icons(root, project / "icons")
        target = out_dir / f"{page.stem}.png"
        cairosvg.svg2png(
            bytestring=ET.tostring(root, encoding="utf-8"),
            url=page.resolve().as_uri(),  # 让 ../images/xxx.png 按页面所在目录解析
            write_to=str(target),
            output_width=1280,
            output_height=720,
        )
        outputs.append(target.resolve())
    return outputs


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(__doc__)
        return 2
    for path in render(Path(argv[1])):
        print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
