"""
MCP Pywheels 集成模块

提供使用 pywheels get_answer_async 调用 MCP 工具的高层封装。
对齐 mcp_openai_integration.py 的实现，将 OpenAI SDK 替换为 pywheels。
"""

from typing import Dict, Any, List, Optional

from pywheels.llm_tools.get_answer import get_answer_async, load_api_keys_async

from .mcp_http_client import MCPHTTPClient
from .mcp_config import get_server_config


__all__ = [
    "convert_mcp_tool_to_pywheels",
    "MCPPywheelsSession",
]


def convert_mcp_tool_to_pywheels(mcp_tool: Any, mcp_client: MCPHTTPClient) -> Dict[str, Any]:
    """
    将 MCP 工具定义转换为 pywheels function calling 格式

    Args:
        mcp_tool: MCP 工具对象
        mcp_client: MCP HTTP 客户端实例

    Returns:
        pywheels function calling 格式的工具定义
    """
    # 创建工具实现函数（调用 MCP 服务器）
    async def call_mcp_tool(**kwargs) -> str:
        result = await mcp_client.call_tool(mcp_tool.name, kwargs)
        return mcp_client.parse_response(result)

    # 转换参数格式
    parameters = {}
    if hasattr(mcp_tool, 'inputSchema') and mcp_tool.inputSchema:
        props = mcp_tool.inputSchema.get("properties", {})
        required = mcp_tool.inputSchema.get("required", [])

        for param_name, param_info in props.items():
            # 确保 description 不为空
            description = param_info.get("description", "")
            if not description:
                description = f"Parameter {param_name}"

            param_type = param_info.get("type", "string")

            param_def = {
                "type": param_type,
                "description": description,
                "required": param_name in required,
            }

            # 如果是数组类型，确保包含 items 字段
            if param_type == "array":
                items = param_info.get("items")
                if items:
                    param_def["items"] = items
                else:
                    # 如果没有 items 字段，添加默认值
                    param_def["items"] = {"type": "string"}

            parameters[param_name] = param_def

    return {
        "name": mcp_tool.name,
        "description": mcp_tool.description or f"Tool {mcp_tool.name}",
        "parameters": parameters,
        "implementation": call_mcp_tool,
    }


class MCPPywheelsSession:
    """
    MCP Pywheels 会话管理器

    封装了使用 pywheels get_answer_async 调用 MCP 工具的完整流程：
    1. 从 api_keys.json 加载 API 配置
    2. 连接到 MCP 服务器并获取工具列表
    3. 将 MCP 工具转换为 pywheels 格式
    4. 使用 get_answer_async 进行对话，自动处理工具调用

    对齐 MCPOpenAISession 的实现，将 OpenAI SDK 替换为 pywheels。
    """

    def __init__(
        self,
        model_name: str,
        mcp_server_name: str = "mathematica",
        mcp_config_path: str = "mcp_servers_config.json",
        max_tool_iterations: int = 5,
        verbose: bool = False,
    ):
        """
        初始化 MCP Pywheels 会话

        Args:
            model_name: 模型名称（在 api_keys.json 中定义，如 "Gemini-2.5-Flash-for-HET-AGI"）
            mcp_server_name: MCP 服务器名称
            mcp_config_path: MCP 配置文件路径
            max_tool_iterations: 最大工具调用迭代次数（默认 5 次）
            verbose: 是否打印详细日志
        """
        self.model_name = model_name
        self.mcp_server_name = mcp_server_name
        self.mcp_config_path = mcp_config_path
        self.max_tool_iterations = max_tool_iterations
        self.verbose = verbose

        if self.verbose:
            print(f"[MCPPywheelsSession] 使用模型: {model_name}")
            print(f"[MCPPywheelsSession] MCP 服务器: {mcp_server_name}")

        # MCP 客户端（延迟初始化）
        self.mcp_client: Optional[MCPHTTPClient] = None
        self.pywheels_tools: List[Dict[str, Any]] = []

    async def __aenter__(self):
        """进入异步上下文管理器"""
        # 加载 API 配置
        await load_api_keys_async("api_keys.json")

        # 初始化 MCP 客户端
        config = get_server_config(self.mcp_server_name, self.mcp_config_path)
        self.mcp_client = MCPHTTPClient(config, verbose=self.verbose)

        # 连接到 MCP 服务器
        await self.mcp_client.__aenter__()

        # 获取 MCP 工具列表
        mcp_tools = await self.mcp_client.list_tools()

        # 转换为 pywheels 格式
        self.pywheels_tools = [convert_mcp_tool_to_pywheels(tool, self.mcp_client) for tool in mcp_tools]

        if self.verbose:
            print(f"[MCPPywheelsSession] 已连接到 MCP 服务器，获取 {len(self.pywheels_tools)} 个工具")

        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文管理器"""
        if self.mcp_client:
            await self.mcp_client.__aexit__(exc_type, exc_val, exc_tb)

    async def get_answer(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
    ) -> str:
        """
        使用 pywheels get_answer_async 和 MCP 工具获取回答

        Args:
            prompt: 用户问题
            system_prompt: 系统提示词（可选）

        Returns:
            AI 的最终回答

        注意：
            pywheels 的 get_answer_async 内部已经处理了多轮工具调用循环，
            通过 tool_use_trial_num 参数控制最大迭代次数。
            AI 会自己决定何时调用工具，何时返回最终答案。
        """
        if self.verbose:
            print(f"[MCPPywheelsSession] 开始处理问题...")

        # 使用 pywheels get_answer_async
        # pywheels 内部会自动处理工具调用循环，无需手动迭代
        response = await get_answer_async(
            prompt=prompt,
            model=self.model_name,
            system_prompt=system_prompt,
            tools=self.pywheels_tools,
            tool_use_trial_num=self.max_tool_iterations,
        )

        if self.verbose:
            print(f"[MCPPywheelsSession] 获取到最终回答")

        return response
