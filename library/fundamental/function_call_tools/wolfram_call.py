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
            "查询 WolframAlpha 以进行数学计算、科学查询和获取事实数据。\n"
            "用于解方程、获取数学见解、单位换算和检索百科知识。\n"
            "重要约束 (Important Notes):\n"
            f"1. **超时**: 查询有 {timeout} 秒的严格网络超时限制。\n"
            "2. **查询**: 请使用自然语言或数学表达式进行查询。"
        ),
        "parameters": {
            "query": {
                "type": "string",
                "description": (
                    "要发送给 WolframAlpha 的查询字符串。"
                    "例如: 'derivative of x^4 sin(x)' 或 'capital of France'"
                ),
                "required": True,
            },
        },
        "implementation": bound_implementation,
    }
    
    return tool_definition