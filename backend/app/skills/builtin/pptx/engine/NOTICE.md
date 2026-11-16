# 来源说明

本目录是 [PPT Master](https://github.com/hugohe3/ppt-master) 的「SVG → 原生 PPTX」转换引擎与 SVG 质量检查器，
取自 commit `3af3e8ef774c4d67ee57e1306d9256d08c9ee1bf`（Skill 版本 6.9.0），MIT 许可，版权与许可原文见同目录 `LICENSE`
（Copyright (c) 2025-2026 Hugo He）。

CoCoWork 的改动：

- 只保留 `svg_to_pptx.py`、`svg_quality_checker.py`、`compact_svg_styles.py` 及其依赖模块，删去原项目的工作流文档、模板库、
  生图 / 搜图 / 语音 / 视频脚本和测试。
- `attribution_guard.py` 换成空实现，`console_encoding.py` 删去发行版身份校验：原项目要求整个 Skill 与官方发行版逐字节一致才运行，
  这里只取引擎，无法满足该校验。其余代码未改。

`../icons/tabler-filled/` 取自同一 commit 的 `templates/icons/tabler-filled`（Tabler Icons v3.46.0，MIT），许可见 `../icons/THIRD_PARTY_NOTICES.md`。
