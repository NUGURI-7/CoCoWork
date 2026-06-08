"""知识库检索工具 —— per-KB bound 实例。

跟 builtin 单例工具的本质不同：
- builtin tool（calculator）= 全局单例、无状态、registry 启动期注册
- KB tool = per-KB 实例、绑定 kb_id + user、装配阶段动态实例化、不进 registry

LLM 选库靠 description（拼装时塞 KB 名 + 描述），name 只是身份标识。
"""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.models import User
from app.schemas.knowledge import RetrievalHit
from app.services.knowledge.retrieval import RetrievalParams, RetrievalService
from app.tools.base import CoCoTool

# RetrievalService 无状态（dispatch 表是类属性），模块级共享一个实例。
_retrieval_service = RetrievalService()


class KnowledgeRetrievalInput(BaseModel):
    query: str = Field(..., description="要检索的查询文本")


class KnowledgeRetrievalTool(CoCoTool):
    """单库语义检索 —— per-KB bound 实例化。

    name / description / display_name 由调用方按 KB 信息拼装传入；
    每个 KB 一个独立 tool 实例。LLM 通过 description 路由到合适的 KB
    （Agentic RAG 标准做法）。
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    source_type: Literal["builtin", "mcp", "knowledge"] = "knowledge"
    args_schema: type[BaseModel] = KnowledgeRetrievalInput

    # ---- per-instance bound fields（构造时必传）----
    kb_id: UUID
    user: User  # retrieval_service 归属校验需要
    default_top_k: int = 3

    async def _execute(self, query: str) -> str:
        params = RetrievalParams(query=query, top_k=self.default_top_k)
        result = await _retrieval_service.retrieve(self.user, self.kb_id, params)

        if not result.hits:
            return "未在该知识库找到相关内容。"

        return _format_hits(result.hits)


def _format_hits(hits: list[RetrievalHit]) -> str:
    """命中段拼成 markdown，给 LLM 看。

    格式：`## [N] doc_name（相关度 0.xx）` + 段全文，段间用 `---` 分隔。
    只返父级段全文，不返 chunk_text / paragraph_id（噪音）。
    """
    blocks = [
        f"## [{i}] {h.doc_name}(相关度 {h.score:.2f})\n\n{h.content}"
        for i, h in enumerate(hits, 1)
    ]
    return "\n\n---\n\n".join(blocks)

