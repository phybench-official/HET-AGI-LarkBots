import functools
import traceback
from typing import Any, Dict, Callable
from ..wolfram_tools import WolframAPIManager 


__all__ = [
    "wolfram_tool",
]


def _execute_query(
    query: str,
    api_manager: WolframAPIManager,
    timeout: int,
    verbose: bool,
)-> str:
    
    output: str = ""
    try:
        output = api_manager.query(query=query, timeout=timeout)
    except Exception as e:
        output = f"调用 Wolfram API 管理器时主程出错: {e}\n{traceback.format_exc()}"

    if verbose: 
        print(f"--- [Wolfram Tool Executed] ---")
        print(f"Query:\n{query}")
        print(f"Result:\n{output}")
        print(f"-------------------------------")
    
    return output


def wolfram_tool(
    timeout: int = 60,
    verbose: bool = False,
    wolfram_api_keys_path: str = "wolfram_api_keys.json",
)-> Dict[str, Any]:

    api_manager = WolframAPIManager(
        wolfram_api_keys_path = wolfram_api_keys_path,
    )
    
    bound_implementation: Callable[..., str] = functools.partial(
        _execute_query,
        api_manager=api_manager,
        timeout=timeout,
        verbose=verbose
    )
    
    tool_definition: Dict[str, Any] = {
        "name": "query_wolfram_alpha",
        "description": (
            "查询 WolframAlpha 以进行直接的数学计算、科学查询和获取事实数据。\n"
            "用于解单步方程、进行单步函数求导、获取数学事实、单位换算和检索百科知识。\n"
            "重要约束 (Important Notes):\n"
            f"1. **超时**: 查询有 {timeout} 秒的严格网络超时限制。\n"
            "2. **能力边界 (重要)**: 此工具基于 v2/query (Simple API)，"
            "仅适用于**单一、直接的计算或事实查询**。\n"
            "   - **不**支持: 复杂的自然语言指令。\n"
            "   - **不**支持: 复杂的多步骤推理 (如 '求解 A 并代入 B')。\n"
            "如果需要多步推理，请多次调用本工具，每次执行单一步骤\n"
            "3. **查询**: 请使用直接的数学表达式或简单的事实问题。"
        ),
        "parameters": {
            "query": {
                "type": "string",
                "description": (
                    "要发送给 WolframAlpha 的查询字符串 (必须是单一、直接的查询)。\n"
                    "示例 (有效): 'derivative of x^4 sin(x)', 'capital of France', 'zeta(2)', 'solve x^2 + 5x = 0'\n"
                    "示例 (无效，会失败): 'zeta(t) where t - 3 sin(t) = 0 and t > 0', 'zeta(2) in the form of continued fraction'"
                ),
                "required": True,
            },
        },
        "implementation": bound_implementation,
    }
    
    return tool_definition