"""
Mathematica MCP Tool

提供通过 MCP 服务器执行 Mathematica 代码的工具定义。
使用全局单例 MCP 客户端管理连接，支持异步调用。
"""

import asyncio
import traceback
from typing import Any, Dict, Callable, Optional

from ..mcp_client import MCPHTTPClient, get_server_config


__all__ = [
    "mathematica_tool",
    "MathematicaMCPManager",
]


class MathematicaMCPManager:
    """
    Mathematica MCP 客户端管理器（单例模式）

    负责管理 MCP 客户端的生命周期，避免重复连接。
    """

    _instance: Optional["MathematicaMCPManager"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        mcp_server_name: str = "mathematica",
        mcp_config_path: str = "mcp_servers_config.json",
        verbose: bool = False,
    ):
        self.mcp_server_name = mcp_server_name
        self.mcp_config_path = mcp_config_path
        self.verbose = verbose

        self.mcp_client: Optional[MCPHTTPClient] = None
        self._connected: bool = False

    @classmethod
    async def get_instance(
        cls,
        mcp_server_name: str = "mathematica",
        mcp_config_path: str = "mcp_servers_config.json",
        verbose: bool = False,
    ) -> "MathematicaMCPManager":
        """获取单例实例"""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(mcp_server_name, mcp_config_path, verbose)
            return cls._instance

    async def ensure_connected(self) -> None:
        """确保 MCP 客户端已连接"""
        if self._connected and self.mcp_client is not None:
            return

        if self.verbose:
            print(f"[MathematicaMCPManager] 连接到 MCP 服务器: {self.mcp_server_name}")

        config = get_server_config(self.mcp_server_name, self.mcp_config_path)
        self.mcp_client = MCPHTTPClient(config, verbose=self.verbose)
        await self.mcp_client.__aenter__()
        self._connected = True

        if self.verbose:
            print(f"[MathematicaMCPManager] 已连接")

    async def execute_mathematica(
        self,
        code: str,
        timeout: int = 60,
    ) -> str:
        """
        执行 Mathematica 代码

        Args:
            code: Mathematica 代码字符串
            timeout: 超时时间（秒）

        Returns:
            执行结果字符串
        """
        await self.ensure_connected()

        if self.mcp_client is None:
            return "MCP 客户端未初始化"

        try:
            result = await self.mcp_client.call_tool(
                "evaluate_mathematica",
                {"code": code, "timeout_seconds": timeout},
                timeout=timeout + 5  # 客户端超时略大于服务器端超时，留出缓冲时间
            )
            output = self.mcp_client.parse_response(result)
            return output

        except Exception as e:
            return f"执行 Mathematica 代码失败: {e}\n{traceback.format_exc()}"

    async def close(self) -> None:
        """关闭 MCP 客户端连接"""
        if self._connected and self.mcp_client is not None:
            await self.mcp_client.__aexit__(None, None, None)
            self._connected = False
            self.mcp_client = None

            if self.verbose:
                print(f"[MathematicaMCPManager] 已断开连接")


async def _execute_mathematica_async(
    code: str,
    manager: MathematicaMCPManager,
    timeout: int,
    verbose: bool,
) -> str:
    """
    异步执行 Mathematica 代码（内部函数）

    Args:
        code: Mathematica 代码
        manager: MCP 管理器实例
        timeout: 超时时间
        verbose: 是否打印详细日志

    Returns:
        执行结果
    """
    try:
        output = await manager.execute_mathematica(code=code, timeout=timeout)

        if verbose:
            print(f"--- [Mathematica Tool Executed] ---")
            print(f"Code:\n{code}")
            print(f"Result:\n{output}")
            print(f"-----------------------------------")

        return output

    except Exception as e:
        error_msg = f"调用 Mathematica MCP 管理器时出错: {e}\n{traceback.format_exc()}"

        if verbose:
            print(f"--- [Mathematica Tool Error] ---")
            print(f"Code:\n{code}")
            print(f"Error:\n{error_msg}")
            print(f"--------------------------------")

        return error_msg


def mathematica_tool(
    timeout: int = 60,
    verbose: bool = False,
    mcp_server_name: str = "mathematica",
    mcp_config_path: str = "mcp_servers_config.json",
) -> Dict[str, Any]:
    """
    创建 Mathematica MCP 工具定义

    Args:
        timeout: 执行超时时间（秒，默认 60）
        verbose: 是否打印详细日志（默认 False）
        mcp_server_name: MCP 服务器名称（默认 "mathematica"）
        mcp_config_path: MCP 配置文件路径（默认 "mcp_servers_config.json"）

    Returns:
        pywheels 格式的工具定义字典

    使用示例:
        from library.fundamental.function_call_tools import mathematica_tool
        from pywheels.llm_tools import get_answer_async

        response = await get_answer_async(
            prompt="请计算积分",
            model="Deepseek-V3",
            tools=[mathematica_tool(timeout=60, verbose=True)],
        )
    """

    async def implementation_wrapper(code: str) -> str:
        manager = await MathematicaMCPManager.get_instance(
            mcp_server_name=mcp_server_name,
            mcp_config_path=mcp_config_path,
            verbose=verbose,
        )

        return await _execute_mathematica_async(
            code=code,
            manager=manager,
            timeout=timeout,
            verbose=verbose,
        )

    tool_definition: Dict[str, Any] = {
        "name": "execute_mathematica",
        "description": (
            "通过 Mathematica MCP 服务器执行 Mathematica 代码并返回计算结果。\n"
            "适用于需要符号计算、高级数学函数、微积分、方程求解等复杂数学问题。\n"
            "重要约束 (Important Notes):\n"
            f"1. **超时**: 代码执行有 {timeout} 秒的严格超时限制。\n"
            "2. **语法**: 使用标准 Mathematica 语法（如 Integrate[x^2 Sin[x], x]）。\n"
            "3. **输出**: Mathematica 会自动返回表达式的计算结果，无需使用 Print。\n"
            "4. **符号计算**: 支持符号积分、微分、方程求解等高级数学运算。\n"
            "5. **精确计算**: 支持任意精度的数值计算和符号化简。"
        ),
        "parameters": {
            "code": {
                "type": "string",
                "description": (
                    "要执行的 Mathematica 代码字符串。必须使用标准 Mathematica 语法。\n"
                    "示例:\n"
                    "  - 积分: 'Integrate[x^2 * Sin[x], x]'\n"
                    "  - 求解方程: 'Solve[x^2 + 5*x + 6 == 0, x]'\n"
                    "  - 微分: 'D[Sin[x^2], x]'\n"
                    "  - 简化: 'Simplify[(x^2 - 1)/(x - 1)]'"
                ),
                "required": True,
            },
        },
        "implementation": implementation_wrapper,
    }

    return tool_definition
