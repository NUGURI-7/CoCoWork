"""MCP server 运行时连接：连上外部 server、拉取它暴露的工具。

测试连接、Agent 装配工具都走这里。无状态、按需连接，连接前过 SSRF 校验。
"""
import asyncio
import ipaddress
import json
import logging
import socket
from urllib.parse import urlparse

from langchain_core.tools import BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient

from app.core.encryption import decrypt
from app.models.mcp import MCPServer

logger = logging.getLogger(__name__)


class MCPConnectionError(Exception):
    """MCP server 连接 / 校验失败（含 SSRF 拦截、握手、鉴权、超时）。"""


# SSRF 拦截网段：精确列举真正危险的（内网 / 回环 / 链路本地含元数据 /
# IPv6 ULA）。不用 ipaddress.is_private —— 它还涵盖 198.18/15 benchmark、
# 100.64/10 CGNAT 等「非全局但也非攻击目标」的网段，会误伤本地代理的
# fake-ip（如 Clash/Surge 把域名映射到 198.18.x）。
_BLOCKED_NETS = [
    ipaddress.ip_network("0.0.0.0/8"),       # 本机 / 未指定
    ipaddress.ip_network("10.0.0.0/8"),      # RFC1918 内网
    ipaddress.ip_network("172.16.0.0/12"),   # RFC1918 内网
    ipaddress.ip_network("192.168.0.0/16"),  # RFC1918 内网
    ipaddress.ip_network("127.0.0.0/8"),     # 回环
    ipaddress.ip_network("169.254.0.0/16"),  # 链路本地，含云元数据 169.254.169.254
    ipaddress.ip_network("::1/128"),         # IPv6 回环
    ipaddress.ip_network("fc00::/7"),        # IPv6 ULA
    ipaddress.ip_network("fe80::/10"),       # IPv6 链路本地
]


def _is_blocked_ip(ip: str) -> bool:
    """IP 是否落在受限网段（精确列举，见 _BLOCKED_NETS）。"""
    addr = ipaddress.ip_address(ip)
    return any(addr in net for net in _BLOCKED_NETS)


async def _guard_ssrf(server_url: str) -> None:
    """SSRF 防护：只允许 http/https，且目标 IP 不得指向内网 / 保留地址。

    解析 hostname → 所有 A/AAAA 记录，任一落在受限网段就拒。用 loop 的
    异步 DNS，避免阻塞事件循环。

    注意：这是「解析时」校验，不防 DNS rebinding（校验后 IP 再变化）——
    完整防护需 pin IP 连接，v1 不做；但直填内网地址 / 解析到内网的域名
    这类绝大多数 SSRF 已被拦下。
    """
    parsed = urlparse(server_url)
    if parsed.scheme not in ("http", "https"):
        raise MCPConnectionError(f"不支持的协议：{parsed.scheme or '空'}")
    host = parsed.hostname
    if not host:
        raise MCPConnectionError("URL 缺少主机名")

    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(host, None)
    except socket.gaierror as e:
        raise MCPConnectionError(f"域名解析失败：{host}") from e

    for info in infos:
        ip = info[4][0]
        if _is_blocked_ip(ip):
            raise MCPConnectionError(f"禁止连接内网 / 保留地址（{host} → {ip}）")


def _build_connection(
    server_url: str, transport: str, headers: dict[str, str] | None
) -> dict:
    """构造 langchain-mcp-adapters 的单 server 连接配置。

    transport 直接透传（'streamable_http' / 'sse'），对齐 TypedDict
    StreamableHttpConnection / SSEConnection 的字段；headers 为空则不带。
    """
    conn: dict = {"transport": transport, "url": server_url}
    if headers:
        conn["headers"] = headers
    return conn


async def fetch_mcp_tools(
    server_url: str, transport: str, headers: dict[str, str] | None
) -> list[BaseTool]:
    """连接一个 MCP server，拉取它暴露的工具（initialize + tools/list）。

    连接前先过 SSRF 校验。无状态、按需连接：每次新建 client、跑一次
    get_tools、用完即弃——跟「每请求新建 ChatModel」「per-KB 实例化
    retriever tool」同一逻辑。成功返回可直接装进 agent 的 BaseTool 列表；
    SSRF 拦截 / 连接 / 握手 / 鉴权失败 raise（SSRF 抛 MCPConnectionError）。
    """
    await _guard_ssrf(server_url)
    client = MultiServerMCPClient(
        {"server": _build_connection(server_url, transport, headers)}
    )
    return await client.get_tools()


async def fetch_tools_for_server(server: MCPServer) -> list[BaseTool]:
    """从一条 MCPServer 记录解密 headers、连上拉工具（装配链用）。

    失败会 raise（SSRF / 连接 / 握手 / 鉴权）——由调用方 assemble_tools
    容错跳过，单个 server 挂掉不连累整个 agent 装配。
    """
    headers = (
        json.loads(decrypt(server.headers_encrypted))
        if server.headers_encrypted
        else None
    )
    return await fetch_mcp_tools(server.server_url, server.transport, headers)
