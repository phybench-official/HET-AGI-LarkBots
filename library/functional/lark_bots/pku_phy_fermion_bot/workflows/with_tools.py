from .....fundamental import *
from ..equation_rendering import *


__all__ = [
    "with_tools_func_factory",
]


system_prompt_for_physics_problems = """
你是一位严谨的科学家。请遵循以下原则解答问题，给出详细的解题过程：
1. **思维原子化**：将解题步骤拆解为不可再分的最小逻辑单元，严禁跳跃步骤；
2. **溯源与说理**：每一步推导必须基于公认的基础原理或定理，拒绝直接引用的小众公式或二级结论；
3. **诚实原则**：若你认为信息不足或无法确信答案，请直接坦诚告知，严禁强行作答或编造；
4. **工具依赖**：任何复杂的数值计算或符号推导，优先使用 Python 或 Mathematica 工具验证，尽可能减少不可靠的自行计算。

关于 Mathematica 工具的特别说明：
我们已在 Mathematica 工具中接入了高能物理的常用拓展，包括 
    - FeynCalc
    - FeynArts
    - FormCalc
    - Package-X
    - Susyno
    - LieART
    - SARAH
    - HPL
    - PolyLogTools
    - xAct
    - GR
    - LiteRed2
对于涉及高能物理的计算密集型推理步骤（如：计算费曼积分），或求导、解微分方程这类适合用 Mathematica 来做的推理步骤，我们强烈建议你调用 Mathematica 工具进行解答；对于其余计算密集型推理步骤，你可以使用更轻量级的 Python 工具来解答，numpy、scipy 等库也已为你安装好。
"""


def with_tools_func_factory(
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
        
        tool_use_trials = []
        original_python_tool = python_tool(
            timeout = lark_bot._config["workflows"]["with_tools"]["python_timeout"],
            verbose = True,
        )
        original_mathematica_tool = mathematica_tool(
            timeout = lark_bot._config["workflows"]["with_tools"]["mathematica_timeout"],
            verbose = True,
        )
        hijacked_python_tool = {
            **original_python_tool
        }
        hijacked_mathematica_tool = {
            **original_mathematica_tool
        }
        async def hijacked_python_tool_implementation(
            **kwargs,
        )-> str:
            nonlocal tool_use_trials
            result = await asyncio.to_thread(original_python_tool["implementation"], **kwargs)
            tool_use_trials.append({
                "name": "Python",
                "input": f"{lark_bot.begin_of_code}{lark_bot.begin_of_language}Python{lark_bot.end_of_language}{lark_bot.begin_of_content}{kwargs['code']}{lark_bot.end_of_content}{lark_bot.end_of_code}",
                "output": f"{lark_bot.begin_of_code}{lark_bot.begin_of_language}Python{lark_bot.end_of_language}{lark_bot.begin_of_content}{result}{lark_bot.end_of_content}{lark_bot.end_of_code}",
            })
            return result
        async def hijacked_mathematica_tool_implementation(
            **kwargs,
        )-> str:
            nonlocal tool_use_trials
            result = await original_mathematica_tool["implementation"](**kwargs)
            tool_use_trials.append({
                "name": "Mathematica",
                "input": f"{lark_bot.begin_of_code}{lark_bot.begin_of_language}Plain Text{lark_bot.end_of_language}{lark_bot.begin_of_content}{kwargs['code']}{lark_bot.end_of_content}{lark_bot.end_of_code}",
                "output": f"{lark_bot.begin_of_code}{lark_bot.begin_of_language}JSON{lark_bot.end_of_language}{lark_bot.begin_of_content}{result}{lark_bot.end_of_content}{lark_bot.end_of_code}",
            })
            return result
        hijacked_python_tool["implementation"] = hijacked_python_tool_implementation
        hijacked_mathematica_tool["implementation"] = hijacked_mathematica_tool_implementation

        raw_response = await get_answer_async(
            prompt = problem_text,
            model = lark_bot._config["workflows"]["with_tools"][model]["model"],
            system_prompt = system_prompt_for_physics_problems,
            images = problem_images,
            image_placeholder = lark_bot.image_placeholder,
            temperature = lark_bot._config["workflows"]["with_tools"][model]["temperature"],
            timeout = lark_bot._config["workflows"]["with_tools"][model]["timeout"],
            trial_num = lark_bot._config["workflows"]["with_tools"][model]["trial_num"],
            trial_interval = lark_bot._config["workflows"]["with_tools"][model]["trial_interval"],
            tools = [
                hijacked_python_tool,
                hijacked_mathematica_tool,
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
        
        document_content = ""
        document_content += response
        if len(tool_use_trials):
            document_content += (
                f"{lark_bot.begin_of_forth_heading}"
                "工具调用情况"
                f"{lark_bot.end_of_forth_heading}"
            )
            for index, tool_use_trial in enumerate(tool_use_trials, 1):
                document_content += (
                    f"{lark_bot.begin_of_fifth_heading}"
                    f"第 {index} 次工具调用 | {tool_use_trial['name']}"
                    f"{lark_bot.end_of_fifth_heading}"
                )
                document_content += f"工具调用输入："
                document_content += tool_use_trial["input"]
                document_content += f"工具调用输出："
                document_content += tool_use_trial["output"]
        
        return {
            "document_content": document_content,
            "raw_response": raw_response,
            "response": response,
            "tool_use_trials": tool_use_trials,
        }
    
    return workflow_func
    
    