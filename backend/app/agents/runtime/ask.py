"""把 LangGraph 的中断包成一个业务接口。

调用方只看见「问用户 → 拿到答案」，看不到 interrupt / Command / resume
这些框架词。往后 LangGraph 改 API，只需要动这一个文件。
"""

from langgraph.types import interrupt

from app.schemas.agent.interrupt_schema import AskAnswer, AskPayload


def ask_user(payload: AskPayload) -> AskAnswer:
    """停下来问用户一句，拿到答案再继续。

    调用点既可以是工具函数内部，也可以是图节点内部 —— 两处都实测能正确
    穿透到最外层的事件流并恢复。

    **绝不能用 try/except 包住这个调用**：中断是靠抛一个特殊异常实现的，
    吞掉它整套机制就废了（官方明确警告过这点）。

    执行语义要留神：第一次走到这里时图当场冻结存盘、本次调用不会返回；
    用户提交答案后图从存档恢复、**整个节点从头重跑**，这一行才拿到值。
    所以这一行之前的代码会执行两遍 —— 别在它前面放不可重复的操作
    （扣款、发消息、写文件）。

    LangGraph 全程不认识这两个类型，它只是传送带：进去的 dict 原样存进
    checkpoint 再发给前端，出来的 dict 原样来自「继续」接口。两头的格式
    都是本项目自己约的，所以两头都各校验一次。

    同步函数：interrupt 本身是同步的，在 async 工具里直接调用即可。
    """
    raw = interrupt(payload.model_dump(mode="json"))
    return AskAnswer.model_validate(raw)
