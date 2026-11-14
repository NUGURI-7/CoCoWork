"""有效活动查询：门店活动系统的查询入口。演示数据写在代码里，生产环境对接活动系统。"""

from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field

from app.tools.base import CoCoTool, ToolCategory


@dataclass(frozen=True)
class Promotion:
    title: str
    stores: tuple[str, ...]
    products: tuple[str, ...]
    time_window: str
    offer: str
    valid_from: date
    valid_until: date
    terms: str


PROMOTIONS = (
    Promotion(
        "下午茶蛋挞时段促销", ("万达店", "万象城店"), ("原味蛋挞",),
        "每天 15:00–17:00", "原味蛋挞四个 19.9 元",
        date(2026, 11, 1), date(2027, 12, 31), "限堂食和自提，售完即止",
    ),
    Promotion(
        "海盐黄油卷新品尝鲜", ("万达店",), ("海盐黄油卷",),
        "全天", "新品第二个半价",
        date(2026, 11, 1), date(2027, 12, 31), "每人限购两组",
    ),
    Promotion(
        "周末司康咖啡组合", ("万象城店", "大学城店"), ("可可司康", "美式咖啡"),
        "周六、周日全天", "可可司康配美式 22 元",
        date(2026, 11, 1), date(2027, 12, 31), "不与其他优惠同享",
    ),
)

_NOT_FOUND = "没有查到符合条件的有效活动。播报里不要写任何优惠、价格或活动时段。"


def _matches(value: str, candidates: tuple[str, ...]) -> bool:
    return not value or any(value in c or c in value for c in candidates)


def _format(p: Promotion) -> str:
    return (
        f"【{p.title}】\n优惠：{p.offer}\n时段：{p.time_window}\n"
        f"适用门店：{'、'.join(p.stores)}\n参与商品：{'、'.join(p.products)}\n"
        f"有效期：{p.valid_from:%Y-%m-%d} 至 {p.valid_until:%Y-%m-%d}\n使用条件：{p.terms}"
    )


class PromotionLookupInput(BaseModel):
    store: str = Field(default="", description="门店名，如「万达店」；不限门店留空")
    product: str = Field(default="", description="商品名，如「原味蛋挞」；不限商品留空")


class PromotionLookupTool(CoCoTool):
    name: str = "lookup_promotions"
    display_name: str = "查询有效活动"
    description: str = (
        "查询麦穗烘焙当前有效的门店活动：优惠内容、参与商品、适用门店、时段和使用条件。"
        "播报涉及优惠、价格或时段时，必须先用它核对。"
    )
    category: ToolCategory = "data_source"
    args_schema: type[BaseModel] = PromotionLookupInput

    async def _execute(self, store: str = "", product: str = "") -> str:
        today = date.today()
        hits = [
            p for p in PROMOTIONS
            if p.valid_from <= today <= p.valid_until
            and _matches(store.strip(), p.stores)
            and _matches(product.strip(), p.products)
        ]
        return "\n\n".join(_format(p) for p in hits) if hits else _NOT_FOUND
