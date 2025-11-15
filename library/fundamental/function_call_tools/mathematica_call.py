import httpx
import functools
import traceback
from typing import Any, Dict, Callable, List, Optional
from ..json_tools import load_from_json


__all__ = [
    "mathematica_evaluate_tool",
    "mathematica_batch_tool",
    "mathematica_package_info_tool",
]


class MathematicaMCPClient:
    """
    Mathematica MCP 服务器客户端 (FastMCP + HTTP 传输)

    该客户端连接到基于 FastMCP 的 Mathematica 服务器，
    使用 HTTP POST 调用服务器提供的工具。
    """

    def __init__(
        self,
        url: str,
        api_key: str,
        timeout: float = 60.0,
    )-> None:
        """
        初始化 MCP 客户端

        :param url: MCP 服务器 URL (例如: http://host:port/mcp)
        :param api_key: API 密钥 (用于 Bearer token 认证)
        :param timeout: HTTP 请求超时时间（秒）
        """
        self.base_url = url.rstrip('/')
        self.api_key = api_key
        self.timeout = timeout

    def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    )-> str:
        """
        调用 FastMCP 服务器上的工具

        FastMCP 使用 HTTP POST 到 /call-tool 端点，而非 JSON-RPC

        :param tool_name: 工具名称
        :param arguments: 工具参数字典
        :return: 工具执行结果（字符串）
        """
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            }

            # FastMCP 工具调用端点
            endpoint = f"{self.base_url}/call-tool"

            # FastMCP 请求格式
            payload = {
                "name": tool_name,
                "arguments": arguments,
            }

            # 发送 HTTP POST 请求
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

            # FastMCP 返回格式: {"content": [{"type": "text", "text": "..."}], ...}
            # 或直接返回结果对象
            if isinstance(result, dict):
                # 检查是否有错误
                if "error" in result:
                    error_msg = result.get("error", "未知错误")
                    return f"MCP 服务器返回错误: {error_msg}"

                # 检查 success 字段
                if "success" in result and not result["success"]:
                    error_msg = result.get("error", "操作失败")
                    return f"执行失败: {error_msg}"

                # 提取结果内容
                # 对于 evaluate_mathematica，返回格式包含 output 字段
                if "output" in result:
                    output_parts = [f"结果: {result['output']}"]

                    # 添加执行时间
                    if "execution_time" in result:
                        output_parts.append(f"执行时间: {result['execution_time']}秒")

                    # 添加消息（警告/错误）
                    if "messages" in result and result["messages"]:
                        messages_str = "\n".join([
                            f"[{msg.get('tag', 'INFO')}] {msg.get('text', '')}"
                            for msg in result["messages"]
                        ])
                        output_parts.append(f"消息:\n{messages_str}")

                    # 添加语法警告
                    if "syntax_warnings" in result and result["syntax_warnings"]:
                        warnings_str = "\n".join(result["syntax_warnings"])
                        output_parts.append(f"语法警告:\n{warnings_str}")

                    return "\n\n".join(output_parts)

                # 对于其他工具，尝试提取有用信息
                if "content" in result and isinstance(result["content"], list):
                    text_parts = []
                    for item in result["content"]:
                        if isinstance(item, dict) and item.get("type") == "text":
                            text_parts.append(item.get("text", ""))
                    if text_parts:
                        return "\n".join(text_parts)

                # 返回整个结果的字符串表示
                return str(result)

            # 如果返回的不是字典，直接转换为字符串
            return str(result)

        except httpx.TimeoutException:
            return f"MCP 请求超时（超过 {self.timeout} 秒）。服务器可能正在处理复杂计算。"
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            if status_code == 401:
                return "MCP 认证失败：API 密钥无效或已过期。请检查 mcp_servers_config.json 中的 auth_token。"
            elif status_code == 404:
                return f"MCP 端点未找到：{e.request.url}。请检查服务器 URL 配置。"
            else:
                error_text = e.response.text[:500]  # 限制错误消息长度
                return f"MCP HTTP 错误 [{status_code}]: {error_text}"
        except httpx.ConnectError:
            return f"无法连接到 MCP 服务器 ({self.base_url})。请检查：\n1. 服务器是否运行\n2. URL 是否正确\n3. 网络连接是否正常"
        except Exception as e:
            return f"调用 Mathematica MCP 服务器时出错: {e}\n{traceback.format_exc()}"


# ==================== Tool 1: evaluate_mathematica ====================

