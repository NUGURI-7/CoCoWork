"""PlainTextParser 单测 —— 手编字节、零 DB 零 API。

守的规矩分两类：

1. **解码层的三个坑**（CRLF / BOM / NUL）。它们的共同特征是**静默**——文件
   `cat` 出来正常、编辑器看正常、日志打出来也正常，只有下游的 `^` 正则、
   分词、精确比较会莫名其妙失效。没有测试锁住，日后谁把 `_decode` 里那
   几行「简化」掉，回归不会有任何报错。
2. **刻意不动的东西**（ZWJ / 全角空格）。防的是反向过度清理——把承载语义
   的字符也一并剔了。

样本刻意用真实长度：编码探测是统计性的，几十字节的玩具样本会猜错
（实测 22 字节的 GBK 被判成 EUC-KR），那是样本不现实，不是实现有问题。
"""

import pytest

from app.services.knowledge.parser import get_parser
from app.services.knowledge.parser.base import BlockType
from app.services.knowledge.parser.text_impl import PlainTextParser

# 三段真实长度的中文，覆盖探测所需的统计量
DOC = (
    "向量检索是把文字变成高维向量，再用余弦距离找最近邻，强项是语义匹配。\n\n"
    "关键词检索走全文索引，对专有名词和型号这类精确匹配更稳。\n\n"
    "混合检索用加权 RRF 融合两路名次，兼顾语义与词面。"
)
PARAS = DOC.split("\n\n")

parser = PlainTextParser()


async def _parse(raw: bytes) -> list[str]:
    return [b.text for b in await parser.parse(raw)]


# --- 解码层的三个坑 ---


async def test_crlf_splits_identically_to_lf():
    """CRLF 文档必须与 LF 切出同样的段。

    这是三个坑里最致命的：Windows 的段分隔是 `\\r\\n\\r\\n`，其中并无连续
    的 `\\n\\n`，v1 的 `text.split("\\n\\n")` 在此**整份失效、挤成一段**，
    且现象与 list-heavy 文档的巨段一模一样，事后根本分不清是谁的锅。
    """
    assert await _parse(DOC.replace("\n", "\r\n").encode("utf-8")) == PARAS


async def test_bom_stripped_so_leading_markup_survives():
    """UTF-8 BOM 必须剥掉——它是第二步标题识别的隐形杀手。

    `\\ufeff` 的 Unicode 类别是 Cf 不是空白，`strip()` 去不掉；留着会让
    `^#{1,6}\\s` 匹配失败，于是整份文档的 H1 识别不出来。
    """
    out = await _parse(("﻿# 一级标题\n\n" + DOC).encode("utf-8"))
    assert out[0] == "# 一级标题"


async def test_windows_notepad_combo():
    """记事本存的中文文档 = BOM + CRLF 同时出现，这才是真实输入。"""
    raw = ("﻿" + DOC.replace("\n", "\r\n")).encode("utf-8")
    assert await _parse(raw) == PARAS


async def test_nul_removed_for_postgres():
    """NUL 必须剔除：PostgreSQL 的 text 类型直接拒收，落库会炸。

    类别 Cc，`strip()` 同样去不掉。MaxKB 的 pdf 解析里有一行
    `content.replace("\\0", "")`，同一个坑。
    """
    assert await _parse(DOC.replace("向量", "向\x00量", 1).encode("utf-8")) == PARAS


async def test_zero_width_chars_removed():
    """零宽空格 / 词连接符剔除——与 BOM 同属 Cf，同样打穿正则与分词。"""
    dirty = DOC.replace("关键", "关​键", 1).replace("混合", "混⁠合", 1)
    assert await _parse(dirty.encode("utf-8")) == PARAS


# --- 刻意不动的东西（防过度清理） ---


async def test_emoji_zwj_preserved():
    """ZWJ 承载语义，不可剔——删了 `👨‍👩‍👧` 会碎成三个独立的人。"""
    out = await _parse("👨‍👩‍👧 一家三口\n\n正文段落在这里。".encode("utf-8"))
    assert out[0].startswith("👨‍👩‍👧")


async def test_ideographic_space_preserved():
    """全角空格不剔：中文文档里它常是有意的排版，改了即改内容。

    只守「`_decode` 不主动剔」这一条。段首尾的全角空格仍会被 `.strip()`
    去掉（类别 Zs、`isspace()` 为真），故样本放在句中——两件事不冲突。
    """
    out = await _parse("正文一段。\n\n句中有　　全角空格的一段。".encode("utf-8"))
    assert out[1] == "句中有　　全角空格的一段。"


# --- 编码探测 ---


@pytest.mark.parametrize("encoding", ["utf-8", "gbk", "utf-16"])
async def test_non_utf8_encodings_detected(encoding: str):
    """UTF-8 快路之外，GBK / UTF-16 走探测慢路，结果须与原文一致。

    UTF-16 额外考一件事：它自带 BOM，而探测路径解出的字符串**仍带 BOM**
    （实测确认），故清理不能只依赖 `utf-8-sig`。
    """
    assert await _parse(DOC.encode(encoding)) == PARAS


async def test_big5_traditional_detected():
    """繁体 Big5 另备样本——DOC 是简体，Big5 编不了「检」这类字。

    单列一条是为了证明探测不是只对 GBK 有效（两者字节范围高度重叠，
    分得开才说明探测真在工作）。
    """
    doc = (
        "這是繁體中文的測試文本，用於驗證編碼探測是否正常運作。\n\n"
        "第二段內容放在這裡，長度需足夠讓統計探測生效。"
    )
    assert await _parse(doc.encode("big5")) == doc.split("\n\n")


async def test_undecodable_binary_raises():
    """认不出编码时抛 ValueError，不返回一堆乱码段落污染知识库。"""
    with pytest.raises(ValueError):
        await parser.parse(bytes(range(256)) * 4)


# --- 切段行为（第一步的契约：与 v1 等价） ---


async def test_split_equals_v1_double_newline():
    """按空行切、strip、丢空段——逐字复刻 v1 的 `_split_paragraphs`。"""
    raw = f"  {PARAS[0]}  \n\n\n\n{PARAS[1]}\n\n   \n\n{PARAS[2]}".encode("utf-8")
    assert await _parse(raw) == PARAS


async def test_empty_file_returns_no_blocks():
    assert await parser.parse(b"") == []


async def test_all_blocks_are_paragraph_in_step_one():
    """第一步不认标题：全部 PARAGRAPH，无层级、无页码。

    第二步换 MarkdownParser 后本条会失效——届时该改的是这条断言，不是实现。
    """
    blocks = await parser.parse(("# 看起来像标题\n\n" + DOC).encode("utf-8"))
    assert {b.block_type for b in blocks} == {BlockType.PARAGRAPH}
    assert all(b.heading_level is None and b.page is None for b in blocks)


# --- 装配 ---


def test_each_format_routes_to_its_own_impl():
    """md 与 txt 分派到各自实现。

    第一步两者曾共用 `PlainTextParser`，第二步 md 改道 `MarkdownParser`
    （认 `#` 打标题层级），txt 无结构可言故留在原处。
    """
    from app.services.knowledge.parser.markdown_impl import MarkdownParser

    assert isinstance(get_parser("md"), MarkdownParser)
    assert isinstance(get_parser("txt"), PlainTextParser)


def test_unknown_type_raises_value_error():
    """走到这里还不支持 = 上传白名单与 `_PARSERS` 脱节，属编程错误。"""
    with pytest.raises(ValueError, match="pdf"):
        get_parser("pdf")
