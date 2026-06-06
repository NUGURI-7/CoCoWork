"""
    @project: DaisyWind
    @Author: niu
    @file: chat_agent.py
    @date: 2026/4/10 16:05
    @desc:
"""

from pydantic_ai import Agent, BinaryImage

from backend.app.agents.deps import AgentDeps
from backend.app.agents.providers import build_model
from backend.app.tools.brave_web_search_tool import brave_web_search
from backend.app.tools.notes_tool import search_notes
from backend.app.tools.tavily_web_search_tool import tavily_web_search

SYSTEM_PROMPT = """\
You are a helpful AI assistant.

Respond in the language the user is using.
Use Markdown formatting where appropriate, and always specify the language in code blocks.

You have access to tools that let you search the user's personal data. Call a
tool only when it is genuinely useful — for simple small talk, general
knowledge, or content you already know, answer directly without using tools.

When the user asks about their own notes, past entries, or content they have
written, use the `search_notes` tool to look them up by keyword.

When the user asks about time-sensitive information (current news, weather,
prices, recent releases) or facts that may have changed since your training
cutoff, use the `tavily_web_search` or `brave_web_search` tool to search the public web. Do not use
it for questions you can confidently answer from general knowledge.
"""

IMAGE_SYSTEM_PROMPT = """\
You are an image generation assistant.

For every user request, your primary output MUST be a generated image.
- Always produce an image, even if the request is brief or ambiguous — make a reasonable interpretation and generate.
- Do not reply with text-only refusals or clarifying questions; if the request is unclear, generate your best guess.
- Keep any accompanying text minimal (one short caption at most). The image is the answer.
- Match the language of any caption to the user's language.
"""

def build_chat_agent(provider: str, model_name: str) -> Agent[AgentDeps, str | BinaryImage]:
    """构造一个基础 Chat Agent（无 Tool）。

    Args:
        provider: 厂商标识
        model_name: 模型名

    Returns:
        配置好的 PydanticAI Agent，output 类型为 str（纯文本）
    """
    model = build_model(provider, model_name)

    is_image_model = provider == 'gemini' and 'image' in model_name

    agent_kwargs = {
        "system_prompt": IMAGE_SYSTEM_PROMPT if is_image_model else SYSTEM_PROMPT,
        "deps_type": AgentDeps,
    }
    if is_image_model:
        agent_kwargs["output_type"] = [str, BinaryImage]

    agent = Agent(model, **agent_kwargs)

    if not is_image_model:
        agent.tool(search_notes)
        agent.tool(tavily_web_search)
        agent.tool(brave_web_search)

    return agent