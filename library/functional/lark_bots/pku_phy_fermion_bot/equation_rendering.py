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
    
    image_placeholder = "<image_never_used>"
    
    # 采用 XML 结构 + CDATA 以彻底解决 JSON 转义灾难和长文本指令不遵循问题
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
7. **Output Format**: 
   - Output the result strictly enclosed in XML tags `<rendered_text>`.
   - It is HIGHLY RECOMMENDED to use CDATA sections `<![CDATA[ ... ]]>` to wrap the content. This prevents parsing errors if the text contains characters like `<` or `&`.
   - **Do NOT escape backslashes.** Write `\\alpha` as `\\alpha`, not `\\\\alpha`.
</instruction>

<examples>
    <example_1>
        <input>
        这道题的答案是 $x = 5$。我们都知道 $$E = mc^2$$ 是很有名的公式。
        </input>
        <output>
        <rendered_text><![CDATA[这道题的答案是 {begin_of_equation}x = 5{end_of_equation}。我们都知道 {begin_of_equation}E = mc^2{end_of_equation} 是很有名的公式。]]></rendered_text>
        </output>
        <note>Original language preserved. $ and $$ removed. CDATA used for safety.</note>
    </example_1>

    <example_2>
        <input>
        Please run the function execute_mathematica to solve differential equation y' = y.
        </input>
        <output>
        <rendered_text><![CDATA[Please run the function execute_mathematica to solve differential equation {begin_of_equation}y' = y{end_of_equation}.]]></rendered_text>
        </output>
        <note>"execute_mathematica" is NOT wrapped. "y' = y" IS wrapped.</note>
    </example_2>

    <example_3>
        <input>
        Let $\\alpha$ be the angle. The value is 10.
        </input>
        <output>
        <rendered_text><![CDATA[Let {begin_of_equation}\\alpha{end_of_equation} be the angle. The value is 10.]]></rendered_text>
        </output>
        <note>Backslash preserved as single backslash inside CDATA.</note>
    </example_3>
</examples>

<input_text>
{text}
</input_text>

<principles_recap>
1. Output format: `<rendered_text><![CDATA[ YOUR_CONTENT_HERE ]]></rendered_text>`.
2. **CRITICAL**: Remove old `$` or `$$` symbols completely.
3. **CRITICAL**: Do NOT wrap code function names or plain English.
4. **CRITICAL**: **Do NOT translate.**
5. **CRITICAL**: Wrap all actual math variables and equations with {begin_of_equation} and {end_of_equation}.
</principles_recap>

Please generate the XML response now.
"""

    result = {}

    def check_and_accept(
        response: str,
    )-> bool:
        nonlocal result
        print(f"Render Equation: checking the following response now\n{response}")
        try:
            # 使用 Regex 健壮地提取 XML 标签中的内容
            # 兼容模型输出 CDATA 或直接输出文本的情况
            # 模式解释:
            # <rendered_text>         : 起始标签
            # \s* : 容忍标签后的空白
            # (?:<!\[CDATA\[)?        : 可选的 CDATA 开始标记 (非捕获组)
            # (.*?)                   : 捕获核心内容 (非贪婪匹配，配合 DOTALL 匹配换行符)
            # (?:\]\]>)?              : 可选的 CDATA 结束标记 (非捕获组)
            # \s* : 容忍空白
            # </rendered_text>        : 结束标签
            
            xml_pattern = r'<rendered_text>\s*(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?\s*</rendered_text>'
            matches = re.findall(xml_pattern, response, re.DOTALL | re.IGNORECASE)
            
            if not matches:
                return False
            
            extracted_text = matches[0]
            
            # 如果原文不为空，但提取出的内容全是空白，视为无效响应
            if text.strip() and not extracted_text.strip():
                return False
            
            # 提取出的内容即为最终文本，无需像 JSON 那样进行反序列化，避免了转义符地狱
            result["rendered_text"] = extracted_text
            return True
        except Exception as e:
            print(f"Render Equation: check_and_accept failed with error: {e}")
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