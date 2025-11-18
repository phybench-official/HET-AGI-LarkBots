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
) -> str:
    
    """
    AI 解题模块
    接收确认后的题目文本和原始图片，调用大模型生成详细的物理具体过程
    返回纯文本格式的解答，后续需经由 render_equation_async 处理
    """
    
    image_placeholder = "<image_never_used_114514_1919810>"
    response = await get_answer_async(
        prompt = problem_text + len(problem_images) * image_placeholder,
        model = model,
        images = problem_images,
        image_placeholder = image_placeholder,
        temperature = temperature,
        timeout = timeout,
        trial_num = trial_num,
        trial_interval = trial_interval,
    )
    return response
