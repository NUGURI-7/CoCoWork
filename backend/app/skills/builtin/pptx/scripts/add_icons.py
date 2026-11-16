#!/usr/bin/env python3
"""把用到的图标从内置图标库复制进项目，页面里才能用 <use data-icon="tabler-filled/名字">。

    python3 add_icons.py <project_path> bulb rocket shield-check ...
    python3 add_icons.py --search chart          # 按关键词列出可用图标名

图标库是 Tabler Icons 实心版（1055 个），名字即 icons/tabler-filled/ 下的文件名（不带 .svg）。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

LIBRARY = Path(__file__).resolve().parent.parent / "icons" / "tabler-filled"


def main(argv: list[str]) -> int:
    if len(argv) == 3 and argv[1] == "--search":
        names = sorted(p.stem for p in LIBRARY.glob(f"*{argv[2]}*.svg"))
        print("\n".join(names) if names else f"没有名字里含「{argv[2]}」的图标，换个英文关键词试试")
        return 0
    if len(argv) < 3:
        print(__doc__)
        return 2
    target = Path(argv[1]) / "icons" / "tabler-filled"
    target.mkdir(parents=True, exist_ok=True)
    missing = [n for n in argv[2:] if not (LIBRARY / f"{n}.svg").is_file()]
    if missing:
        raise SystemExit(f"图标不存在：{', '.join(missing)}。先用 --search 查准确名字。")
    for name in argv[2:]:
        shutil.copy2(LIBRARY / f"{name}.svg", target / f"{name}.svg")
    print(f"已复制 {len(argv) - 2} 个图标到 {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
