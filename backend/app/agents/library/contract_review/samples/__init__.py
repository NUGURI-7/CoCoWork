"""示例合同：虚构公司 + 按公司模板改出问题，供没有自己合同的用户体验初审。"""

from functools import cache
from pathlib import Path

_DIR = Path(__file__).parent

# 表单上显示的标签 → 合同文件
SAMPLES: dict[str, str] = {
    "南湾智造 · 堡垒机企业版合同": "nanwan_enterprise.md",
    "北辰云港 · 堡垒机标准版合同": "beichen_standard.md",
}


@cache
def load_sample(label: str) -> str:
    """按标签读出示例合同正文；标签不在册时抛 KeyError。"""
    return (_DIR / SAMPLES[label]).read_text(encoding="utf-8")