def _execute_mathematica(
    code: str,
    mcp_client: MathematicaMCPClient,
    packages: Optional[List[str]],
    timeout_seconds: Optional[int],
    verbose: bool,
)-> str:
    """
    执行 Mathematica 代码

    :param code: Mathematica 代码字符串
    :param mcp_client: MCP 客户端实例
    :param packages: 要加载的包列表
    :param timeout_seconds: 超时时间（秒）
    :param verbose: 是否打印详细信息
    :return: 执行结果
    """
    output: str = ""

    try:
        # 构建参数字典（按照服务端 evaluate_mathematica 的参数格式）
        arguments = {"code": code}

        if packages is not None and len(packages) > 0:
            arguments["packages"] = packages

        if timeout_seconds is not None:
            arguments["timeout_seconds"] = timeout_seconds

        # 调用 MCP 服务器的 evaluate_mathematica 工具
        output = mcp_client.call_tool(
            tool_name="evaluate_mathematica",
            arguments=arguments
        )

    except Exception as e:
        output = f"执行 Mathematica 代码时出错: {e}\n{traceback.format_exc()}"

    if verbose:
        print(f"--- [Mathematica Evaluate Tool Executed] ---")
        print(f"Code: {code}")
        if packages:
            print(f"Packages: {packages}")
        if timeout_seconds:
            print(f"Timeout: {timeout_seconds}s")
        print(f"Result:\n{output}")
        print(f"--------------------------------------------")

    return output


def mathematica_evaluate_tool(
    timeout: float = 60.0,
    verbose: bool = False,
    mcp_config_path: str = "mcp_servers_config.json",
    server_name: str = "mathematica",
)-> Dict[str, Any]:
    """
    创建 Mathematica 代码执行工具

    :param timeout: HTTP 请求超时时间（秒）
    :param verbose: 是否打印详细执行信息
    :param mcp_config_path: MCP 配置文件路径
    :param server_name: MCP 服务器名称
    :return: 工具定义字典
    """
    # 从配置文件加载 MCP 服务器配置
    mcp_config = load_from_json(mcp_config_path)
    server_config = mcp_config["servers"][server_name]

    # 创建 MCP 客户端
    mcp_client = MathematicaMCPClient(
        url=server_config["url"],
        api_key=server_config["auth_token"],
        timeout=server_config.get("timeout", timeout),
    )

    # 绑定参数到执行函数
    bound_implementation: Callable[..., str] = functools.partial(
        _execute_mathematica,
        mcp_client=mcp_client,
        verbose=verbose,
    )

    tool_definition: Dict[str, Any] = {
        "name": "evaluate_mathematica",
        "description": (
            "执行 Mathematica (Wolfram Language) 代码并返回计算结果。\n"
            "适用于符号计算、高级数学运算、微分方程求解、矩阵运算、高能物理计算等。\n"
            "支持 FeynCalc 等高能物理专用包。\n\n"
            "重要约束 (Important Notes):\n"
            f"1. **超时**: 代码执行有超时限制（默认 {timeout} 秒，可通过 timeout_seconds 参数调整，最大 300 秒）。\n"
            "2. **语法**: 必须使用正确的 Wolfram Language 语法。\n"
            "3. **输出**: 代码执行结果会自动返回，最后一个表达式的值会被输出。\n"
            "4. **包加载**: 可通过 packages 参数加载特定的 Mathematica 包（如 ['FeynCalc']）。\n"
            "5. **符号计算**: 支持符号代数、微积分、微分方程求解、因式分解等。\n"
            "6. **数值计算**: 支持高精度数值计算、数值优化、数值积分等。\n"
            "7. **独立执行**: 每次调用都是独立的内核会话，变量不会在调用间保留。\n"
            "8. **错误处理**: Mathematica 不支持 try/catch 语法，请使用 Check[]/Catch[]/Throw[]。\n"
            "9. **Unicode 支持**: 支持中文注释和 Unicode 字符（如希腊字母 μ, ν 等）。\n\n"
            "示例用法:\n"
            "- 符号积分: 'Integrate[x^2 Sin[x], x]'\n"
            "- 求解方程: 'Solve[x^2 + 5x + 6 == 0, x]'\n"
            "- 求导: 'D[Sin[x^2], x]'\n"
            "- 高精度计算: 'N[Pi, 100]'\n"
            "- 因式分解: 'Factor[x^4 - 1]'\n"
            "- 微分方程: 'DSolve[y''[x] + y[x] == 0, y[x], x]'\n"
            "- FeynCalc 示例: 'DiracSimplify[GA[\\[Mu], \\[Nu], \\[Mu]]]' (需要 packages=['FeynCalc'])"
        ),
        "parameters": {
            "code": {
                "type": "string",
                "description": (
                    "要执行的 Mathematica 代码字符串。\n"
                    "支持 InputForm 语法和 Unicode 字符。\n"
                    "可以包含中文注释，例如: '(* 定义变量 *) x = 1'"
                ),
                "required": True,
            },
            "packages": {
                "type": "array",
                "description": (
                    "要加载的 Mathematica 包名称列表（可选）。\n"
                    "例如: [\"FeynCalc\"] 用于高能物理计算\n"
                    "服务器会在执行代码前自动加载这些包"
                ),
                "required": False,
            },
            "timeout_seconds": {
                "type": "integer",
                "description": (
                    "代码执行超时时间（秒，可选）。\n"
                    "默认 60 秒，最大 300 秒。\n"
                    "超时后服务器会自动中止计算并返回 $Aborted"
                ),
                "required": False,
            },
        },
        "implementation": bound_implementation,
    }

    return tool_definition


