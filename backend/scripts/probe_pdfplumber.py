"""pdfplumber 输出探测 —— 写 `PdfParser` 之前先看清它到底给什么。

**长期保留**：字号启发式的阈值不可能凭空定，只能看真实分布；以后每次调阈值、
换语料都要重跑一遍对照。与 `verify_parser_parity.py` 不同——那个的基线是数据库
状态（重跑即失效），这个的基线是 PDF 文件本身，永远可重跑。

只读，不写库、不调模型。

    uv run python -m scripts.probe_pdfplumber data/pdf/PDF结构测试文档.pdf
    uv run python -m scripts.probe_pdfplumber <pdf> --pages 3 --lines 40
    uv run python -m scripts.probe_pdfplumber <pdf> --thresholds   # 页级判据的分离度

`--thresholds` 是**换语料后重定阈值的入口**：它全文档扫一遍，把三个页级判据
（目录页 / 封面页 / 整页旋转）的实测值逐页打出来，与代码里现行的阈值并排对照。
没有它就只能凭印象拍数——而**凭印象拍必错**，实测教训见设计稿：只采了 3 页样本
得出的 39:0 分离度，放到全语料上直接翻车（正常斜体行的交叠占比同样是 1.00）。
"""

import argparse
import logging
from collections import Counter, defaultdict
from pathlib import Path

import pdfplumber

# 阈值从实现里 import 而不是在这儿抄一份：抄了就会悄悄跑偏，
# 而这个脚本存在的全部意义就是「拿实测分布对照现行阈值」
from app.services.knowledge.parser.pdf_impl import (
    _COVER_MAX_LINES,
    _COVER_SIZE_RATIO,
    _TOC_LEADER,
    _TOC_LINE_RATIO,
    _TOC_MIN_LINES,
)

# pdfminer 对每个缺 FontBBox 的字体刷一条 warning——Chrome 打印出的 PDF 会满屏刷。
# 不影响解析结果（字号/坐标照样拿得到），但会把真正的输出淹掉。
# **`PdfParser` 实装时也得压掉**，否则一份文档能刷出几千行日志。
logging.getLogger("pdfminer").setLevel(logging.ERROR)

# 同一行的 y 坐标容差（pt）。字符的 top 会因字号不同而微差，
# 完全相等的分组会把一行里的大小字拆开
LINE_TOLERANCE = 2.0


def _is_bold(fontname: str) -> bool:
    """字重只能从字体名猜——PDF 里没有独立的 weight 字段。

    答案表把「H1 只比正文大 1pt」列为最关键的陷阱，其解法正是字重；
    故这个判断的可靠性直接决定启发式的上限，要先验证它认不认得出来。
    """
    lowered = fontname.lower()
    return any(k in lowered for k in ("bold", "black", "heavy", "semibold", "medium"))


def _group_lines(chars: list[dict]) -> list[dict]:
    """把字符按 y 坐标聚成行。返回每行的字号 / 字重 / 位置 / 文本。

    行是启发式的最小判断单元——「这一行是不是标题」，而不是「这个字符是不是」。
    一行内字号可能不一致（正文里嵌了上标引用），故取**出现最多的字号**做代表，
    不取平均：平均值会被一个上标拉出一个不存在的字号档。
    """
    buckets: dict[float, list[dict]] = defaultdict(list)
    for ch in chars:
        key = next(
            (k for k in buckets if abs(k - ch["top"]) <= LINE_TOLERANCE), round(ch["top"], 1)
        )
        buckets[key].append(ch)

    lines: list[dict] = []
    for top in sorted(buckets):
        group = sorted(buckets[top], key=lambda c: c["x0"])
        sizes = Counter(round(c["size"], 1) for c in group)
        fonts = Counter(c["fontname"] for c in group)
        lines.append({
            "top": round(top, 1),
            "x0": round(min(c["x0"] for c in group), 1),
            "size": sizes.most_common(1)[0][0],
            "sizes_all": dict(sizes),
            "font": fonts.most_common(1)[0][0],
            "bold": _is_bold(fonts.most_common(1)[0][0]),
            "text": "".join(c["text"] for c in group).strip(),
        })
    return lines


