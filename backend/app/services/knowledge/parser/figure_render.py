"""PDF 区域截图：本地路与云端路共用的「按框裁图」。

两条解析路认图的方式不同（本地读 PDF 里的嵌入位图，云端靠版面模型给框），
但拿到框之后的事一样：在原 PDF 上裁出这块、渲染成 PNG。
"""
from io import BytesIO

# 抽图渲染分辨率（DPI）。150 比默认 72 清楚、又不至于让单图体积失控
FIGURE_RESOLUTION = 150


def render_region(page, bbox: tuple[float, float, float, float]) -> bytes:
    """把页面上 bbox 这块区域渲染成 PNG 字节。bbox 是 pdfplumber 的 (左, 上, 右, 下)。

    **渲染区域而非抽原始图流**：原始图流有各种颜色空间 / 掩膜 / 变换，直接取出
    要自己处理一堆编码；裁页面再渲染，pdfplumber（底层 pypdfium2）把这些都算好，
    拿到的恒是一张规整 RGB 位图。
    """
    cropped = page.crop(bbox)
    out = BytesIO()
    cropped.to_image(resolution=FIGURE_RESOLUTION).save(out, format="PNG")
    return out.getvalue()