# ==================== Tool 2: evaluate_batch ====================

def _execute_batch(
    expressions: List[str],
    mcp_client: MathematicaMCPClient,
    packages: Optional[List[str]],
    timeout_seconds: Optional[int],
    verbose: bool,
)-> str:
    """
    批量执行多个 Mathematica 表达式

    注意：服务端 evaluate_batch 期望的格式是 List[Dict[str, Any]]
    我们需要将简单的字符串列表转换为字典列表

    :param expressions: Mathematica 表达式字符串列表
    :param mcp_client: MCP 客户端实例
    :param packages: 要加载的包列表（仅应用于第一个表达式）
    :param timeout_seconds: 每个表达式的超时时间
    :param verbose: 是否打印详细信息
    :return: 执行结果
    """
    output: str = ""

    try:
        # 将字符串列表转换为服务端期望的格式: List[Dict]
        formatted_expressions = []
        for idx, expr in enumerate(expressions):
            expr_dict = {"code": expr}

            # 只在第一个表达式添加 packages
            if idx == 0 and packages:
                expr_dict["packages"] = packages

            # 添加超时设置
            if timeout_seconds is not None:
                expr_dict["timeout_seconds"] = timeout_seconds

            formatted_expressions.append(expr_dict)

        # 调用 MCP 服务器的 evaluate_batch 工具
        result = mcp_client.call_tool(
            tool_name="evaluate_batch",
            arguments={"expressions": formatted_expressions}
        )

        output = result

    except Exception as e:
        output = f"批量执行 Mathematica 表达式时出错: {e}\n{traceback.format_exc()}"

    if verbose:
        print(f"--- [Mathematica Batch Tool Executed] ---")
        print(f"Expressions ({len(expressions)} items):")
        for i, expr in enumerate(expressions, 1):
            print(f"  [{i}] {expr}")
        print(f"Result:\n{output}")
        print(f"-----------------------------------------")

    return output


def mathematica_batch_tool(
    timeout: float = 90.0,
    verbose: bool = False,
    mcp_config_path: str = "mcp_servers_config.json",
    server_name: str = "mathematica",
)-> Dict[str, Any]:
    """
    创建 Mathematica 批量执行工具

    :param timeout: HTTP 请求超时时间（秒）
    :param verbose: 是否打印详细执行信息
    :param mcp_config_path: MCP 配置文件路径
    :param server_name: MCP 服务器名称
    :return: 工具定义字典
    """
    # 从配置文件加载 MCP 服务器配置
    mcp_config = load_from_json(mcp_config_path)
    server_config = mcp_config["servers"][server_name]

    # 创建 MCP 客户端
    mcp_client = MathematicaMCPClient(
        url=server_config["url"],
        api_key=server_config["auth_token"],
        timeout=server_config.get("timeout", timeout),
    )

    # 绑定参数到执行函数
    bound_implementation: Callable[..., str] = functools.partial(
        _execute_batch,
        mcp_client=mcp_client,
        verbose=verbose,
    )

    tool_definition: Dict[str, Any] = {
        "name": "evaluate_mathematica_batch",
        "description": (
            "批量执行多个 Mathematica 表达式，在同一个会话中按顺序依次执行。\n"
            "适用于需要多步计算的场景，后续表达式可以引用前面定义的变量和函数。\n\n"
            "重要特性:\n"
            "1. **共享会话**: 所有表达式在同一个 Mathematica 内核会话中执行\n"
            "2. **顺序执行**: 表达式按列表顺序依次执行\n"
            "3. **状态保持**: 前面表达式定义的变量可在后续表达式中使用\n"
            f"4. **超时**: 每个表达式有独立的超时限制（默认 {timeout} 秒）\n\n"
            "适用场景:\n"
            "- 多步骤计算（定义变量 → 计算 → 输出结果）\n"
            "- 复杂的数学推导（需要多个中间步骤）\n"
            "- 需要复用前面计算结果的场景\n\n"
            "示例用法:\n"
            "expressions: [\n"
            "  \"a = 5\",\n"
            "  \"b = a^2\",\n"
            "  \"c = b + 10\",\n"
            "  \"c\"\n"
            "]\n"
            "输出: [5, 25, 35, 35]"
        ),
        "parameters": {
            "expressions": {
                "type": "array",
                "description": (
                    "要执行的 Mathematica 表达式字符串列表。\n"
                    "每个字符串都是一个独立的 Mathematica 表达式。\n"
                    "表达式会按顺序在同一个会话中执行。"
                ),
                "required": True,
            },
            "packages": {
                "type": "array",
                "description": (
                    "要加载的 Mathematica 包名称列表（可选）。\n"
                    "这些包会在执行第一个表达式前加载。"
                ),
                "required": False,
            },
            "timeout_seconds": {
                "type": "integer",
                "description": "每个表达式的执行超时时间（秒，可选）。默认 60 秒，最大 300 秒。",
                "required": False,
            },
        },
        "implementation": bound_implementation,
    }

    return tool_definition


