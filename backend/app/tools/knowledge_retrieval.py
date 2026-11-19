"""知识库检索工具 —— per-KB bound 实例。

跟 builtin 单例工具的本质不同：
- builtin tool（calculator）= 全局单例、无状态、registry 启动期注册
- KB tool = per-KB 实例、绑定 kb_id + user、装配阶段动态实例化、不进 registry

LLM 选库靠 description（拼装时塞 KB 名 + 描述），name 只是身份标识。
"""

import re
from collections.abc import Sequence
from typing import Literal
from uuid import UUID

from langchain_core.tools import BaseTool
from pydantic import BaseModel, ConfigDict, Field

from app.core.identifiers import short_id
from app.models import User
from app.models.knowledge import RetrievalMode
from app.schemas.knowledge import RetrievalHit
from app.services.knowledge.figure_urls import figure_ref
from app.services.knowledge.retrieval import RetrievalParams, RetrievalService
from app.tools.base import ClientArtifact, CoCoTool, ToolCategory, ToolSourceType

# 段内图记号 [[figure:N]]，格式与 parser/base.py 的 figure_marker 一致
_FIGURE_MARKER_RE = re.compile(r"\[\[figure:(\d+)\]\]")

# RetrievalService 无状态（dispatch 表是类属性），模块级共享一个实例。
_retrieval_service = RetrievalService()


class KnowledgeRetrievalInput(BaseModel):
    query: str = Field(..., description="要检索的查询文本")


class KnowledgeHitRef(BaseModel):
    """一个命中段的出处 —— 前端把回答里的 [[cite:<ref>]] 换成角标、弹窗展示原文时查的就是它。"""

    ref: str
    paragraph_id: UUID
    document_id: UUID
    doc_name: str
    title: str
    page: int | None
    content: str


class KnowledgeHitsArtifact(ClientArtifact):
    """本次命中的段 —— 前端拿 paragraph_ids 换段内插图的签名链接，拿 hits 解析回答里的引用记号。"""

    kind: Literal["knowledge_hits"] = "knowledge_hits"
    paragraph_ids: list[UUID]
    hits: list[KnowledgeHitRef]


class KnowledgeRetrievalTool(CoCoTool):
    """单库语义检索 —— per-KB bound 实例化。

    name / description / display_name 由调用方按 KB 信息拼装传入；
    每个 KB 一个独立 tool 实例。LLM 通过 description 路由到合适的 KB
    （Agentic RAG 标准做法）。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_type: ToolSourceType = "knowledge"
    category: ToolCategory = "data_source"
    args_schema: type[BaseModel] = KnowledgeRetrievalInput
    response_format: Literal["content", "content_and_artifact"] = "content_and_artifact"

    # ---- per-instance bound fields（构造时必传）----
    kb_id: UUID
    user: User  # retrieval_service 归属校验需要
    default_top_k: int = 3
    default_mode: RetrievalMode = RetrievalMode.VECTOR
    default_rerank_model_id: UUID | None = None

    async def _execute(self, query: str) -> str:
        params = RetrievalParams(
            query=query, top_k=self.default_top_k,
            mode=self.default_mode,
            rerank_model_id=self.default_rerank_model_id,
        )
        result = await _retrieval_service.retrieve(self.user, self.kb_id, params)

        if not result.hits:
            return "未在该知识库找到相关内容。"

        return _format_hits(result.hits), KnowledgeHitsArtifact(
            paragraph_ids=[h.paragraph_id for h in result.hits],
            hits=[
                KnowledgeHitRef(
                    ref=short_id(h.paragraph_id), paragraph_id=h.paragraph_id,
                    document_id=h.document_id, doc_name=h.doc_name, title=h.title,
                    page=h.page, content=_scope_figures(h.content, h.paragraph_id),
                )
                for h in result.hits
            ],
        )


def cite_marker(paragraph_id: UUID) -> str:
    """引用记号 `[[cite:<段短标识>]]`：工具给模型的出处标记、模型照抄进回答的角标、前端查表的键，三处同一格式。"""
    return f"[[cite:{short_id(paragraph_id)}]]"


CITATION_RULES = """## 引用知识库内容
知识库检索结果里，每段标题开头有一个引用记号，形如 [[cite:2e3f4a5b]]。回答用到某段内容时，在那句话末尾、句末标点之前抄上该段的记号。

- 必须标注：数字、日期、金额、期限、规定条款、流程步骤、原文引述
- 不标注：常识、过渡句、你自己的归纳和建议
- 一句话用到多段，记号依次紧挨着写：[[cite:2e3f4a5b]][[cite:c3d40e17]]，最多 3 个
- 记号原样照抄，只能用检索结果里出现过的，不得编造、不得改写成其他格式
- 不要另起一段列出参考来源，界面会自动展示

示例：
检索结果：## [[cite:2e3f4a5b]] 员工手册.pdf · 第三章 费用报销 · 第 12 页
差旅费用须在出差结束后 30 天内提交报销，逾期需部门负责人签字。
回答：差旅费需要在出差结束后 30 天内提交报销[[cite:2e3f4a5b]]，超期要部门负责人签字[[cite:2e3f4a5b]]。"""

CITATION_RELAY_NOTE = (
    "成员汇报里如果带有引用记号 [[cite:…]]，转述时把记号原样保留在对应句子末尾，"
    "不要删除、改写，也不要挪到别的句子后面。"
)


def citation_rules_for(tools: Sequence[BaseTool]) -> str | None:
    """手上真有知识库工具才返回引用规则：没有检索结果可引的 agent，多这段只是噪音。"""
    return CITATION_RULES if any(isinstance(t, KnowledgeRetrievalTool) for t in tools) else None


def _format_hits(hits: list[RetrievalHit]) -> str:
    """命中段拼成 markdown，给 LLM 看。

    格式：`## [[cite:<段短标识>]] 出处 · 相关度 0.xx` + 段全文，段间用 `---` 分隔。
    只返父级段全文，不返 chunk_text（噪音）。

    **出处含标题链与页码**：段的 `content` 里只有它直接的那级标题，看不到
    祖先——「不超过 30 天」脱离「第三章 > 报销流程」就是个孤儿句子。
    `title` / `page` 本就在 RetrievalHit 里（检索层一直在填、命中测试界面
    一直在显示），此前只是没拼进给模型的那份文本。
    """
    blocks = []
    for h in hits:
        # 无标题区域（纯 txt / md 前言）title 为空串；page 仅 PDF 有
        parts = [h.doc_name]
        if h.title:
            parts.append(h.title)
        if h.page is not None:
            parts.append(f"第 {h.page} 页")
        parts.append(f"相关度 {h.score:.2f}")
        blocks.append(f"## {cite_marker(h.paragraph_id)} {' · '.join(parts)}\n\n{_scope_figures(h.content, h.paragraph_id)}")
    return "\n\n---\n\n".join(blocks)


def _scope_figures(content: str, paragraph_id: UUID) -> str:
    """段内编号 [[figure:N]] → 跨段唯一的 [[figure:<段短标识>-N]]。

    N 只在段内唯一，一次回答里多个命中段都可能有 figure:1；
    前缀取段 id 的短标识，模型原样抄进回答，前端据此对回签名结果。
    """
    return _FIGURE_MARKER_RE.sub(
        lambda m: f"[[figure:{figure_ref(paragraph_id, int(m.group(1)))}]]", content,
    )
