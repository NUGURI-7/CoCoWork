"""
    @project: DaisyWind
    @Author: niu
    @file: pricing.py.py
    @date: 2026/4/10 15:24
    @desc: Token 价格表与费用计算。
"""



# 单价：
#   text_input / text_output：美元 / 百万 token
#   image_output_per_unit：美元 / 张（图像生成模型）
TOKEN_PRICE: dict[str, dict[str, float]] = {
    "deepseek-chat":                  {"text_input": 0.27,  "text_output": 1.10},
    "deepseek-reasoner":              {"text_input": 0.55,  "text_output": 2.19},
    "gemini-3.1-pro-preview":         {"text_input": 2.00,  "text_output": 12.00},
    "gemini-3.1-flash-lite-preview":  {"text_input": 0.25,  "text_output": 1.50},
    "gemini-3-flash-preview":         {"text_input": 0.50,  "text_output": 3.00},
    # 图像生成模型：无 text_output，改为按张计费
    "gemini-3.1-flash-image-preview": {"text_input": 0.25,  "image_output_per_unit": 0.067},
    "gemini-3-pro-image-preview":     {"text_input": 2.00,  "image_output_per_unit": 0.134},
}



def calc_cost(
    model_name: str,
    input_tokens: int,
    output_tokens: int,
    image_count: int = 0,
) -> float | None:
    """计算一次调用的费用（美元）。模型不在价格表中时返回 None。

    三项成本叠加：
    - 输入 token × text_input 单价
    - 输出 token × text_output 单价（图像模型无此项，text_output=0）
    - 输出图片张数 × image_output_per_unit（文本模型无此项，image_count 默认 0）
    """
    price = TOKEN_PRICE.get(model_name)
    if not price:
        return None

    cost = input_tokens  * price.get("text_input",  0) / 1_000_000
    cost += output_tokens * price.get("text_output", 0) / 1_000_000
    cost += image_count  * price.get("image_output_per_unit", 0)
    return cost
