"""Agent 实例层 config jsonb 的强类型单一真源。

Tortoise `JSONField` 存出去是 dict[str, Any]，全靠业务层校验形状。
本 schema 是该 dict 的强契约：
- runner / service 取 agent.config 后用 AgentConfig.model_validate(...) 校验取值
- 装配器 / route 改 config 时用 model_dump(mode="json") 回写
- 前端 ConfigPanel 字段命名按本 schema 对齐

字段演化策略：
- 加字段不破坏 —— jsonb 加键、Pydantic 加可选字段
- 改值形态（primitive → object）破坏 —— 凡可能演化处都用 object（如 ModelSlot 而非裸 UUID）
"""

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ============ 模型槽位 ============


class ModelParams(BaseModel):
    """单个模型槽位的调用参数。

        显式列 chat 常用三个；其他参数（presence_penalty / response_format /
        reasoning_effort / stop / seed 等）走 extra="allow" 透传给 LangChain，
        不在此处穷举。
    """

    model_config = ConfigDict(extra="allow")

    temperature: float | None = None
    top_p: float | None = None
    max_tokens: int | None = None


class ModelSlot(BaseModel):
    """能力槽位的模型引用 + 调用参数。

    值用 object 而非裸 UUID —— 将来加 fallback / 路由策略 / stream toggle
    都不破坏 schema。
    """

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(..., description="AIModel 记录 ID")
    params: ModelParams = Field(default_factory=ModelParams)


class AgentModels(BaseModel):
    """按能力的模型槽位 map。

    chat 选填 —— Agent 刚创建时 config 还是空、模型在 ConfigPanel 选；
    跑前由 runner 校验 chat 必须配。

    单模型多模态时（GPT-4o / Claude 视觉 / Gemini），chat 槽位的
    AIModel.meta.modalities 标原生能力，runner 优先用 chat 自带能力、
    不强求配 vision / stt / tts 槽位。
    """

    model_config = ConfigDict(extra="forbid")

    chat: ModelSlot | None = None
    stt: ModelSlot | None = None
    tts: ModelSlot | None = None
    vision: ModelSlot | None = None
    image_gen: ModelSlot | None = None
    video: ModelSlot | None = None


# ============ 行为 / UI ============

class AgentBehavior(BaseModel):
    """产品层行为配置（voice agent VAD / 打断阈值 / turn detection / 静音超时 等）。

    P0 空 —— voice / vision 那片实装时加字段。
    """

    model_config = ConfigDict(extra="forbid")


class AgentUI(BaseModel):
    """UI 元数据 —— 跟运行解耦，前端展示用。"""

    model_config = ConfigDict(extra="forbid")

    avatar_url: str | None = None


# ============ 顶层 config ============

class AgentConfig(BaseModel):
    """Agent 实例层 config jsonb 的强类型契约。"""
    model_config = ConfigDict(extra="forbid")

    models: AgentModels = Field(default_factory=AgentModels)

    system_prompt: str | None = None
    capabilities: list[str] = Field(default_factory=list)

    knowledge: list[UUID] = Field(default_factory=list)
    tools: list[UUID] = Field(default_factory=list)
    skills: list[UUID] = Field(default_factory=list)

    behavior: AgentBehavior = Field(default_factory=AgentBehavior)
    ui: AgentUI = Field(default_factory=AgentUI)
