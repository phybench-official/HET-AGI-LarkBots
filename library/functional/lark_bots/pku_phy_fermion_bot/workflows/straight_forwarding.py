from .....fundamental import *
from ..equation_rendering import *


__all__ = [
    "HET_problem_system_prompt",
    "straight_forwarding_func_factory",
]


HET_problem_system_prompt = """
你是一位严谨的科学家。请遵循以下原则解答问题，给出详细的解题过程：
0. **答案汇总**：最终答案必须且只能汇总在文末唯一的 `\\boxed{...}` 中（即使有多小问，也请在同一个框内分条列出），严禁在中间推导步骤中使用该标记；
1. **思维原子化**：将解题步骤拆解为不可再分的最小逻辑单元，严禁跳跃步骤；
2. **溯源与说理**：每一步推导必须基于公认的基础原理或定理，拒绝直接引用的小众公式或二级结论；
3. **诚实原则**：若你认为信息不足或无法确信答案，请直接坦诚告知，严禁强行作答或编造。
"""


def straight_forwarding_func_factory(
    model: str,
    lark_bot: LarkBot,
)-> Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]:
    
    async def workflow_func(
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        
        problem_text = context["problem_text"]
        problem_image_keys = context["problem_images"]
        problem_message_id = context["problem_message_id"]
        if problem_image_keys:
            problem_images = await lark_bot.download_message_images_async(
                message_id = problem_message_id,
                image_keys = problem_image_keys,
            )
        else:
            problem_images = []
        
        response = await get_answer_async(
            prompt = problem_text,
            model = lark_bot._config["workflows"]["straight_forwarding"][model]["model"],
            system_prompt = HET_problem_system_prompt,
            images = problem_images,
            image_placeholder = lark_bot.image_placeholder,
            temperature = lark_bot._config["workflows"]["straight_forwarding"][model]["temperature"],
            timeout = lark_bot._config["workflows"]["straight_forwarding"][model]["timeout"],
            trial_num = lark_bot._config["workflows"]["straight_forwarding"][model]["trial_num"],
            trial_interval = lark_bot._config["workflows"]["straight_forwarding"][model]["trial_interval"],
        )
        
        if response:
            rendered_response = await render_equation_async(
                text = response,
                begin_of_equation = lark_bot.begin_of_equation,
                end_of_equation = lark_bot.end_of_equation,
                model = lark_bot._config["equation_rendering"]["model"],
                temperature = lark_bot._config["equation_rendering"]["temperature"],
                timeout = lark_bot._config["equation_rendering"]["timeout"],
                trial_num = lark_bot._config["equation_rendering"]["trial_num"],
                trial_interval = lark_bot._config["equation_rendering"]["trial_interval"],
            )
        else:
            rendered_response = f"由于系统内部原因，{model} 输出为空，建议您再试一次"
        
        return {
            "document_content": rendered_response,
            "response": response,
            "rendered_response": rendered_response,
        }
    
    return workflow_func
    
    