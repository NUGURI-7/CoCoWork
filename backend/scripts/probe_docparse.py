"""PaddleOCR-VL 文档解析探针（一次性实验脚本，不进产品）。

目的：搞清硅基流动的 OpenAI 兼容接口调 PaddleOCR-VL 时，
**返回体里到底有没有结构化版面信息（元素类型 / 坐标 / 页码）**，
还是只有一段 markdown 文本。结论决定 DocumentBlock 要不要留坐标字段。

先跑 `--list` 看库里有哪些 provider / model，再跑正式探测。

用法（在 backend/ 目录下）::

    uv run python -m scripts.probe_docparse --list
    uv run python -m scripts.probe_docparse --image <图片路径> --model <模型名>
"""

import argparse
import asyncio
import base64
import json
from pathlib import Path

from app.core.encryption import decrypt
from app.db.postgresql import pg_client
from app.models.model import AIModel, Provider
from app.services.model.model_client import ModelClient


async def _list() -> None:
    """列出库里的 provider / model，便于挑探测目标。"""
    providers = await Provider.all()
    print(f"\n=== Provider（{len(providers)}）===")
    for p in providers:
        print(f"  {p.id}  type={p.provider_type:<16} name={p.name:<20} base_url={p.base_url}")

    models = await AIModel.all().prefetch_related("provider")
    print(f"\n=== AIModel（{len(models)}）===")
    for m in models:
        print(f"  {m.id}  type={m.model_type:<10} {m.model_name:<40} provider={m.provider.name}")


async def _probe(image_path: Path, model_name: str, prompt: str, max_tokens: int) -> None:
    """拿库里任一 siliconflow provider 的凭证，直接打 chat/completions 看返回体。"""
    provider = await Provider.filter(provider_type="siliconflow").first()
    if provider is None:
        # 兜底：按 base_url 认
        provider = await Provider.filter(base_url__icontains="siliconflow").first()
    if provider is None:
        print("！库里没有 siliconflow provider，先用 --list 看看有哪些")
        return

    api_key = decrypt(provider.api_key_encrypted)
    client = ModelClient.build_client(provider.base_url, api_key)

    b64 = base64.b64encode(image_path.read_bytes()).decode()
    suffix = image_path.suffix.lstrip(".").lower()
    mime = "image/jpeg" if suffix in {"jpg", "jpeg"} else f"image/{suffix}"

    print(f"\n→ provider={provider.name}  base_url={provider.base_url}")
    print(f"→ model={model_name}  image={image_path.name}（{len(b64)} b64 chars）")
    print(f"→ prompt={prompt!r}  max_tokens={max_tokens}\n")

    resp = await client.chat.completions.create(
        model=model_name,
        max_tokens=max_tokens,
        messages=[{
            "role": "user",
            "content": [
                {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}},
                {"type": "text", "text": prompt},
            ],
        }],
    )

    raw = resp.model_dump()
    print("=== 顶层字段 ===")
    print(list(raw.keys()))
    print("\n=== choices[0] 字段 ===")
    print(list(raw["choices"][0].keys()))
    print("\n=== choices[0].message 字段 ===")
    print(list(raw["choices"][0]["message"].keys()))
    print("\n=== 完整返回体（截断 content）===")
    trimmed = json.loads(json.dumps(raw, ensure_ascii=False))
    content = trimmed["choices"][0]["message"].get("content") or ""
    trimmed["choices"][0]["message"]["content"] = f"<{len(content)} chars，见下>"
    print(json.dumps(trimmed, ensure_ascii=False, indent=2))
    print("\n=== content 前 2000 字 ===")
    print(content[:2000])


async def main() -> None:
    parser = argparse.ArgumentParser(description="PaddleOCR-VL 返回体探针")
    parser.add_argument("--list", action="store_true", help="只列 provider / model")
    parser.add_argument("--image", help="要解析的图片路径（PDF 需先转图）")
    parser.add_argument("--model", default="PaddlePaddle/PaddleOCR-VL-1.5", help="模型名")
    parser.add_argument(
        "--prompt", default="OCR:",
        help="官方任务 prompt：OCR: / Table Recognition: / Formula Recognition: / Chart Recognition:",
    )
    parser.add_argument("--max-tokens", type=int, default=4096, help="上限，防重复生成烧光额度")
    args = parser.parse_args()

    await pg_client.connect()
    try:
        if args.list or not args.image:
            await _list()
            return
        await _probe(Path(args.image), args.model, args.prompt, args.max_tokens)
    finally:
        await pg_client.close()


if __name__ == "__main__":
    asyncio.run(main())