def _probe_thresholds(pdf) -> None:
    """全文档扫一遍，逐页打印三个**页级判据**的实测值，供换语料后重定阈值。

    三个判据对应 `pdf_impl` 里三处按页剔除非正文内容的逻辑：

    | 判据 | 现行阈值 | 拦的是什么 |
    |---|---|---|
    | 目录页 | 点号行占比 ≥ 0.5 且行数 ≥ 5 | 目录条目被切成段、进库、参与检索 |
    | 封面页 | 无正文字号行 + 最大字号 ≥ 正文 ×1.5 + 行数 ≤ 20 | 封面大字被判成 H1/H2 且永不出栈 |
    | 整页旋转 | 该页无任何水平字符 | 竖排表每字一行、顺序全乱 |

    **怎么用**：看「分离度」——命中的页与没命中的页之间应该有一大段空档。
    实测三份语料时，目录页占比 0.83 / 0.74 而其余页恒为 0，中间空了整整 0.7，
    阈值落在 0.5 才有余量。**如果换了语料后发现命中页与正常页的数值挨得很近，
    那就不是调阈值的问题，是这个判据在新语料上不成立**——该换判据，别硬调。
    """
    print(f"\n{'=' * 74}\n6. 页级判据的实测分离度（全 {len(pdf.pages)} 页）\n{'=' * 74}")

    # 正文基准字号按**行数**取众数（与 pdf_impl._body_size 同口径；按字符数会被长行带偏）
    per_page: list[tuple[int, list[dict], int, int]] = []
    line_sizes: Counter[float] = Counter()
    for page_no, page in enumerate(pdf.pages, 1):
        upright = [c for c in page.chars if c.get("upright", True)]
        lines = [ln for ln in _group_lines(upright) if ln["text"]]
        per_page.append((page_no, lines, len(page.chars), len(upright)))
        for ln in lines:
            line_sizes[ln["size"]] += 1

    if not line_sizes:
        print("  （整份文档没有可用文本，无从判起）")
        return
    body = line_sizes.most_common(1)[0][0]
    print(f"  正文基准字号（按行数众数）：{body}\n")
    print(f"  {'页':>4} {'行数':>5} {'点号行占比':>10} {'最大字号÷正文':>13} {'有正文字号行':>12} {'旋转字符':>9}  判定")

    for page_no, lines, n_chars, n_upright in per_page:
        rotated = n_chars - n_upright
        if not lines:
            verdict = "★整页旋转" if rotated else "无文本层"
            print(f"  {page_no:>4} {0:>5} {'—':>10} {'—':>13} {'—':>12} {rotated:>9}  {verdict}")
            continue

        toc_ratio = sum(1 for ln in lines if _TOC_LEADER.search(ln["text"])) / len(lines)
        max_ratio = max(ln["size"] for ln in lines) / body
        has_body = any(ln["size"] == body for ln in lines)

        is_toc = len(lines) >= _TOC_MIN_LINES and toc_ratio >= _TOC_LINE_RATIO
        is_cover = (
            not has_body
            and max_ratio >= _COVER_SIZE_RATIO
            and len(lines) <= _COVER_MAX_LINES
        )
        verdict = "★目录页" if is_toc else ("★封面页" if is_cover else "")
        # 没命中但沾边的页也打出来——分离度要看的正是这些「差一点」的页
        borderline = toc_ratio > 0 or (not has_body) or rotated
        if not (verdict or borderline):
            continue
        print(
            f"  {page_no:>4} {len(lines):>5} {toc_ratio:>10.2f} {max_ratio:>13.2f} "
            f"{str(has_body):>12} {rotated:>9}  {verdict}"
        )

    print(
        f"\n  现行阈值：目录 占比≥{_TOC_LINE_RATIO} 且行数≥{_TOC_MIN_LINES}；"
        f"封面 倍数≥{_COVER_SIZE_RATIO} 且行数≤{_COVER_MAX_LINES} 且无正文字号行"
    )
    print("  （只列命中或沾边的页；全是空白说明这份文档三个判据一个都不触发）")


