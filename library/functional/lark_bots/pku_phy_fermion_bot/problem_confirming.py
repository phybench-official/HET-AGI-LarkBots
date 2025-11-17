from ....fundamental import *


__all__ = [
    "confirm_problem_async",
]


async def confirm_problem_async(
    problem_text: str,
    problem_images: List[bytes],
    answer: str,
    history: Dict[str, List[Any]],
    model: str,
    temperature: float,
    timeout: int,
    trial_num: int,
    trial_interval: int,
)-> Dict[str, Any]:
    
    """
    多轮次环节
    接收当前 problem_text、problem_images、answer 和 history（会话记录）
    指导这一步应当作何响应，目的是：
        - 补全可能缺失的 answer 字段
        - 检查浅显的错误（如 bad modality、answer mismatch），尝试与用户交互进行纠正，保证题目质量
        - 让用户确认题目（以及题目在飞书云文档中的展示效果），然后再进入后续环节
    返回一个 Dict，保证包含：
        - new_problem_text: Optional[str]
        - new_answer: Optional[str]
        - succeeded: bool
        - response: str
    系统会更新 problem_text、更新 new_answer，根据 succeeded 判断是否终止此循环，
    然后向用户发送 response
    （必要的信息是，如果 succeeded，那么发送此循环最后一条信息后会立即开始 AI 解题环节）
    此环节不负责对齐至内部富文本格式以支持公式渲染的工作。
    """
    
    image_placeholder = "<image_never_used_114514_1919810>"
    
    # 格式化历史记录
    formatted_history = ""
    prompts = history.get("prompt", [])
    roles = history.get("roles", [])
    for p, r in zip(prompts, roles):
        role_name = "用户" if r == "user" else "AI助手"
        formatted_history += f"{role_name}: {p}\n"

    problem_image_num = len(problem_images)

    prompt = f"""
您是一个严谨的物理问题审查助手。
您的任务是依据“当前题目信息”和“对话历史”，判断是否可以进入“AI解题”环节，或者需要与用户交互以修正/补全信息。

# 第一部分：审查规则与决策逻辑

请在【分析】步骤中依次执行以下检查：

1.  **完整性检查**：
    - 检查 `answer` 是否为 "暂无"。如果是，用户最新的回复是否提供了答案？
    - 如果答案仍缺失，必须要求用户补充。

2.  **可行性检查 (画图题拒绝)**：
    - 检查题目是否要求 AI 进行画图（如“画出受力分析图”、“补全光路”）。
    - **规则**：AI 无法生成图像。如果遇到此类要求，必须设 `succeeded=false`，并在 `response` 中明确拒绝，建议用户修改题目为不需画图的描述，或建议用户放弃此题，“去群聊消息中再次@我”提交新的题目。

3.  **一致性检查**：
    - 检查题干是否依赖图片（如“如图所示”），但当前图片数量为 0。如果是，需提示用户进行修改。
    - 检查答案的形式和数量（若有多小问）是否匹配题干
    - 注意：严禁自行解题！您应该 100% 信任用户答案，禁止深入思考问题，禁止对答案本身做正确性判断。

4.  **用户意图判断**：
    - **确认**：用户回复“没问题”、“是的”、“开始吧” -> 准备进入解题环节。
    - **修改/补充**：用户回复提供了新的题干细节或答案 -> 需要提取并更新信息。

5.  **输出动作定义**：
    - **情况 A (完美通过)**：信息完整、可行且用户已确认。
        - `succeeded`: `true`
        - `response`: 获悉确认、表明正在进入后续流程的简短回复（如“确认无误，正在为您调用 AI 求解...”）。
    - **情况 B (需要更新)**：用户提供了修正或补充。
        - `succeeded`: `false` (因为更新后必须让用户再次确认)。
        - `new_problem_text` / `new_answer`: 填入**完整的全新文本**以覆盖旧内容。如果不涉及修改，保持 `null`。
        - `response`: 告知已更新并请求确认。
    - **情况 C (存在问题/闲聊)**：
        - `succeeded`: `false`
        - `new_problem_text` / `new_answer`: `null`
        - `response`: 指出问题或回应闲聊，引导用户进行下一步。

# 第二部分：输出格式

请严格遵循以下格式输出：
1.  先输出 `【分析】`，简要写出推理过程。
2.  再输出 `【输出】`，紧接着是一个标准的 JSON 代码块。

JSON 结构定义：
```json
{{
  "new_problem_text": "string | null (完整的题干新文本)",
  "new_answer": "string | null (完整的答案新文本)",
  "succeeded": boolean,
  "response": "string (回复给用户的消息)"
}}
````

# 第三部分：Few-Shot 样例

**样例 1: 完美确认**
【分析】
答案存在且完整。题目没有问题。用户回复“没问题”表示确认。满足解题条件。
【输出】

```json
{{
  "new_problem_text": null,
  "new_answer": null,
  "succeeded": true,
  "response": "确认无误，正在为您调用 AI 进行求解，请稍候..."
}}
```

**样例 2: 用户补充缺失的答案**
【分析】
原答案为“暂无”。用户回复中提供了答案“v=gt”。需要更新 answer 字段。状态仍为未成功，需等待用户对更新后的结果做最终确认。
【输出】

```json
{{
  "new_problem_text": null,
  "new_answer": "v=gt",
  "succeeded": false,
  "response": "已收到，参考答案已更新。请确认现在的题目信息是否完整？"
}}
```

**样例 3: 拒绝画图要求**
【分析】
题干包含“请画出...”。AI 无法作图。必须拒绝并引导用户修改。
【输出】

```json
{{
  "new_problem_text": null,
  "new_answer": null,
  "succeeded": false,
  "response": "抱歉，我无法处理要求“画图”的题目。建议您修改题目描述为不涉及画图的形式，或仅要求计算数值。"
}}
```

**样例 4: 用户修正题干数值**
【分析】
用户要求将题干中质量由 3kg 改为 2kg。需生成包含正确数值的**完整**新题干覆盖旧题干。
【输出】

```json
{{
  "new_problem_text": "质量为 2kg 的小球在光滑平面上运动...",
  "new_answer": null,
  "succeeded": false,
  "response": "已将题干修正为“质量为 2kg”。请问现在信息准确了吗？"
}}
```

# 第四部分：当前输入任务

请根据以下信息进行处理：

  - **当前题干 (problem_text)**: {problem_text + len(problem_images) * image_placeholder}
  - **图片数量**: {problem_image_num} 张
  - **当前参考答案 (answer)**: {answer}
  - **对话历史**:
    {formatted_history}

请给出你的分析与输出：
"""

    result = {}

    def check_and_accept(
        response: str,
    )-> bool:
        nonlocal result
        print(f"Confirm Problem: checking the following response now\n{response}")
        try:
            halfway_result = {}
            # 提取 【输出】 后的 JSON 块
            json_pattern = r'```json\s*(.*?)\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            assert matches
            
            # 取最后一个匹配块，确保不抓取到 Few-Shot 里的 JSON
            json_string = matches[-1].strip()
            json_dict = deserialize_json(json_string)
            
            # 字段存在性检查
            required_keys = ["new_problem_text", "new_answer", "succeeded", "response"]
            for key in required_keys:
                assert key in json_dict
            
            # 类型检查
            if json_dict["new_problem_text"] is not None:
                assert isinstance(json_dict["new_problem_text"], str)
            if json_dict["new_answer"] is not None:
                assert isinstance(json_dict["new_answer"], str)
            assert isinstance(json_dict["succeeded"], bool)
            assert isinstance(json_dict["response"], str)
            assert len(json_dict["response"]) > 0

            halfway_result["new_problem_text"] = json_dict["new_problem_text"]
            halfway_result["new_answer"] = json_dict["new_answer"]
            halfway_result["succeeded"] = json_dict["succeeded"]
            halfway_result["response"] = json_dict["response"]
            
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
