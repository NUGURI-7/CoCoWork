"""知识库检索工具 —— per-KB bound 实例。

跟 builtin 单例工具的本质不同：
- builtin tool（calculator）= 全局单例、无状态、registry 启动期注册
- KB tool = per-KB 实例、绑定 kb_id + user、装配阶段动态实例化、不进 registry

LLM 选库靠 description（拼装时塞 KB 名 + 描述），name 只是身份标识。
"""

import re
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

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


class KnowledgeHitsArtifact(ClientArtifact):
    """本次命中的段 id —— 前端拿去换段内插图的签名链接。"""

    kind: Literal["knowledge_hits"] = "knowledge_hits"
    paragraph_ids: list[UUID]


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
        )


def _format_hits(hits: list[RetrievalHit]) -> str:
    """命中段拼成 markdown，给 LLM 看。

    格式：`## [N] 出处 · 相关度 0.xx` + 段全文，段间用 `---` 分隔。
    只返父级段全文，不返 chunk_text / paragraph_id（噪音）。

    **出处含标题链与页码**：段的 `content` 里只有它直接的那级标题，看不到
    祖先——「不超过 30 天」脱离「第三章 > 报销流程」就是个孤儿句子。
    `title` / `page` 本就在 RetrievalHit 里（检索层一直在填、命中测试界面
    一直在显示），此前只是没拼进给模型的那份文本。
    """
    blocks = []
    for i, h in enumerate(hits, 1):
        # 无标题区域（纯 txt / md 前言）title 为空串；page 仅 PDF 有
        parts = [h.doc_name]
        if h.title:
            parts.append(h.title)
        if h.page is not None:
            parts.append(f"第 {h.page} 页")
        parts.append(f"相关度 {h.score:.2f}")
        blocks.append(f"## [{i}] {' · '.join(parts)}\n\n{_scope_figures(h.content, h.paragraph_id)}")
    return "\n\n---\n\n".join(blocks)


def _scope_figures(content: str, paragraph_id: UUID) -> str:
    """段内编号 [[figure:N]] → 跨段唯一的 [[figure:<段短标识>-N]]。

    N 只在段内唯一，一次回答里多个命中段都可能有 figure:1；
    前缀取段 id 的短标识，模型原样抄进回答，前端据此对回签名结果。
    """
    return _FIGURE_MARKER_RE.sub(
        lambda m: f"[[figure:{figure_ref(paragraph_id, int(m.group(1)))}]]", content,
    )
