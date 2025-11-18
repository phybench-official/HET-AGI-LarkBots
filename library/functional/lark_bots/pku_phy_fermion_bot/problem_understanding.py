from ....fundamental import *


__all__ = [
    "understand_problem_async",
]


async def understand_problem_async(
    message: str,
    problem_images: List[bytes],
    model: str,
    temperature: float,
    timeout: int,
    trial_num: int,
    trial_interval: int,
)-> Dict[str, Any]:
    
    """
    单轮次环节
    接收一条用户消息和图片，解析出 problem_text 和 answer，
    并确定题目小标题 problem_title （简短的文字内容，避免公式）
    problem_images 仅作上下文给出，内容、数量和顺序一经用户发出即定死
    answer 允许为“暂无”，严禁自行解题
    在后续的题目确认环节会再与用户交互，修缮 problem_text 和 answer
    返回一个 Dict，保证包含：
        - problem_title: str
        - problem_text: str
        - answer: str
    此环节不负责对齐至内部富文本格式以支持公式渲染的工作。
    """
    
    image_placeholder = "<image_never_used>"
    
    # 采用 XML 结构 + 指令三明治 + Few-Shots (返回 JSON 格式)
    prompt = f"""
<system_role>
You are a professional Physics Problem Organizer.
Your task is to FAITHFULLY extract and structure raw user input into a standardized format.
You are NOT a solver; you are a librarian.
</system_role>

<instruction>
Please analyze the content in <input_text> and extract information into a JSON object following these rules:

1. **problem_title** (String):
   - Generate a VERY SHORT, pure text title summarizing the physics concept (e.g., "Momentum Conservation").
   - **Constraint**: Must be Plain Text. NO LaTeX. NO formulas. NO complex symbols.

2. **problem_text** (String):
   - Extract the full problem description.
   - **Clean Up Prefix**: Remove meta-labels like "【题目】", "题目：", "Question:", or "题目是".
   - **Separation**: If the input contains the answer, ensure `problem_text` ONLY contains the question part.
   - **Image Flexibility**:
     - The input **MAY or MAY NOT** contain images. Both cases are perfectly valid.
     - **If Images Exist**: Do NOT transcribe/OCR them. Use natural phrases like "As shown in the figure" to refer to them.
     - **If No Images**: Just process the text. Do NOT hallucinate phrases like "As shown in the figure" if there is no figure.

3. **answer** (String):
   - Extract the reference answer provided by the user.
   - **CRITICAL - NO INFERENCE**: If the input is just a question, you are **STRICTLY FORBIDDEN** to solve it.
   - If no answer is explicitly provided, this field MUST be "暂无".
   - If the user provided an answer key, extract it here.

4. **Format**: Output MUST be explicitly wrapped in **```json and ```** code blocks.
</instruction>

<examples>
    <example_1>
        <input>
        【题目】如图所示，求小车的加速度。
        (User provided 1 image)
        </input>
        <output>
        ```json
        {{
            "problem_title": "牛顿第二定律",
            "problem_text": "如图所示，求小车的加速度。",
            "answer": "暂无"
        }}
        ```
        <note>Image exists -> Refer to it naturally. Prefix removed. No answer -> "暂无".</note>
    </example_1>

    <example_2>
        <input>
        Calculate the integral of x^2 from 0 to 1.
        (No images provided)
        </input>
        <output>
        ```json
        {{
            "problem_title": "Definite Integral",
            "problem_text": "Calculate the integral of x^2 from 0 to 1.",
            "answer": "暂无"
        }}
        ```
        <note>No images -> Perfectly OK, just process text. STRICTLY FORBIDDEN TO SOLVE IT. Answer is "暂无".</note>
    </example_2>

    <example_3>
        <input>
        Question: What is the force?
        Answer: F = ma.
        (No images provided)
        </input>
        <output>
        ```json
        {{
            "problem_title": "Force Definition",
            "problem_text": "What is the force?",
            "answer": "F = ma."
        }}
        ```
        <note>Clean separation of Question and Answer.</note>
    </example_3>
</examples>

<input_text>
{message + len(problem_images) * image_placeholder}
</input_text>

<principles_recap>
1. **Format**: Explicitly use ```json ... ``` block.
2. **Clean Text**: Remove prefixes. Separate Q & A.
3. **Image Handling**: Refer to images IF present; otherwise just handle text. No OCR.
4. **NO INFERENCE**: If answer is missing, write "暂无". **STRICTLY FORBIDDEN TO SOLVE.**
</principles_recap>

Please generate the JSON response now.
"""

    result = {}

    def check_and_accept(
        response: str,
    )-> bool:
        nonlocal result
        print(f"Understand Problem: checking the following response now\n{response}")
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
            
            required_keys = ["problem_title", "problem_text", "answer"]
            for key in required_keys:
                assert key in json_dict
                assert isinstance(json_dict[key], str)
                # 简单的非空校验
                assert len(json_dict[key]) > 0
            
            # 简单的逻辑校验：title 不应包含 LaTeX 符号
            # if "$" in json_dict["problem_title"] or "\\" in json_dict["problem_title"]:
            #     print("Warning: LaTeX detected in problem_title, which should be pure text.")
            #     return False 

            halfway_result["problem_title"] = json_dict["problem_title"]
            halfway_result["problem_text"] = json_dict["problem_text"]
            halfway_result["answer"] = json_dict["answer"]
            
            result = halfway_result
            return True
        except:
            return False

    _ = await get_answer_async(
        prompt = prompt,
        model = model,
        images = problem_images,
        image_placeholder = image_placeholder,
        temperature = temperature,
        timeout = timeout,
        trial_num = trial_num,
        trial_interval = trial_interval,
        check_and_accept = check_and_accept,
    )

    return result