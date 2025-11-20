from .....fundamental import *
from ..equation_rendering import *


__all__ = [
    "with_tools_func_factory",
]


def with_tools_func_factory(
    model: str,
    lark_bot: LarkBot,
)-> Callable[[Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]:
    
    async def workflow_func(
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        
        problem_text = context["problem_text"]
        problem_images = context["problem_images"]
        
        raw_response = await get_answer_async(
            prompt = problem_text,
            model = lark_bot._config["workflows"]["with_tools"][model]["model"],
            system_prompt = "请回答这道物理题目，列出详细解答过程。请善用 Python 和 Mathematica 工具。",
            images = problem_images,
            image_placeholder = lark_bot.image_placeholder,
            temperature = lark_bot._config["workflows"]["with_tools"][model]["temperature"],
            timeout = lark_bot._config["workflows"]["with_tools"][model]["timeout"],
            trial_num = lark_bot._config["workflows"]["with_tools"][model]["trial_num"],
            trial_interval = lark_bot._config["workflows"]["with_tools"][model]["trial_interval"],
            tools = [
                mathematica_tool(
                    timeout = 60,
                    verbose = True,
                ),
                python_tool(
                    timeout = 60,
                    verbose = True,
                ),
            ],
            tool_use_trial_num = lark_bot._config["workflows"]["with_tools"][model]["tool_use_trial_num"],
        )
        
        if raw_response:
            response = await render_equation_async(
                text = raw_response,
                begin_of_equation = lark_bot.begin_of_equation,
                end_of_equation = lark_bot.end_of_equation,
                model = lark_bot._config["equation_rendering"]["model"],
                temperature = lark_bot._config["equation_rendering"]["temperature"],
                timeout = lark_bot._config["equation_rendering"]["timeout"],
                trial_num = lark_bot._config["equation_rendering"]["trial_num"],
                trial_interval = lark_bot._config["equation_rendering"]["trial_interval"],
            )
        else:
            response = f"由于内部原因，{model} 输出为空，建议您再试一次"
        
        return {
            "document_content": response,
            "raw_response": raw_response,
        }
    
    return workflow_func
    
    