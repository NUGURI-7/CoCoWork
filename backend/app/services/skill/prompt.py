"""skill 清单的 system prompt 片段。

不用 deepagents 的 SkillsMiddleware（它在 agent 启动时就 als() 扫目录，
与容器懒启动冲突，见设计稿决策 22），故自己拼这一段。

XML 形状照搬 skills_ref.to_prompt() —— 那是 Anthropic 官方定的格式，
模型很可能在训练中见过；自拟一个格式是在赌，且赌输了没法归因
（skill 不被调用，分不清是描述写差了还是格式没对上）。
不直接调 to_prompt() 是因为它吃本地目录、还会把宿主机绝对路径写进
<location>，而我们要给的是容器里的虚拟路径。
"""
import html
from typing import Protocol
from collections.abc import Sequence


from app.services.sandbox.layout import SandboxPaths

_TEMPLATE = """## Skills

你有一批 skill 可用。每个 skill 是一份写好的操作说明书（SKILL.md）外加一套
可直接运行的脚本，专治那些「有固定套路、自己现编容易出错」的任务。

{skills}

**怎么用**

1. 先看上面每个 skill 的 description，判断当前任务是否落在它的范围内。
2. 匹配上了，**先把它的说明书读完**：`read_file(file_path="<location 里给的路径>", limit=1000)`。
   必须显式传 `limit` —— 默认只读 100 行，SKILL.md 普遍读不全，读半截照着做会出错。
3. 照说明书的步骤做。里面的脚本用 `execute` 跑，**路径一律用 location 同目录下的绝对路径**。
4. 说明书说了算。它写「数据先落成文件再跑脚本」就别图省事塞命令行参数，
   它写「不要用 0 代替缺失值」就别用 —— 这些都是踩过坑才写下来的。

**文件放哪**

- `{outputs}/` —— **这一轮交给用户的成果**。脚本的输出参数（`--out` 之类）直接指到这里。
  只有放进这个目录的文件，用户才看得到、才能下载 —— 放在别处等于白做。
{workspace_line}
- `{tmp}/` —— 这一轮的草稿：中间数据、临时文件。用完即弃，别把成果放这儿。

没有哪个 skill 对得上任务时，就正常干活，不要为了用而用。"""

# 工作区那一行的两个版本 —— 差别只在提不提取回工具。
# 自带行首的「- 」，因为它在模板里是整行替换的。
_WORKSPACE_WITH_FETCH = """- `{workspace}/` —— 工作区，**每一轮开始时都是空的**。
  以前产出的文件不在这儿 —— 历史消息里 `<artifacts>` 标注过的，
  要接着用（在上次那张图上改、读上次导出的数据）就先 `fetch_artifact` 取回来。"""

# Playground 那条路没有取回工具（决策 26），就别提它 ——
# 说一个它调不到的工具名，只会换来一次失败的工具调用
_WORKSPACE_PLAIN = """- `{workspace}/` —— 工作区，**每一轮开始时都是空的**，
  这一轮要用的东西都得这一轮生成。"""


class SkillListing(Protocol):
    """prompt 只需要这两个字段。内置的 BuiltinSkill 与 DB 里的 Skill 行都满足。"""

    name: str
    description: str


def build_skills_prompt(
        skills: Sequence[SkillListing], paths: SandboxPaths, *, can_fetch: bool
) -> str:
    """拼 skill 清单的 system prompt 片段。挂了 skill 才调，没挂返回空串。

    Args:
        can_fetch: 这个参与者有没有 fetch_artifact 工具（决策 26：Playground 没有）。
            prompt 里不提它调不到的工具。
    """
    if not skills:
        return ""
    return _TEMPLATE.format(
        skills=_available_skills_block(skills, paths),
        outputs=paths.outputs,
        workspace_line=(
            _WORKSPACE_WITH_FETCH if can_fetch else _WORKSPACE_PLAIN
        ).format(workspace=paths.workspace),
        tmp=paths.tmp,
    )


def _available_skills_block(skills: Sequence[SkillListing], paths: SandboxPaths) -> str:
    """<available_skills> XML 块，逐行形状与 skills_ref.to_prompt() 一致。"""
    lines = ["<available_skills>"]
    for props in skills:
        lines += [
            "<skill>",
            "<name>",
            html.escape(props.name),
            "</name>",
            "<description>",
            html.escape(props.description),
            "</description>",
            "<location>",
            # name 等于目录名是规范强制的，上传时 validate() 已校验过，
            # 故可由 name 直接推出路径，不必另外传目录名进来。
            # 不做转义：name 的字符集被规范限死（小写字母/数字/连字符），无可转义之物。
            f"{paths.skills}/{props.name}/SKILL.md",
            "</location>",
            "</skill>",
        ]
    lines.append("</available_skills>")
    return "\n".join(lines)
