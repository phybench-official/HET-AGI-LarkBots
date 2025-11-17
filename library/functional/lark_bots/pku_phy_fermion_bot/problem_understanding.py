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
    
    image_placeholder = "<image_never_used_114514_1919810>"
    
    prompt = f"""
您是一个专业的物理题目整理助手。
您的任务是分析用户提供的文本和图像信息，提取关键内容，并将其结构化。

# 1. 核心任务
阅读用户的输入（包含文本和图片），提取出题目标题、完整的题干描述以及参考答案。

# 2. 提取规则
1.  **题目标题 (problem_title)**：
    - 根据题干内容生成一个极简短的标题，概括题目涉及的核心物理知识点（例如：“动量守恒定律”、“带电粒子在磁场中运动”）。
    - **约束**：标题必须是纯文本，**严禁**包含任何数学公式、LaTeX 代码或复杂符号。
2.  **题干 (problem_text)**：
    - 提取并整合完整的题目描述。
    - **关于图片内容**：如果题目信息主要包含在图片中，您**不需要**将其强制转录为文字。完全可以使用“如图所示，...”或“请回答图中的问题”等自然语言描述来指代图片内容，只要上下文通顺即可。
    - 保持原文的表达方式和语序。
3.  **参考答案 (answer)**：
    - 提取用户提供的参考答案或解析。
    - **关键约束**：如果用户**未提供**任何形式的参考答案或解析，您必须将此字段设为 **"暂无"**。
    - **严禁解题**：您只需提取现有的答案。如果用户没给答案，绝对不要自己去尝试计算或解答。

# 3. JSON 格式
输出必须是严格的 JSON 格式。

# 4. 输出结构
请返回一个 JSON 代码块（显式给出 ```json 和 ```），结构如下：
```json
{{
  "problem_title": "string: 简短的纯文本标题",
  "problem_text": "string: 完整的题干内容",
  "answer": "string: 提取的答案 或 '暂无'"
}}
````

现在，请处理以下用户输入（图片已作为上下文附带）：

{message + len(problem_images) * image_placeholder}

请给出你的 json 处理结果：
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
            assert matches
            
            json_string = matches[0].strip()
            json_dict = deserialize_json(json_string)
            
            required_keys = ["problem_title", "problem_text", "answer"]
            for key in required_keys:
                assert key in json_dict
                assert isinstance(json_dict[key], str)
                # 简单的非空校验
                assert len(json_dict[key]) > 0
            
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
