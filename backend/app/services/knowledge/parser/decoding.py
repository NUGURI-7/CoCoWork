"""文本字节 → 字符串。所有文本类 parser 共用，故独立成模块。

这里修的三个坑（CRLF / BOM / NUL）共同特征是**静默**：文件 cat 出来
正常、编辑器看正常，只有下游的 `^` 正则、分词、精确比较会莫名失效。
**修在入口而非各下游各自防御**——下游有多少处就要防多少处，且每处都会忘。
"""

from charset_normalizer import from_bytes

# 剔除的不可见字符：BOM / 零宽空格 / 词连接符 / NUL。写转义序列不写字面
# 字符——后者在编辑器里同样看不见，改坏了没人发现。
# 刻意**不剔** U+200C ZWNJ 与 U+200D ZWJ：前者是波斯语等的构词符，后者是
# emoji 组合的连接符（删了 👨‍👩‍👧 会碎成三个人），它们承载语义。
_INVISIBLE = str.maketrans("", "", "\ufeff\u200b\u2060\x00")


def decode_text(raw: bytes) -> str:
    """解码文本字节并做最小规范化。识别不出编码时抛 `ValueError`。

    **编码**：先试 `utf-8-sig` 而非 `utf-8`——前者兼容带 BOM 的 UTF-8
    （Windows 记事本默认存法），后者会把 BOM 解成开头一个不可见的
    `\\ufeff`。失败才做探测：UTF-8 是绝大多数情况、直接解码成功是确定的，
    探测则是概率的且要扫字节做统计，故「快路优先、慢路兜底」。

    **换行**：CRLF / CR 统一成 LF。否则 Windows 文档的段分隔是
    `\\r\\n\\r\\n`，其中并无连续的 `\\n\\n`，**按空行切段会整份失效、
    挤成一段**——比 BOM 严重得多。

    **不可见字符**：`\\ufeff` 等的 Unicode 类别是 Cf、`\\x00` 是 Cc，
    **`strip()` 一个都去不掉**；它们会让 `^#` 正则、jieba 分词、精确
    比较静默失效，`\\x00` 更会被 PostgreSQL 直接拒收。探测路径解出的
    UTF-16 仍带 BOM（实测确认），故此处统一清理、不依赖 `utf-8-sig`。
    """
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        detected = from_bytes(raw).best()
        if detected is None:
            raise ValueError("无法识别文件编码")
        text = str(detected)

    text = text.replace("\r\n", "\n").replace("\r", "\n")
    return text.translate(_INVISIBLE)