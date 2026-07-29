"""文档解析（云端路）：百度文档解析 API（PaddleOCR-VL）。

分两层，靠函数边界隔开：

- **运输层**（`_access_token` / `_submit` / `_poll` / `_download`）——异步接口，
  提交拿取件单、轮询到完成、再发一次 HTTP 把结构化结果拉下来。全程跑在 SAQ
  worker 里，web 侧不参与。
- **翻译层**（`blocks_from_parse_result` 及其下属）——纯函数，只认 `parse_result`
  这个 dict，不关心它是现调 API 来的还是读的本地存档。故映射逻辑能拿 `out/` 里
  的存档直接跑，**改映射不烧解析额度**。

百度返回的形状（实测确认，非文档推断）：
    {"pages": [{"page_num": 0, "layouts": [...], "tables": [...]}]}
页码从 **0** 起，标题层级是 `title_1` / `title_2` … 这类字符串。

**只取 `parse_result_url`，不取 `markdown_url`**：两者逐字比对过，正文 / LaTeX /
表格 markdown / 标题层级完全一致，但 markdown 里**没有页码**——而页码是引用溯源
（roadmap P4）的上游，解析这步不存后面补不回来。markdown 是装订好的书，
parse_result 是散页加标注。
"""
import asyncio
import base64
import logging
import re
from typing import Any

import httpx

from app.core.config import settings
from app.core.redis import redis_client
from app.services.knowledge.parser.base import BlockType, DocumentBlock, Parser

logger = logging.getLogger(__name__)


# 百度 AIP 的固定端点。不进 config —— 这是代码事实（百度的地址就长这样），
# 不是部署变量（换台机器不会变）
_BASE_URL = "https://aip.baidubce.com"
_TOKEN_URL = f"{_BASE_URL}/oauth/2.0/token"

# 官方有效期 30 天，缓存故意设 29：宁可多兑换一次，
# 也不要拿着刚过期的票去调接口，再吃一个看不懂的 401
_TOKEN_CACHE_KEY = "baidu:docparse:access_token"
_TOKEN_TTL = 29 * 24 * 3600


async def _access_token(client: httpx.AsyncClient) -> str:
    """AK/SK 换 access_token，命中缓存则直接返回。

    Redis 的 TTL 天然就是「有效期」—— key 到点自己消失，不必另存过期时间，
    也不必写「过没过期」的判断。
    """
    redis = redis_client.client
    cached = await redis.get(_TOKEN_CACHE_KEY)
    if cached:
        return cached

    api_key = settings.BAIDU_DOCPARSE_API_KEY
    secret_key = settings.BAIDU_DOCPARSE_SECRET_KEY

    if not (api_key and secret_key):
        # 库选了 baidu 但部署侧没配 Key —— 建库时本该拦下；拦漏了就在这儿炸，
        # 别拿空 Key 去发请求，换回一个看不懂的鉴权错误
        raise RuntimeError(
            "未配置百度文档解析凭证：BAIDU_DOCPARSE_API_KEY / BAIDU_DOCPARSE_SECRET_KEY",
        )

    resp = await client.post(
        _TOKEN_URL,
        params={
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        },
    )
    resp.raise_for_status()
    data = resp.json()

    token = data.get("access_token")
    if not token:
        # AK/SK 不对时百度回的是 **200** + {"error": "invalid_client", ...}，
        # 没有 access_token 字段 —— 故成败不能只靠 raise_for_status 判
        raise RuntimeError(f"百度换 token 失败：{data.get('error_description') or data}")

    await redis.set(_TOKEN_CACHE_KEY, token, ex=_TOKEN_TTL)
    return token


_SUBMIT_URL = f"{_BASE_URL}/rest/2.0/brain/online/v2/paddle-vl-parser/task"