def main() -> None:
    parser = argparse.ArgumentParser(description="探测 pdfplumber 的输出形态")
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--pages", type=int, default=3, help="读几页")
    parser.add_argument(
        "--start", type=int, default=1,
        help="从第几页开始（1 起）。期刊 PDF 前几页常是下载页 / 摘要页，得跳过才见正文",
    )
    parser.add_argument("--lines", type=int, default=30, help="每页打印前 N 行")
    parser.add_argument(
        "--thresholds", action="store_true",
        help="全文档扫描页级判据（目录页 / 封面页 / 整页旋转）的实测分离度，"
             "换语料重定阈值时跑这个；只出这一节，不打逐行明细",
    )
    args = parser.parse_args()

    with pdfplumber.open(args.pdf) as pdf:
        if args.thresholds:
            print(f"文件：{args.pdf.name}")
            _probe_thresholds(pdf)
            return

        total = len(pdf.pages)
        begin = max(0, args.start - 1)
        pages = pdf.pages[begin : begin + args.pages]

        print(f"文件：{args.pdf.name}")
        print(f"总页数：{total}，本次读第 {begin + 1}~{begin + len(pages)} 页")

        # ---- 1. 字号 × 字重分布：启发式的原料 ----
        size_chars: Counter[tuple[float, bool]] = Counter()
        all_lines: list[list[dict]] = []
        for page in pages:
            lines = _group_lines(page.chars)
            all_lines.append(lines)
            for ln in lines:
                size_chars[(ln["size"], ln["bold"])] += len(ln["text"])

        print(f"\n{'=' * 74}\n1. 字号 × 字重分布（按字符数排序）\n{'=' * 74}")
        print(f"  {'字号':>6} {'字重':>6} {'字符数':>8} {'占比':>7}  猜测")
        body = size_chars.most_common(1)[0][0][0]  # 字符数最多的字号 = 正文基准
        grand = sum(size_chars.values())
        for (size, bold), n in size_chars.most_common():
            guess = "← 正文基准" if size == body and not bold else ""
            if size > body and bold:
                guess = "标题候选（比正文大 + 加粗）"
            elif size > body:
                guess = "比正文大但未加粗"
            elif size < body:
                guess = "比正文小（页眉页脚 / 注释）"
            print(f"  {size:>6} {'粗' if bold else '常规':>6} {n:>8} {n / grand:>6.1%}  {guess}")

        # ---- 2. 页眉页脚：靠位置重复而非字号 ----
        print(f"\n{'=' * 74}\n2. 跨页重复的行（页眉页脚检测：位置 + 重复次数）\n{'=' * 74}")
        repeats: Counter[str] = Counter()
        positions: dict[str, list[float]] = defaultdict(list)
        for lines in all_lines:
            for ln in lines:
                if ln["text"]:
                    repeats[ln["text"]] += 1
                    positions[ln["text"]].append(ln["top"])
        found = [(t, c) for t, c in repeats.items() if c >= max(2, len(pages))]
        if not found:
            print("  （没有完全重复的行——页眉页脚可能带页码，纯文本比对抓不到）")
        for text, count in found:
            print(f"  ×{count}  top≈{positions[text][0]:>6.1f}  {text[:50]}")

        # ---- 3. 逐行明细：直接对照答案表 ----
        for idx, lines in enumerate(all_lines, 1):
            print(f"\n{'=' * 74}\n3.{idx} 第 {idx} 页逐行（前 {args.lines} 行）\n{'=' * 74}")
            print(f"  {'top':>7} {'x0':>6} {'字号':>5} {'粗':>3}  文本")
            for ln in lines[: args.lines]:
                if not ln["text"]:
                    continue
                mixed = "" if len(ln["sizes_all"]) == 1 else f"  ⚠️混{ln['sizes_all']}"
                print(
                    f"  {ln['top']:>7.1f} {ln['x0']:>6.1f} {ln['size']:>5} "
                    f"{'Y' if ln['bold'] else '·':>3}  {ln['text'][:44]}{mixed}"
                )

        # ---- 4. 表格：必须独立成块，不能被拆成正文行 ----
        print(f"\n{'=' * 74}\n4. 表格提取（extract_tables）\n{'=' * 74}")
        for idx, page in enumerate(pages, 1):
            tables = page.extract_tables()
            if not tables:
                continue
            for t_no, table in enumerate(tables, 1):
                print(f"  第 {idx} 页 表{t_no}：{len(table)} 行 × {len(table[0])} 列")
                for row in table[:4]:
                    print("    | " + " | ".join((c or "").replace("\n", " ")[:16] for c in row))

        # ---- 5. 栏数：按 x0 看行首分布 ----
        print(f"\n{'=' * 74}\n5. 行首 x0 分布（判断单栏 / 双栏）\n{'=' * 74}")
        x0s = Counter(ln["x0"] for lines in all_lines for ln in lines if ln["text"])
        for x0, n in sorted(x0s.items())[:12]:
            print(f"  x0={x0:>6}  {n:>4} 行  {'█' * min(n, 40)}")
        spread = max(x0s) - min(x0s) if x0s else 0
        print(f"\n  x0 跨度 {spread:.1f}pt —— 单栏文档的行首应聚在少数几个值上"
              f"（正文缩进 + 标题顶格）；双栏会明显分成左右两簇")


if __name__ == "__main__":
    main()
