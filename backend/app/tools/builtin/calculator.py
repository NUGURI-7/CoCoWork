"""内置工具：calculator —— AST 白名单安全求值。

为什么不用 eval：eval 执行任意 Python，一句 `__import__('os').system(...)` 就能
打穿服务器。本工具把表达式解析成 AST，逐节点白名单校验，只放行数字 / 四则 / 幂 /
括号 / 一组常用 math 函数与常量，其余一律拒绝 —— 根本不执行非白名单代码。

防 CPU / 内存炸弹：幂指数上限 + factorial 入参上限 + 表达式长度上限，
挡住 `2**9e9`、`factorial(1e5)` 这类病态输入（base 的 timeout 对同步 CPU 无效）。
"""

import ast
import math
import operator
from typing import Any

from pydantic import BaseModel, Field

from app.tools.base import CoCoTool
from app.tools.registry import register_tool

_MAX_EXPR_LEN = 500
_MAX_EXPONENT = 1000
_MAX_FACTORIAL = 1000

_BIN_OPS = {
    ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
    ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod, ast.Pow: operator.pow,
}
_UNARY_OPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


def _safe_factorial(n: Any) -> int:
    if not (isinstance(n, int) and 0 <= n <= _MAX_FACTORIAL):
        raise ValueError(f"factorial 仅支持 0..{_MAX_FACTORIAL} 的整数")
    return math.factorial(n)


# 白名单函数：只放行无副作用的纯数学函数
_FUNCS = {
    "sqrt": math.sqrt, "abs": abs, "round": round,
    "sin": math.sin, "cos": math.cos, "tan": math.tan,
    "log": math.log, "log2": math.log2, "log10": math.log10,
    "exp": math.exp, "floor": math.floor, "ceil": math.ceil,
    "factorial": _safe_factorial, "gcd": math.gcd, "min": min, "max": max,
}
_CONSTS = {"pi": math.pi, "e": math.e, "tau": math.tau}


def _eval(node: ast.AST) -> Any:
    """递归求值：逐节点白名单，命中非白名单类型立即 raise。"""
    if isinstance(node, ast.Constant):
        # bool 是 int 子类，单独排除（True/False 当数字语义怪异）
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError(f"不支持的常量：{node.value!r}")
        return node.value
    if isinstance(node, ast.BinOp):
        op = _BIN_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的运算符：{type(node.op).__name__}")
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Pow) and abs(right) > _MAX_EXPONENT:
            raise ValueError(f"指数过大（|exp| > {_MAX_EXPONENT}）")
        return op(left, right)
    if isinstance(node, ast.UnaryOp):
        op = _UNARY_OPS.get(type(node.op))
        if op is None:
            raise ValueError(f"不支持的一元运算符：{type(node.op).__name__}")
        return op(_eval(node.operand))
    if isinstance(node, ast.Name):
        if node.id in _CONSTS:
            return _CONSTS[node.id]
        raise ValueError(f"未知标识符：{node.id}")
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in _FUNCS:
            raise ValueError(f"不支持的函数：{getattr(node.func, 'id', '<expr>')}")
        if node.keywords:
            raise ValueError("不支持关键字参数")
        return _FUNCS[node.func.id](*[_eval(a) for a in node.args])
    raise ValueError(f"不支持的表达式：{type(node).__name__}")


def _safe_eval(expression: str) -> Any:
    if len(expression) > _MAX_EXPR_LEN:
        raise ValueError(f"表达式过长（> {_MAX_EXPR_LEN} 字符）")
    return _eval(ast.parse(expression, mode="eval").body)


class CalculatorInput(BaseModel):
    expression: str = Field(
        ...,
        description="数学表达式，如 '2 + 3 * 4'、'sqrt(16)'、'round(pi, 2)'。"
                    "支持四则 / 幂 / 括号，以及 sqrt sin cos log exp factorial 等函数和 pi e 常量。",
    )


@register_tool
class CalculatorTool(CoCoTool):
    name: str = "calculator"
    display_name: str = "计算器"
    description: str = (
        "计算数学表达式并返回精确结果。当需要做算术、求幂开方、三角 / 对数 / 阶乘等"
        "数值计算时使用，不要心算。输入一个表达式字符串。"
    )
    args_schema: type[BaseModel] = CalculatorInput

    async def _execute(self, expression: str) -> str:
        result = _safe_eval(expression)
        if isinstance(result, float) and result.is_integer():
            result = int(result)  # 4.0 → 4，去掉无意义小数尾
        return f"{expression} = {result}"