async def _submit(
        client: httpx.AsyncClient, token: str, raw: bytes, file_name: str,
) -> str:
    """提交解析任务，返回取件单号 task_id。"""
    # 百度 AIP 的老规矩（实测踩出来的）：body 是 form-urlencoded 而非 JSON
    # —— 发 JSON 会回 282003 missing parameters；布尔值也得写成字符串 "true"
    payload = {
        "file_data": base64.b64encode(raw).decode(),
        "file_name": file_name,  # 百度靠后缀判文件类型，名字本身无所谓
        "relevel_titles": "true",  # 标题分级 —— 本片存在的全部理由就是它
        "merge_tables": "true",  # 合并跨页表格
    }
    resp = await client.post(
        _SUBMIT_URL, params={"access_token": token}, data=payload,
    )
    resp.raise_for_status()
    data = resp.json()

    # 同 token 那步：百度业务失败照样回 200，错误在 body 里
    if data.get("error_code"):
        raise RuntimeError(
            f"百度提交解析失败 error_code={data['error_code']}：{data.get('error_msg')}",
        )
    return data["result"]["task_id"]


_QUERY_URL = f"{_BASE_URL}/rest/2.0/brain/online/v2/paddle-vl-parser/task/query"

# 官方建议提交后 5~10 秒再开始问；查询接口 QPS 限 5，间隔给足不去蹭上限
_POLL_INTERVAL = 6.0
_POLL_TIMEOUT = 600.0

# 单次 HTTP 超时；整趟解析要多久由 _POLL_TIMEOUT 管，两者不是一回事
_HTTP_TIMEOUT = 120.0


