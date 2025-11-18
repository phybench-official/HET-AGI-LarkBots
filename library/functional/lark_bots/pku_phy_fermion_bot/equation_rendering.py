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
    
    # 采用 XML 结构 + 指令三明治 + Few-Shots (JSON 格式)
    prompt = f"""
<system_role>
You are a professional typesetting and equation rendering assistant.
Your goal is to format text for Feishu/Lark documents by correctly wrapping math formulas.
</system_role>

<instruction>
Please process the content in <input_text> following these rules:

1. **Identify Math**: Find ALL math formulas, variables (e.g., x, y, \\alpha), and equations.
2. **Wrap with Tags**: Enclose identified math content between specific tags:
   - Start Tag: {begin_of_equation}
   - End Tag:   {end_of_equation}
3. **Clean Delimiters**: You MUST REMOVE any existing LaTeX delimiters like `$`, `$$`, `\\(`, `\\)`, `\\[`, `\\]` from the original text. Do not keep them inside or outside the new tags.
   - Wrong: {begin_of_equation}$$F=ma$${end_of_equation}
   - Right: {begin_of_equation}F=ma{end_of_equation}
4. **Avoid Over-processing**: DO NOT wrap:
   - Normal English words or phrases.
   - Code function names (e.g., "execute_mathematica", "print", "def").
   - Units unless they are part of a formula.
5. **Language Consistency**: **Strictly preserve the original language.**
   - **Keep Chinese as Chinese.**
   - **Keep English as English.**
   - **Do NOT translate.**
6. **Preserve Content**: Do not change the wording, summary, or logic. Only adjust formatting.
7. **Format**: Output the result strictly as a JSON code block; **explicitly offer enclosing ```json and ```** for extraction convenience.
</instruction>

<examples>
    <example_1>
        <input>
        这道题的答案是 $x = 5$。我们都知道 $$E = mc^2$$ 是很有名的公式。
        </input>
        <output>
        ```json
        {{
            "rendered_text": "这道题的答案是 {begin_of_equation}x = 5{end_of_equation}。我们都知道 {begin_of_equation}E = mc^2{end_of_equation} 是很有名的公式。"
        }}
        ```
        </output>
        <note>Original language (Chinese) preserved. $ and $$ removed.</note>
    </example_1>

    <example_2>
        <input>
        Please run the function execute_mathematica to solve differential equation y' = y.
        </input>
        <output>
        ```json
        {{
            "rendered_text": "Please run the function execute_mathematica to solve differential equation {begin_of_equation}y' = y{end_of_equation}."
        }}
        ```
        </output>
        <note>"execute_mathematica" is NOT wrapped because it is code/English. "y' = y" IS wrapped.</note>
    </example_2>

    <example_3>
        <input>
        Let $\\alpha$ be the angle. The value is 10.
        </input>
        <output>
        ```json
        {{
            "rendered_text": "Let {begin_of_equation}\\alpha{end_of_equation} be the angle. The value is 10."
        }}
        ```
        </output>
    </example_3>
</examples>

<input_text>
{text}
</input_text>

<principles_recap>
1. Output format: JSON code block with key "rendered_text"; ensure explicit closure.
2. **CRITICAL**: Remove old `$` or `$$` symbols completely.
3. **CRITICAL**: Do NOT wrap code function names or plain English.
4. **CRITICAL**: **Do NOT translate.** Keep Chinese as Chinese, English as English.
5. **CRITICAL**: Wrap all actual math variables and equations with {begin_of_equation} and {end_of_equation}.
</principles_recap>

Please generate the JSON response now.
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
            
            if not matches:
                # Fallback: try to parse raw JSON if markdown tags are missing
                try:
                    deserialize_json(response.strip())
                    json_string = response.strip()
                except:
                    return False
            else:
                json_string = matches[0].strip()
            
            json_dict = deserialize_json(json_string)
            
            assert "rendered_text" in json_dict
            assert isinstance(json_dict["rendered_text"], str)
            
            # Ensure the output is not empty if input wasn't
            if text.strip():
                assert json_dict["rendered_text"].strip()
            
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