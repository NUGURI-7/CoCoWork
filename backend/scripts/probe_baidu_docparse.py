"""百度文档解析（PaddleOCR-VL）返回结构探测 —— 写 `BaiduDocParser` 之前先看清它到底给什么。

用法：
    uv run python -m scripts.probe_baidu_docparse ../data/pdf/PDF结构测试文档.pdf
    uv run python -m scripts.probe_baidu_docparse --replay out/baidu_parse_result.json

**额度有限（免费 200 页），跑一次就把原始返回整个存到 `out/`**，之后所有分析
走 `--replay` 读本地文件，不重复烧额度。

凭证从库里的 baidu provider 读，不走命令行参数——AK/SK 不该出现在 shell history 里。
"""

import argparse
import asyncio
import base64
import json
import sys
from collections import Counter
from pathlib import Path

import httpx

from app.db.postgresql import pg_client
from app.models.model import Provider
from app.services.model.credentials import load_credentials

TOKEN_URL = "https://aip.baidubce.com/oauth/2.0/token"
SUBMIT_PATH = "/rest/2.0/brain/online/v2/paddle-vl-parser/task"
QUERY_PATH = "/rest/2.0/brain/online/v2/paddle-vl-parser/task/query"

OUT_DIR = Path(__file__).resolve().parent.parent / "out"

# 官方建议提交后 5～10 秒开始轮询；查询接口 QPS 5，间隔给足
POLL_INTERVAL = 6.0
POLL_TIMEOUT = 600.0