async def _poll(
        client: httpx.AsyncClient, token: str, task_id: str,
) -> dict[str, Any]:
    """拿着取件单反复问，直到 success。返回 result 体（含两个下载链接）。"""
    waited = 0.0
    while waited < _POLL_TIMEOUT:
        # 先睡后问：刚提交必然还没好，立刻问一次是白扔一个 QPS 配额
        await asyncio.sleep(_POLL_INTERVAL)
        waited += _POLL_INTERVAL

        resp = await client.post(
            _QUERY_URL, params={"access_token": token}, data={"task_id": task_id},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error_code"):
            raise RuntimeError(
                f"百度查询任务失败 error_code={data['error_code']}：{data.get('error_msg')}",
            )

        result = data["result"]
        status = result.get("status")
        if status == "success":
            return result
        if status == "failed":
            # 失败原因百度塞在 result 里，整个带上供排查
            raise RuntimeError(f"百度解析失败 task_id={task_id}：{result}")

        logger.debug("百度解析中 task_id=%s status=%s 已等 %.0fs", task_id, status, waited)

    raise TimeoutError(f"百度解析轮询超时（{_POLL_TIMEOUT:.0f}s）task_id={task_id}")


async def _download(client: httpx.AsyncClient, result: dict[str, Any]) -> dict[str, Any]:
    """下载 parse_result —— 结构化数据不在返回体里，接口只给了链接。"""
    url = result.get("parse_result_url")
    if not url:
        raise RuntimeError(f"百度返回里没有 parse_result_url：{result}")

    # 对象存储直链，不带 access_token；30 天有效，但我们当场就拉
    resp = await client.get(url)
    resp.raise_for_status()
    return resp.json()


# 百度 layout.type → 我们的块类型。实测见过的取值：
# header / footer / number（页眉页脚页码，纯噪声，丢）
# text（正文）/ paragraph_title（标题）/ table（表格）
# figure_title（图表标题——实测在论文里全是表标题，「表2-3 粉煤灰基本性能参数」）
# vision_footnote（脚注）
#
# figure_title 与 vision_footnote 留成正文：表标题是「这张表讲什么」的唯一线索，
# 丢了下游只剩一堆裸数字；脚注同理，常含引用出处。
_TYPE_MAP: dict[str, BlockType] = {
    "text": BlockType.PARAGRAPH,
    "paragraph_title": BlockType.HEADING,
    "table": BlockType.TABLE,
    "figure_title": BlockType.PARAGRAPH,
    "vision_footnote": BlockType.PARAGRAPH,
}

# 认不出的 type 一律丢弃，而不是降级成正文——parse-don't-validate 在这里要
# 反过来用：百度的 type 是封闭枚举，冒出没见过的值多半是新的非正文元素
# （印章、水印之类），当正文收进来是污染，宁可漏不可脏。
_DROP_TYPES = frozenset({"header", "footer", "number"})

_TITLE_LEVEL = re.compile(r"^title_(\d+)$")


def _heading_level(sub_type: str) -> int | None:
    """`title_3` → 3。认不出的层级返回 None，由调用方降级处理。"""
    match = _TITLE_LEVEL.match(sub_type or "")
    return int(match.group(1)) if match else None


def _to_block(
        layout: dict[str, Any], page: int | None, table_markdowns: dict[str, str],
) -> DocumentBlock | None:
    """单个 layout → 块。该丢的返回 None。"""
    layout_type = layout.get("type", "")
    if layout_type in _DROP_TYPES:
        return None

    block_type = _TYPE_MAP.get(layout_type)
    if block_type is None:
        logger.info("跳过未登记的 layout type=%r", layout_type)
        return None

    if block_type is BlockType.TABLE:
        # 拿不到就是空串，落到下面那道空文本检查里整块丢掉——宁可少一张表，
        # 也不能把 layouts 里那坨 table_html 当正文 embed 进去
        text = table_markdowns.get(layout.get("layout_id", ""), "")
    else:
        text = layout.get("text", "")

    text = text.strip()
    if not text:
        return None

    level: int | None = None
    if block_type is BlockType.HEADING:
        level = _heading_level(layout.get("sub_type", ""))
        if level is None:
            logger.warning(
                "标题层级认不出 sub_type=%r，降级为正文：%.20s",
                layout.get("sub_type"), text,
            )
            block_type = BlockType.PARAGRAPH

    return DocumentBlock(
        text=text, block_type=block_type, heading_level=level, page=page,
    )


def blocks_from_parse_result(parsed: dict[str, Any]) -> list[DocumentBlock]:
    """百度 `parse_result` → 块列表，顺序即阅读顺序。

    `pages` 与页内 `layouts` 百度都按阅读顺序给，照单遍历即可，不必自己排。
    """
    blocks: list[DocumentBlock] = []

    for page in parsed.get("pages", []):
        # 百度的 page_num 从 0 起，IR 的 page 从 1 起
        raw_page = page.get("page_num")
        page_no = raw_page + 1 if isinstance(raw_page, int) else None

        # 表格块在 layouts 里的 text 是一坨 table_html，真正要的 markdown
        # 在同页的 tables[] 里，两边靠 layout_id 认亲
        table_markdowns = {
            table.get("layout_id", ""): table.get("markdown", "")
            for table in page.get("tables", [])
        }

        for layout in page.get("layouts", []):
            block = _to_block(layout, page_no, table_markdowns)
            if block is not None:
                blocks.append(block)

    return blocks


class BaiduDocParser(Parser):
    """把上面两层串起来：文件字节 → 百度 → IR 块列表。

    一份文档十几秒量级（提交 + 轮询），故只在 worker 里跑，别放进请求链路。
    """

    def __init__(self, file_ext: str = "pdf") -> None:
        # 百度靠文件名后缀判类型，而 `Parser.parse` 只收字节、不收文件名，
        # 故后缀在装配时定死（见 parser/__init__.py 的 _PARSERS）。
        # 不为百度一家把 file_name 塞进 ABC —— 本地那三个解析器都不需要它
        self._file_ext = file_ext

    async def parse(self, raw: bytes) -> list[DocumentBlock]:
        if not raw:
            return []  # 对齐 ABC 约定，也免得拿空 body 白烧一次额度

        # 每次 parse 新建 client：复用连接池更省，但要管生命周期（谁建谁关、
        # worker 重启怎么办）。一份文档才三四次 HTTP、十几秒一趟，不是高频
        # 路径，简单可靠优先
        async with httpx.AsyncClient(timeout=_HTTP_TIMEOUT) as client:
            token = await _access_token(client)
            task_id = await _submit(client, token, raw, f"document.{self._file_ext}")
            result = await _poll(client, token, task_id)
            parsed = await _download(client, result)

        return blocks_from_parse_result(parsed)
