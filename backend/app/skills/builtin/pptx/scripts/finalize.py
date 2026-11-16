#!/usr/bin/env python3
"""页面写完后的固定收尾，一条命令做完：

    python3 finalize.py <project_path>                 # 盖品牌 → 整理样式 → 检查 → 渲染预览图
    python3 finalize.py <project_path> -o <out.pptx>   # 盖品牌 → 整理样式 → 检查 → 导出并校验

任一步失败就停下，打印那一步的输出，退出码非 0；检查报错时按报告改页面后重新执行本命令即可。
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
ENGINE = SKILL_DIR / "engine"


def _run(label: str, args: list[str]) -> str:
    result = subprocess.run([sys.executable, *args], capture_output=True, text=True)
    output = (result.stdout + result.stderr).strip()
    if result.returncode != 0:
        raise SystemExit(f"【{label}】失败：\n{output}")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("project", type=Path)
    parser.add_argument("-o", "--output", type=Path, help="导出的 .pptx 路径；不给则只渲染预览图")
    opts = parser.parse_args()
    project = opts.project.resolve()

    _run("盖品牌", [str(SKILL_DIR / "brand" / "brand_stamp.py"), str(project)])
    _run("整理样式", [str(ENGINE / "compact_svg_styles.py"), str(project / "svg_output"), "--inplace"])
    _run("检查", [
        str(ENGINE / "svg_quality_checker.py"), str(project),
        "--quick-generate", "--canonical-authoring", "--stage", "final", "--json",
    ])

    if opts.output is None:
        print("检查通过。预览图：")
        print(_run("渲染", [str(SKILL_DIR / "scripts" / "render_pages.py"), str(project)]))
        return 0

    out = opts.output.resolve()
    _run("导出", [str(ENGINE / "svg_to_pptx.py"), str(project), "--quick-generate", "--no-notes", "-o", str(out)])
    _run("校验", [str(SKILL_DIR / "scripts" / "office" / "validate.py"), str(out)])
    print(f"已导出 {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
