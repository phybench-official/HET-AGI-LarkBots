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
    
    return {}