async def _fetch_token(client: httpx.AsyncClient, api_key: str, secret_key: str) -> str:
    """AK + SK 换 access_token（有效期 30 天）。"""
    resp = await client.post(
        TOKEN_URL,
        params={
            "grant_type": "client_credentials",
            "client_id": api_key,
            "client_secret": secret_key,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    if "access_token" not in data:
        raise RuntimeError(f"换 token 失败：{data}")
    print(f"✓ access_token 到手，有效期 {data.get('expires_in')} 秒")
    return data["access_token"]


async def _submit(
    client: httpx.AsyncClient, base_url: str, token: str, pdf: Path,
) -> str:
    """提交解析任务，返回 task_id。"""
    # 百度 AIP 的老规矩：body 是 form-urlencoded，不是 JSON（发 JSON 会回
    # 282003 missing parameters）。布尔值也得是字符串 "true" / "false"。
    payload = {
        "file_data": base64.b64encode(pdf.read_bytes()).decode(),
        "file_name": pdf.name,
        "relevel_titles": "true",      # 标题分级 —— 本片要的就是它
        "merge_tables": "true",        # 合并跨页表格
        "return_span_boxes": "true",   # 行级坐标（给日后 bbox 高亮留）
    }
    resp = await client.post(
        f"{base_url}{SUBMIT_PATH}", params={"access_token": token}, data=payload,
    )
    resp.raise_for_status()
    data = resp.json()
    if data.get("error_code"):
        raise RuntimeError(f"提交失败 error_code={data['error_code']}: {data.get('error_msg')}")
    task_id = data["result"]["task_id"]
    print(f"✓ 已提交，task_id={task_id}")
    return task_id


async def _poll(
    client: httpx.AsyncClient, base_url: str, token: str, task_id: str,
) -> dict:
    """轮询直到 success / failed，返回 result 体。"""
    waited = 0.0
    while waited < POLL_TIMEOUT:
        await asyncio.sleep(POLL_INTERVAL)
        waited += POLL_INTERVAL

        resp = await client.post(
            f"{base_url}{QUERY_PATH}",
            params={"access_token": token},
            data={"task_id": task_id},
        )
        resp.raise_for_status()
        data = resp.json()
        if data.get("error_code"):
            raise RuntimeError(f"查询失败 error_code={data['error_code']}: {data.get('error_msg')}")

        result = data["result"]
        status = result.get("status")
        print(f"  [{waited:>5.0f}s] status={status}")
        if status == "success":
            return result
        if status == "failed":
            raise RuntimeError(f"解析失败：{result}")
    raise TimeoutError(f"轮询超过 {POLL_TIMEOUT}s 仍未完成")


async def _run(pdf: Path) -> None:
    await pg_client.connect()
    provider = await Provider.filter(provider_type="baidu").first()
    if provider is None:
        sys.exit("！库里没有 baidu provider，先在页面上建一个")
    creds = load_credentials(provider.provider_type, provider.credentials_encrypted)
    secret_key = getattr(creds, "secret_key", "")
    if not secret_key:
        sys.exit("！这个 provider 的凭证里没有 secret_key")

    print(f"→ provider={provider.name}  base_url={provider.base_url}")
    print(f"→ 文件={pdf.name}（{pdf.stat().st_size / 1024:.0f} KB）\n")

    async with httpx.AsyncClient(timeout=120.0) as client:
        token = await _fetch_token(client, creds.api_key, secret_key)
        task_id = await _submit(client, provider.base_url, token, pdf)
        result = await _poll(client, provider.base_url, token, task_id)

        # 文件名带上源 PDF 名——跑第二份文档时不会把第一份的结果盖掉
        OUT_DIR.mkdir(exist_ok=True)
        stem = f"baidu_{pdf.stem}"
        (OUT_DIR / f"{stem}_task_result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2)
        )
        print(f"\n✓ 任务结果已存 → out/{stem}_task_result.json")
        print(f"  markdown_url     = {result.get('markdown_url', '')[:80]}...")
        print(f"  parse_result_url = {result.get('parse_result_url', '')[:80]}...")

        # 两个链接 30 天有效，趁现在整个拉下来存本地
        for key, name in (
            ("parse_result_url", f"{stem}_parse_result.json"),
            ("markdown_url", f"{stem}_result.md"),
        ):
            url = result.get(key)
            if not url:
                continue
            r = await client.get(url)
            r.raise_for_status()
            (OUT_DIR / name).write_bytes(r.content)
            print(f"✓ 已下载 → out/{name}（{len(r.content) / 1024:.0f} KB）")

    await pg_client.close()
    _report(json.loads((OUT_DIR / f"{stem}_parse_result.json").read_text()))


def _report(parsed: dict) -> None:
    """把结构摘要打出来 —— 重点是 IR 映射要用到的那几个字段。"""
    print(f"\n{'=' * 70}\n结构摘要\n{'=' * 70}")
    print("顶层键:", list(parsed.keys()))

    pages = parsed.get("pages", [])
    print(f"\npages 共 {len(pages)} 页")
    if not pages:
        print(json.dumps(parsed, ensure_ascii=False, indent=2)[:2000])
        return

    print("单页的键:", list(pages[0].keys()))
    print("page_num 序列:", [p.get("page_num") for p in pages], "← 确认从 0 还是 1 起")

    types: Counter = Counter()
    sub_types: Counter = Counter()
    layout_keys: set = set()
    for page in pages:
        for layout in page.get("layouts", []):
            types[layout.get("type")] += 1
            sub_types[layout.get("sub_type")] += 1
            layout_keys |= set(layout.keys())

    print("\nlayout 元素的键:", sorted(layout_keys))
    print("type 取值分布:", dict(types))
    print("sub_type 取值分布:", dict(sub_types), "← 标题层级长什么样")

    for page in pages:
        for layout in page.get("layouts", []):
            if layout.get("sub_type"):
                print("\n带 sub_type 的块示例:")
                print(json.dumps(layout, ensure_ascii=False, indent=2)[:700])
                break
        else:
            continue
        break

    tables = [t for p in pages for t in p.get("tables", [])]
    print(f"\ntables 共 {len(tables)} 个")
    if tables:
        print("table 的键:", sorted(tables[0].keys()))
        print(json.dumps(tables[0], ensure_ascii=False, indent=2)[:700])


def main() -> None:
    ap = argparse.ArgumentParser(description="探测百度文档解析 API 的返回形态")
    ap.add_argument("pdf", type=Path, nargs="?", help="要解析的 PDF")
    ap.add_argument("--replay", type=Path, help="不调 API，直接分析本地已存的 parse_result JSON")
    args = ap.parse_args()

    if args.replay:
        _report(json.loads(args.replay.read_text()))
        return
    if not args.pdf or not args.pdf.exists():
        ap.error("需要一个存在的 PDF 路径（或用 --replay 分析本地结果）")
    asyncio.run(_run(args.pdf))


if __name__ == "__main__":
    main()