# ==================== Tool 3: get_package_info ====================

def _get_package_info(
    package_name: str,
    mcp_client: MathematicaMCPClient,
    verbose: bool,
)-> str:
    """
    获取 Mathematica 包的详细信息

    :param package_name: 包名称
    :param mcp_client: MCP 客户端实例
    :param verbose: 是否打印详细信息
    :return: 包信息
    """
    output: str = ""

    try:
        # 调用 MCP 服务器的 get_package_info 工具
        result = mcp_client.call_tool(
            tool_name="get_package_info",
            arguments={"package_name": package_name}
        )

        output = result

    except Exception as e:
        output = f"获取包信息时出错: {e}\n{traceback.format_exc()}"

    if verbose:
        print(f"--- [Mathematica Package Info Tool Executed] ---")
        print(f"Package: {package_name}")
        print(f"Result:\n{output}")
        print(f"------------------------------------------------")

    return output


def mathematica_package_info_tool(
    timeout: float = 30.0,
    verbose: bool = False,
    mcp_config_path: str = "mcp_servers_config.json",
    server_name: str = "mathematica",
)-> Dict[str, Any]:
    """
    创建 Mathematica 包信息查询工具

    :param timeout: HTTP 请求超时时间（秒）
    :param verbose: 是否打印详细执行信息
    :param mcp_config_path: MCP 配置文件路径
    :param server_name: MCP 服务器名称
    :return: 工具定义字典
    """
    # 从配置文件加载 MCP 服务器配置
    mcp_config = load_from_json(mcp_config_path)
    server_config = mcp_config["servers"][server_name]

    # 创建 MCP 客户端
    mcp_client = MathematicaMCPClient(
        url=server_config["url"],
        api_key=server_config["auth_token"],
        timeout=server_config.get("timeout", timeout),
    )

    # 绑定参数到执行函数
    bound_implementation: Callable[..., str] = functools.partial(
        _get_package_info,
        mcp_client=mcp_client,
        verbose=verbose,
    )

    tool_definition: Dict[str, Any] = {
        "name": "get_mathematica_package_info",
        "description": (
            "获取指定 Mathematica 包的详细信息。\n"
            "包括包的功能描述、主要函数列表、使用说明、文档链接等。\n\n"
            "当前服务器支持的包:\n"
            "- FeynCalc: 高能物理和量子场论计算专用包\n"
            "  支持 Dirac 代数、Lorentz 张量、费曼图计算、单圈积分等\n\n"
            "适用场景:\n"
            "1. 想要了解某个包提供了哪些功能\n"
            "2. 查看包的使用文档和常用函数\n"
            "3. 确认包是否可用以及如何在代码中使用\n\n"
            "示例用法:\n"
            "package_name: \"FeynCalc\"\n"
            "返回: FeynCalc 的详细信息，包括版本、功能、常用函数列表等"
        ),
        "parameters": {
            "package_name": {
                "type": "string",
                "description": (
                    "Mathematica 包的名称。\n"
                    "支持的包: FeynCalc (高能物理)\n"
                    "如果包不存在，会返回可用包的列表"
                ),
                "required": True,
            },
        },
        "implementation": bound_implementation,
    }

    return tool_definition
