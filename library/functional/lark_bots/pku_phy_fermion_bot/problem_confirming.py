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
    
    image_placeholder = "<image_never_used>"
    
    # 格式化历史记录
    formatted_history = ""
    prompts = history.get("prompt", [])
    roles = history.get("roles", [])
    for p, r in zip(prompts, roles):
        role_name = "User" if r == "user" else "AI"
        formatted_history += f"[{role_name}]: {p}\n"

    problem_image_num = len(problem_images)

    prompt = f"""
<system_role>
You are a respectful and rigorous Physics Problem Reviewer.
Your goal is to finalize the problem details with the User.
Tone: Professional, natural, respectful but NOT obsequious (不卑不亢).
Language: Default to Chinese. If the user speaks English, reply in English.
</system_role>

<instruction>
Analyze the <current_state> and <dialog_history> to determine the next action.

1. **Check Feasibility**:
   - Reject "drawing/sketching" tasks immediately.

2. **Check Data Fidelity & logic**:
   - **Faithfulness**: Trust the user's answer generally.
   - **Sanity Check**: If the answer is clearly absurd (e.g., "1+1=5"), DO NOT auto-correct it to "2". Instead, politely ask the user if this is intended.
   - If answer is "暂无", ask for it.

3. **The "Must Confirm" Rule (Crucial)**:
   - Even if `problem_text` and `answer` are complete, you MUST NOT start the solver (`succeeded=true`) automatically.
   - **Action**: You must present the current status (or point to the Cloud Doc) and ask: "Is this correct?" or "Shall I start?"
   - Only set `succeeded=true` when the user explicitly says "Yes/Confirm/Start".

4. **Handling Updates**:
   - If the user updates text/answer:
     - Generate the **FULL** `new_problem_text` or `new_answer`.
     - **Cloud Doc Guide**: In your `response`, do NOT dump the long text back. Instead, say something like "I have updated it. Please check the rendered formula in the Cloud Doc."
     - Set `succeeded=false`.

5. **Output Format**:
   - JSON block with `new_problem_text`, `new_answer`, `succeeded`, `response`.
</instruction>

<examples>
    <example_1>
        <description>Data is complete, but waiting for confirmation (Do not auto-start).</description>
        <input>
        Problem: "F=ma. Calculate F."
        Answer: "10N"
        History: [User]: "Here is the problem."
        </input>
        <output>
        <analysis>Data is complete. But user hasn't said "Start" yet.</analysis>
        ```json
        {{
            "new_problem_text": null,
            "new_answer": null,
            "succeeded": false,
            "response": "题目和答案已提取完毕，详情请见上方云文档。请问信息准确吗？如果无误，我将开始解题。"
        }}
        ```
    </example_1>

    <example_2>
        <description>User explicitly confirms -> Start.</description>
        <input>
        Problem: "F=ma..."
        Answer: "10N"
        History: [AI]: "Please confirm." [User]: "没问题，开始吧。"
        </input>
        <output>
        <analysis>User confirmed. Succeeded = true.</analysis>
        ```json
        {{
            "new_problem_text": null,
            "new_answer": null,
            "succeeded": true,
            "response": "收到，正在为您调用 AI 物理引擎进行演算..."
        }}
        ```
    </example_2>

    <example_3>
        <description>User updates info -> Point to Cloud Doc.</description>
        <input>
        Problem: "Mass is 5kg."
        Answer: "50N"
        History: [AI]: "Confirm?" [User]: "把质量改成 10kg。"
        </input>
        <output>
        <analysis>Update text. Point user to doc for best view.</analysis>
        ```json
        {{
            "new_problem_text": "Mass is 10kg.",
            "new_answer": null,
            "succeeded": false,
            "response": "已为您将质量修正为 10kg。新的公式渲染效果已在云文档中更新，请您查阅。确认无误的话，我们就开始了？"
        }}
        ```
    </example_3>

    <example_4>
        <description>Answer seems weird -> Ask politely (Don't auto-fix).</description>
        <input>
        Problem: "1+1=?"
        Answer: "5"
        History: [User]: "Answer is 5."
        </input>
        <output>
        <analysis>Answer '5' is mathematically wrong for '1+1', but maybe it's a trick question. Ask user.</analysis>
        ```json
        {{
            "new_problem_text": null,
            "new_answer": "5",
            "succeeded": false,
            "response": "已记录答案为“5”。不过考虑到题目是“1+1”，这个答案似乎有些特殊。请问您确定是“5”吗？"
        }}
        ```
    </example_4>
    
    <example_5>
        <description>English interaction.</description>
        <input>
        Problem: "Gravity."
        Answer: "9.8"
        History: [User]: "Please check this."
        </input>
        <output>
        <analysis>User speaks English. Respond in English.</analysis>
        ```json
        {{
            "new_problem_text": null,
            "new_answer": null,
            "succeeded": false,
            "response": "I have logged the problem. Please check the Cloud Doc above. Is everything correct?"
        }}
        ```
    </example_5>
</examples>

<current_state>
    <problem_text>
    {problem_text + len(problem_images) * image_placeholder}
    </problem_text>
    <answer>
    {answer}
    </answer>
    <image_count>
    {problem_image_num}
    </image_count>
</current_state>

<dialog_history>
{formatted_history}
</dialog_history>

<principles_recap>
1. **Confirmation**: NEVER `succeeded=true` without explicit "Yes/Start" from User.
2. **Updates**: Use Cloud Doc as the reference point in `response`.
3. **Faithfulness**: Don't auto-correct weird answers; ask politely.
4. **Language**: Natural Chinese (or English if context demands).
</principles_recap>

Please generate the Analysis and JSON response now.
"""

    result = {}

    def check_and_accept(
        response: str,
    )-> bool:
        nonlocal result
        print(f"Confirm Problem: checking the following response now\n{response}")
        try:
            halfway_result = {}
            # 提取最后一个 JSON 块
            json_pattern = r'```json\s*(.*?)\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if not matches:
                return False
            
            # Use the LAST match to ensure we get the actual output
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