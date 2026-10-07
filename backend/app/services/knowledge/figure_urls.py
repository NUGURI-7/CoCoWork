"""段内插图的临时链接：meta 里存的是对象存储 key，对外换成预签名直链。

浏览器拿直链直接从对象存储取图，图片字节不经后端。签名是后端本地的 HMAC 计算、
不发网络请求，一页几十张图也不构成开销。
"""
from app.core.storage import storage
from app.models.knowledge import Paragraph
from app.schemas.knowledge import FigureOut, RetrievalHit

# 直链有效期（秒）。页面打开时图就加载完了，1 小时足够；翻页 / 刷新会重新签
FIGURE_URL_EXPIRES = 3600


async def sign_figures(meta: dict) -> list[FigureOut]:
    """段 meta → 带直链的图列表，按编号升序。meta 里没有 figures 时返回 []。"""
    figures = sorted(meta.get("figures", []), key=lambda f: f["index"])
    return [
        FigureOut(
            index=f["index"],
            url=await storage.generate_download_url(f["key"], expires=FIGURE_URL_EXPIRES),
        )
        for f in figures
    ]


async def attach_hit_figures(hits: list[RetrievalHit]) -> None:
    """给命中结果回填段内插图。一次查询取回所有命中段的 meta，不做 N+1。"""
    if not hits:
        return
    rows = await Paragraph.filter(id__in=[h.paragraph_id for h in hits]).values("id", "meta")
    metas = {row["id"]: row["meta"] for row in rows}
    for hit in hits:
        hit.figures = await sign_figures(metas.get(hit.paragraph_id, {}))
