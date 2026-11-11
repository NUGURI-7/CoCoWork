#!/bin/sh
set -eu

# 根据脚本位置定位仓库，兼容从 backend/ 等子目录启动。
project_dir=$(CDPATH= cd "$(dirname "$0")/../.." && pwd)
weekly_file="$project_dir/docs/weekly.md"
# 与用户的日历时区一致，避免服务器时区导致周号提前切换。
week=$(TZ=America/Los_Angeles date +%G-W%V)

if [ ! -r "$weekly_file" ]; then
    printf '[开发周报提醒] 无法读取 docs/weekly.md，请先确认文件是否存在。\n'
    exit 0
fi

# 只认周报标题，正文中提到周号不算已经写过。
if ! grep -Eq "^##[[:space:]]+$week([[:space:]（(]|$)" "$weekly_file"; then
    printf '[开发周报提醒] 本周 %s 还没有 docs/weekly.md 周报条目。请简短提醒用户；用户要求写周报时，再回顾本周改动并先提供草稿。\n' "$week"
fi
