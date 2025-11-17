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
    
    return {}