"""解析层重构的等价性比对（一次性脚本，验完即可删）。

用真实语料回答一个问题：**把 `raw.decode + _split_paragraphs` 换成
`Parser` 抽象之后，段落切分结果变了没有。**

做法是拿 storage 里的原文件跑新 parser，与库里既有的 Paragraph 逐条比对。
**只读，不写库、不调 embedding**——DB 里的段落是旧实现留下的基线，一旦
用新代码重跑过文档基线就没了，故本脚本只在迁移当次有效。

单测（`tests/test_text_parser.py`）与本脚本分工不同：单测用手编字节考
「实现忠实」、永久回归；这里用 45 份真实文档考「换实现没换结果」、一次性。

用法（在 backend/ 目录下）::

    uv run python -m scripts.verify_parser_parity
    uv run python -m scripts.verify_parser_parity --show-diff   # 打印首个差异详情
"""

import argparse
import asyncio

from app.core.storage import storage
from app.db.postgresql import pg_client
from app.models.knowledge import DocStatus, Document, Paragraph
from app.services.knowledge.parser import get_parser


async def _check(doc: Document, show_diff: bool) -> tuple[str, str]:
    """比对单份文档，返回 (状态, 说明)。"""
    old = [
        p.content
        for p in await Paragraph.filter(document_id=doc.id).order_by("position")
    ]
    if not old:
        return "skip", "库中无段落"

    try:
        raw = await storage.read(doc.storage_key)
    except FileNotFoundError:
        return "skip", "存储中无此对象"

    new = [b.text for b in await get_parser(doc.file_type).parse(raw)]

    if new == old:
        return "ok", f"{len(old)} 段"

    detail = f"旧 {len(old)} 段 / 新 {len(new)} 段"
    if show_diff:
        for i, (o, n) in enumerate(zip(old, new)):
            if o != n:
                detail += f"\n      首个差异 @{i}\n      旧: {o[:80]!r}\n      新: {n[:80]!r}"
                break
        else:
            extra = (new if len(new) > len(old) else old)[min(len(old), len(new)):]
            detail += f"\n      前 {min(len(old), len(new))} 段一致，多出: {extra[0][:80]!r}"
    return "diff", detail


async def main() -> None:
    parser = argparse.ArgumentParser(description="解析层重构等价性比对")
    parser.add_argument("--show-diff", action="store_true", help="打印首个差异详情")
    args = parser.parse_args()

    await pg_client.connect()
    try:
        docs = await Document.filter(status=DocStatus.COMPLETED).order_by("created_at")
        print(f"\n比对 {len(docs)} 份已完成的文档（只读，不写库）\n")

        tally = {"ok": 0, "diff": 0, "skip": 0}
        for doc in docs:
            status, detail = await _check(doc, args.show_diff)
            tally[status] += 1
            if status != "ok":
                mark = "✗" if status == "diff" else "-"
                print(f"  {mark} {doc.name[:42]:<44} {detail}")

        print(
            f"\n一致 {tally['ok']} / 不一致 {tally['diff']} / 跳过 {tally['skip']}"
        )
        if tally["diff"]:
            print("→ 有差异。加 --show-diff 看首个不同的段。")
        else:
            print("→ 全部一致，抽象层未改变既有行为。")
    finally:
        await pg_client.close()


if __name__ == "__main__":
    asyncio.run(main())
