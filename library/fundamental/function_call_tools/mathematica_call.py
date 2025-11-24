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
    "mathematica_list_packages_tool",
    "get_mathematica_openai_schema",
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

    async def list_packages(self) -> str:
        """
        列出可用的 Mathematica 包

        Returns:
            可用包的信息字符串
        """
        await self.ensure_connected()

        if self.mcp_client is None:
            return "MCP 客户端未初始化"

        try:
            result = await self.mcp_client.call_tool(
                "list_packages",
                {},
                timeout=30
            )
            output = self.mcp_client.parse_response(result)
            return output

        except Exception as e:
            return f"获取 Mathematica 包列表失败: {e}\n{traceback.format_exc()}"

    async def execute_mathematica(
        self,
        code: str,
        packages: list[str] | None = None,
        timeout: int = 60,
    ) -> str:
        """
        执行 Mathematica 代码

        Args:
            code: Mathematica 代码字符串
            packages: 需要加载的包列表，如 ["FeynCalc", "FeynArts"]
            timeout: 超时时间（秒）

        Returns:
            执行结果字符串
        """
        await self.ensure_connected()

        if self.mcp_client is None:
            return "MCP 客户端未初始化"

        try:
            params = {
                "code": code,
                "timeout_seconds": timeout,
            }
            if packages:
                params["packages"] = packages

            result = await self.mcp_client.call_tool(
                "execute_mathematica",
                params,
                timeout=timeout + 30  # 客户端超时要考虑包加载时间
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
    packages: list[str] | None,
    timeout: int,
    verbose: bool,
) -> str:
    """
    异步执行 Mathematica 代码（内部函数）

    Args:
        code: Mathematica 代码
        manager: MCP 管理器实例
        packages: 需要加载的包列表
        timeout: 超时时间
        verbose: 是否打印详细日志

    Returns:
        执行结果
    """
    try:
        output = await manager.execute_mathematica(
            code=code,
            packages=packages,
            timeout=timeout
        )

        if verbose:
            print(f"--- [Mathematica Tool Executed] ---")
            if packages:
                print(f"Packages: {packages}")
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


