"""工具层基类：CoCoTool —— 在 LangChain BaseTool 上统一加项目级元信息 + 横切行为。

为什么自己包一层而非直接用 BaseTool / @tool 装饰器：
- BaseTool 只有 name/description/args_schema，缺业务元信息（中文名 / 来源 / 危险标记）。
- output 截断 / 超时 / 异常兜底 这类「每个工具都该有」的横切逻辑，必须收口到基类，
  不能散在每个工具各写一遍 —— 否则迟早漏（web_search 忘了 cap → context 直接爆）。

模板方法模式：
- 子类只实现 `_execute()` —— 纯业务逻辑，入参由 args_schema 解析后按名注入，返回字符串。
- 基类的 `_arun()` 统一包：超时 → 业务 → 异常兜底 → 输出截断，子类绕不过。
- 同步入口 `_run()` 封死 —— 工具一律异步，上层永远 await，无需区分 CPU / IO。

name vs display_name：
- `name` 给 LLM，受 OpenAI/Anthropic 正则约束（`^[a-zA-Z0-9_-]{1,64/128}$`，不能中文）。
- `display_name` 给人看（前端工具选择器 / 审计日志），可中文。
"""

import asyncio
import logging
from abc import abstractmethod
from typing import Any, Literal

from langchain_core.tools import BaseTool
from langgraph.errors import GraphBubbleUp

logger = logging.getLogger(__name__)

# 工具来源。写成别名而不是每处各抄一遍 Literal —— 加一种来源只改这一行
ToolSourceType = Literal["builtin", "mcp", "knowledge", "memory"]

# 工具能力分类。两个消费者：前端工具卡片上的标签（给人看），以及模板的配置校验
# （给程序看）—— Retrieve-then-Read 要问的是「用户有没有挂能查到外部信息的工具」。
#
# **按能力分，不按主题分**：不是 search / weather / finance 那种给人浏览工具市场
# 用的标签（Dify 的 tool tags 是那一路）。网页搜索、数据库查询、知识库检索主题上
# 八竿子打不着、能力上是同一类；按主题分的话，校验处就得写一份
# category in ("search", "database", ...) 的白名单，每加一种数据源改它一次。
#
# 只开有真实用途的档：calculator 单独立一档「计算」在卡片上更好看，但一共就两个
# 内置工具、分成两类每类一个，那不叫分类。等 utility 这格真塞不下了再按拥挤程度拆。
ToolCategory = Literal["data_source", "utility"]

# 单次工具输出能进上下文的字符上限（L1 上下文防爆）。
# **跨轮回放沿用同一个数** —— 见 view_context_assembler._cap_result：
# 一次执行能进多少，历史里就是多少，不另立一套标准。
MAX_TOOL_OUTPUT_CHARS = 4000


class CoCoTool(BaseTool):
    """项目所有工具的统一基类。子类只实现 `_execute`，横切逻辑由本类兜底。"""

    # ---- 项目级元信息（LangChain BaseTool 没有的）----
    display_name: str  # 中文展示名；name 给 LLM（英文受正则约束）、本字段给人看
    source_type: ToolSourceType = "builtin"
    # 能力分类。默认给最弱的一档 —— 没主动声明的工具不会被误认成数据源。
    # 漏标的后果是「模板说你没配数据源」（用户看得见、能改），而不是「模板以为你
    # 配了、跑起来查不到东西」（用户看不见、只能怀疑系统坏了）
    category: ToolCategory = "utility"
    dangerous: bool = False  # 有副作用（删文件 / 发请求 / 花钱）的工具标 True，未来接人工确认

    # ---- 横切行为参数 ----
    max_output_chars: int = MAX_TOOL_OUTPUT_CHARS  # 超长截断；返回极短的工具可调小
    timeout_seconds: float = 30.0  # 单次执行超时

    @abstractmethod
    async def _execute(self, **kwargs: Any) -> str:
        """子类实现：纯业务逻辑。入参由 args_schema 解析后按名注入，返回给 LLM 的字符串。"""
        ...

    async def _arun(self, *args: Any, run_manager: Any = None, **kwargs: Any) -> str:
        """统一执行管线：超时 → 业务 → 异常兜底 → 输出截断。子类不重写本方法。

        run_manager 是 LangChain 注入的回调管理器，此处接住但不透传给 `_execute`。
        """
        try:
            result = await asyncio.wait_for(
                self._execute(**kwargs), timeout=self.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning("tool %r timeout after %ss", self.name, self.timeout_seconds)
            return f"工具「{self.display_name}」执行超时（超过 {self.timeout_seconds:g} 秒）"
        except GraphBubbleUp:
            # LangGraph 的控制流信号（人工确认的中断、工具返回 Command 注入 state、
            # 图排空），全靠抛异常向上冒泡实现 —— **它们不是「工具出错」**。
            # 被下面那个 except Exception 截住的话，用户永远等不到那张表单，
            # 只会收到一句「执行出错」，整套中断机制静默失效。
            # 顺序不能与下面对调：Python 按书写顺序匹配 except 分支
            raise
        except Exception as exc:
            # 异常不外抛、不让 traceback 进 LLM context —— 翻成一句话，由 LLM 自行决定换法
            logger.exception("tool %r failed", self.name)
            return f"工具「{self.display_name}」执行出错：{exc}"

        return self._cap_output(result)

    def _cap_output(self, text: str) -> str:
        """超长输出截断 —— 防单个工具返回把 context 撑爆（上下文管理 L1）。"""
        if len(text) <= self.max_output_chars:
            return text
        kept = text[: self.max_output_chars]
        return f"{kept}\n\n[输出过长已截断，原始共 {len(text)} 字符，仅显示前 {self.max_output_chars}]"

    def _run(self, *args: Any, **kwargs: Any) -> str:
        """同步入口封死 —— 工具一律走异步。LangGraph 默认调 `_arun`，本方法只防误用。"""
        raise NotImplementedError(
            f"{type(self).__name__} 只支持异步执行，请通过 ainvoke / _arun 调用"
        )
