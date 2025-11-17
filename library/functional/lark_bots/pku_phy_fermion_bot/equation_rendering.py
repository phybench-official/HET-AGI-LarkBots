from ....fundamental import *


__all__ = [
    "render_equation_async",
]


async def render_equation_async(
    text: str,
    begin_of_equation: str,
    end_of_equation: str,
    model: str,
    temperature: float,
    timeout: int,
    trial_num: int,
    trial_interval: int,
)-> str:
    
    """
    独立的公式渲染模块，目的是把用户文本对齐至内部富文本格式
    以便进一步在飞书云文档上渲染出公式
    飞书云文档是不区分行内公式和行间公式的，所以允许模型微调排版，但严禁擅自改变内容
    """
    
    image_placeholder = "<image_never_used_114514_1919810>"
    
    prompt = f"""
您是一个专业的排版与公式渲染助手。
您的任务是将输入的文本转换为符合特定富文本格式的字符串，重点是正确识别并包裹数学公式。

# 1. 核心任务
读取输入的文本，识别其中**所有**的数学公式（包括行内公式、行间公式、独立的变量名、希腊字母、数字等数学符号），并使用指定的标记符号将其包裹。

# 2. 标记符号
- 公式起始标记：{begin_of_equation}
- 公式结束标记：{end_of_equation}

# 3. 规则与约束
1.  **严禁篡改内容**：您必须严格保留原文的文字、数值和表达逻辑，不得进行翻译、摘要或纠错。您唯一能做的是添加包裹标记和微调换行。
2.  **公式包裹**：
    - 所有的 LaTeX 代码、数学表达式、单个数学变量（如 x, y, m）、希腊字母（如 \\alpha）都必须被包裹。
    - 示例：原文 "公式 F=ma"，输出 "公式 {begin_of_equation}F=ma{end_of_equation}"。
3.  **排版对齐 (换行)**：
    - 目标平台（飞书云文档）完全不区分行内与行间公式。
    - 如果原文本包含独立的行间公式，您**可以**适当地将其调整为行内形式；您也可以通过添加换行符的方式手动创建“行间公式”，使其在文档中阅读更加自然流畅。
4.  **JSON 格式**：输出必须是严格的 JSON 格式。

# 4. 输出结构
请返回一个 JSON 代码块（显式给出 ```json 和 ```），结构如下：
```json
{{
  "rendered_text": "string: 处理后的文本"
}}
````

现在，你要处理的输入文本如下所示：

{text}

请给出你的 json 处理结果：
"""

    result = {}

    def check_and_accept(
        response: str,
    )-> bool:
        nonlocal result
        print(f"Render Equation: checking the following response now\n{response}")
        try:
            halfway_result = {}
            json_pattern = r'```json\s*(.*?)\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            assert matches
            
            json_string = matches[0].strip()
            json_dict = deserialize_json(json_string)
            
            assert "rendered_text" in json_dict
            assert isinstance(json_dict["rendered_text"], str)
            halfway_result["rendered_text"] = json_dict["rendered_text"]
            result = halfway_result
            return True
        except:
            return False

    _ = await get_answer_async(
        prompt = prompt,
        model = model,
        image_placeholder = image_placeholder,
        temperature = temperature,
        timeout = timeout,
        trial_num = trial_num,
        trial_interval = trial_interval,
        check_and_accept = check_and_accept,
    )

    return result["rendered_text"]