from ....fundamental import *


__all__ = [
    "solve_problem_async",
]


async def solve_problem_async(
    problem_text: str,
    problem_images: List[bytes],
    model: str,
    temperature: float,
    timeout: int,
    trial_num: int,
    trial_interval: int,
) -> Dict[str, Any]:
    
    """
    AI 解题模块
    接收确认后的题目文本和原始图片，调用大模型生成详细的物理具体过程
    返回 AI 解答和解题过程信息（如，工具调用情况）
    此环节不负责对齐至内部富文本格式以支持公式渲染的工作。
    """
    
    image_placeholder = "<image_never_used>"
    response = await get_answer_async(
        system_prompt = "请善用 execute_mathematica 工具",
        prompt = problem_text + len(problem_images) * image_placeholder,
        model = model,
        images = problem_images,
        image_placeholder = image_placeholder,
        temperature = temperature,
        timeout = timeout,
        trial_num = trial_num,
        trial_interval = trial_interval,
        tools = [
            mathematica_tool(
                timeout = 60,
                verbose = True,
            ),
        ],
        tool_use_trial_num = 10,
    )
    return {
        "AI_solution": response,
    }