async def _list_packages_async(
    manager: MathematicaMCPManager,
    verbose: bool,
) -> str:
    """
    异步列出可用包（内部函数）

    Args:
        manager: MCP 管理器实例
        verbose: 是否打印详细日志

    Returns:
        可用包列表
    """
    try:
        output = await manager.list_packages()

        if verbose:
            print(f"--- [Mathematica Packages Listed] ---")
            print(f"Result:\n{output}")
            print(f"-------------------------------------")

        return output

    except Exception as e:
        error_msg = f"获取包列表时出错: {e}\n{traceback.format_exc()}"

        if verbose:
            print(f"--- [List Packages Error] ---")
            print(f"Error:\n{error_msg}")
            print(f"-----------------------------")

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
        符合 function calling 规范的工具定义字典

    使用示例:
        from library.fundamental.function_call_tools import mathematica_tool
        from pywheels.llm_tools import get_answer_async

        response = await get_answer_async(
            prompt="请计算积分",
            model="Deepseek-V3",
            tools=[mathematica_tool(timeout=60, verbose=True)],
        )
    """

    async def implementation_wrapper(
        code: str,
        packages: list[str] | None = None,
    ) -> str:
        manager = await MathematicaMCPManager.get_instance(
            mcp_server_name=mcp_server_name,
            mcp_config_path=mcp_config_path,
            verbose=verbose,
        )

        return await _execute_mathematica_async(
            code=code,
            manager=manager,
            packages=packages,
            timeout=timeout,
            verbose=verbose,
        )

    tool_definition: Dict[str, Any] = {
        "name": "execute_mathematica",
        "description": (
            "通过 Wolfram Mathematica 执行符号计算和数值计算，返回精确结果。\n\n"
            "## 核心能力\n"
            "- **符号计算**: 积分、微分、级数展开、极限、方程求解\n"
            "- **数值计算**: 高精度数值求解、数值积分、优化\n"
            "- **线性代数**: 矩阵运算、特征值、矩阵分解\n"
            "- **物理计算**: 量子场论 (QFT)、费曼图、圈积分计算\n\n"
            "## 可用物理计算包\n"
            "通过 packages 参数加载专业物理计算包：\n"
            "- **FeynCalc**: 量子场论符号计算，Dirac代数、圈积分、费曼参数化\n"
            "- **FeynArts**: 费曼图生成和振幅计算\n"
            "- **FORM**: 大规模符号操作\n\n"
            "## 重要约束\n"
            f"1. 超时限制: {timeout} 秒\n"
            "2. 使用标准 Mathematica InputForm 语法\n"
            "3. 代码中不要包含 << 或 Needs[] 加载包，使用 packages 参数\n"
            "4. 结果自动返回，通常不需要 Print\n"
        ),
        "parameters": {
            "code": {
                "type": "string",
                "description": (
                    "Mathematica 代码 (InputForm 语法)。\n\n"
                    "基础示例:\n"
                    "  - 不定积分: 'Integrate[x^2 * Sin[x], x]'\n"
                    "  - 定积分: 'Integrate[Exp[-x^2], {x, 0, Infinity}]'\n"
                    "  - 求解方程: 'Solve[x^2 + 5*x + 6 == 0, x]'\n"
                    "  - 微分: 'D[Sin[x^2], x]'\n"
                    "  - 级数展开: 'Series[Exp[x], {x, 0, 5}]'\n"
                    "  - 矩阵求逆: 'Inverse[{{1, 2}, {3, 4}}]'\n\n"
                    "FeynCalc 示例 (需设置 packages=['FeynCalc']):\n"
                    "  - Dirac 矩阵简化: 'DiracSimplify[GA[mu, nu, mu]]'\n"
                    "  - 圈积分: 'TID[FAD[{q, m}] SPD[q, p], q]'\n"
                    "  - 费曼参数化: 'FCFeynmanParametrize[FAD[{q, m1}, {q + p, m2}], {q}]'\n"
                ),
                "required": True,
            },
            "packages": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "需要加载的 Mathematica 包列表。可选值:\n"
                    "- 'FeynCalc': 量子场论计算 (Dirac代数, 圈积分, 张量约化)\n"
                    "- 'FeynArts': 费曼图生成\n"
                    "- 'FORM': 符号操作\n\n"
                    "示例: ['FeynCalc'] 或 ['FeynCalc', 'FeynArts']"
                ),
                "required": False,
            },
        },
        "implementation": implementation_wrapper,
    }

    return tool_definition


def mathematica_list_packages_tool(
    verbose: bool = False,
    mcp_server_name: str = "mathematica",
    mcp_config_path: str = "mcp_servers_config.json",
) -> Dict[str, Any]:
    """
    创建列出 Mathematica 可用包的工具定义

    Args:
        verbose: 是否打印详细日志
        mcp_server_name: MCP 服务器名称
        mcp_config_path: MCP 配置文件路径

    Returns:
        符合 function calling 规范的工具定义字典
    """

    async def implementation_wrapper() -> str:
        manager = await MathematicaMCPManager.get_instance(
            mcp_server_name=mcp_server_name,
            mcp_config_path=mcp_config_path,
            verbose=verbose,
        )

        return await _list_packages_async(
            manager=manager,
            verbose=verbose,
        )

    tool_definition: Dict[str, Any] = {
        "name": "list_mathematica_packages",
        "description": (
            "列出 Mathematica 服务器上可用的物理计算包及其说明。\n"
            "在使用 execute_mathematica 的 packages 参数前，可以先调用此工具确认可用的包。"
        ),
        "parameters": {},
        "implementation": implementation_wrapper,
    }

    return tool_definition


def get_mathematica_openai_schema(timeout: int = 60) -> list[Dict[str, Any]]:
    """
    获取符合 OpenAI Function Calling 规范的 Mathematica 工具 schema

    这是提供给外部大模型的标准接口，支持 OpenAI 等主流大模型的 function calling 格式。

    Args:
        timeout: 执行超时时间（秒）

    Returns:
        包含 execute_mathematica 和 list_mathematica_packages 的 schema 列表

    使用示例:
        # OpenAI SDK
        import openai
        from library.fundamental.function_call_tools import get_mathematica_openai_schema

        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": "计算积分"}],
            tools=get_mathematica_openai_schema(timeout=60),
            tool_choice="auto"
        )
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "execute_mathematica",
                "description": (
                    "Execute Wolfram Mathematica code for symbolic and numerical computations.\n\n"
                    "Core Capabilities:\n"
                    "- Symbolic: Integration, differentiation, series expansion, limits, equation solving\n"
                    "- Numerical: High-precision solving, numerical integration, optimization\n"
                    "- Linear Algebra: Matrix operations, eigenvalues, matrix decomposition\n"
                    "- Physics: Quantum Field Theory (QFT), Feynman diagrams, loop integrals\n\n"
                    "Available Physics Packages (use packages parameter):\n"
                    "- FeynCalc: QFT symbolic calculations (Dirac algebra, loop integrals)\n"
                    "- FeynArts: Feynman diagram generation\n"
                    "- FORM: Large-scale symbolic manipulation\n\n"
                    "Important Constraints:\n"
                    f"1. Timeout: {timeout} seconds\n"
                    "2. Use standard Mathematica InputForm syntax\n"
                    "3. Do NOT include << or Needs[] in code, use packages parameter\n"
                    "4. Results are returned automatically"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {
                            "type": "string",
                            "description": (
                                "Mathematica code in InputForm syntax.\n\n"
                                "Basic examples:\n"
                                "- Integral: 'Integrate[x^2 * Sin[x], x]'\n"
                                "- Solve: 'Solve[x^2 + 5*x + 6 == 0, x]'\n"
                                "- Differentiate: 'D[Sin[x^2], x]'\n"
                                "- Series: 'Series[Exp[x], {x, 0, 5}]'\n\n"
                                "FeynCalc examples (set packages=['FeynCalc']):\n"
                                "- 'DiracSimplify[GA[mu, nu, mu]]'\n"
                                "- 'TID[FAD[{q, m}] SPD[q, p], q]'"
                            ),
                        },
                        "packages": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Packages to load. Options: 'FeynCalc', 'FeynArts', 'FORM'\n"
                                "Example: ['FeynCalc']"
                            ),
                        },
                    },
                    "required": ["code"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_mathematica_packages",
                "description": "List available Mathematica physics packages with descriptions.",
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },
    ]

