"""
MCP HTTP 客户端模块

提供基于 fastmcp 的 HTTP 客户端封装，用于连接和调用远程 MCP 服务器。
该模块主要用于 Mathematica MCP 服务器的连接和工具调用。
"""

import json
from typing import Dict, Any, List, Optional
from contextlib import asynccontextmanager

from fastmcp import Client
from fastmcp.client.transports import StreamableHttpTransport

from .mcp_config import MCPServerConfig


__all__ = [
    "MCPHTTPClient",
    "create_mcp_client",
    "convert_mcp_tool_to_openai",
]


class MCPHTTPClient:
    """
    MCP HTTP 客户端封装类

    用于连接远程 MCP 服务器并调用工具。
    支持异步上下文管理器，自动处理连接生命周期。
    """

    def __init__(
        self,
        config: MCPServerConfig,
        verbose: bool = False,
    ):
        """
        初始化 MCP HTTP 客户端

        Args:
            config: MCP 服务器配置
            verbose: 是否打印详细日志
        """
        self.config = config
        self.verbose = verbose

        # 配置 HTTP 传输层（使用 Bearer Token 认证）
        headers = {}
        if config.auth_token:
            headers["Authorization"] = f"Bearer {config.auth_token}"

        self.transport = StreamableHttpTransport(
            url=config.url,
            headers=headers
        )

        # 创建 fastmcp 客户端
        self.client = Client(self.transport)
        self._session = None

        if verbose:
            print(f"✅ [MCPHTTPClient] 客户端初始化成功")
            print(f"   服务器 URL: {config.url}")
            print(f"   超时设置: {config.timeout}s")

    async def __aenter__(self):
        """进入异步上下文管理器"""
        self._session = await self.client.__aenter__()
        if self.verbose:
            print(f"🔌 [MCPHTTPClient] 已连接到 MCP 服务器")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """退出异步上下文管理器"""
        result = await self.client.__aexit__(exc_type, exc_val, exc_tb)
        if self.verbose:
            print(f"🔌 [MCPHTTPClient] 已断开 MCP 服务器连接")
        return result

    async def list_tools(self) -> List[Any]:
        """
        列出服务器提供的所有工具

        Returns:
            工具列表

        Raises:
            RuntimeError: 客户端未连接
        """
        if self.verbose:
            print(f"🔧 [MCPHTTPClient] 正在获取工具列表...")

        tools = await self.client.list_tools()

        if self.verbose:
            print(f"   找到 {len(tools)} 个可用工具")
            for tool in tools:
                print(f"   - {tool.name}")

        return tools

    async def call_tool(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        timeout: Optional[float] = None,
    ) -> Any:
        """
        调用 MCP 服务器上的工具

        Args:
            tool_name: 工具名称
            arguments: 工具参数字典
            timeout: 超时时间（秒），如果为 None 则使用配置的默认值

        Returns:
            工具调用结果

        Raises:
            RuntimeError: 客户端未连接
            Exception: 工具调用失败
        """
        if self.verbose:
            print(f"\n🛠️  [MCPHTTPClient] 调用工具: {tool_name}")
            print(f"   参数: {json.dumps(arguments, ensure_ascii=False, indent=2)}")

        # 使用配置的超时时间（如果未指定）
        if timeout is None:
            timeout = self.config.timeout

        # 调用工具
        result = await self.client.call_tool(
            name=tool_name,
            arguments=arguments,
            timeout=timeout
        )

        if self.verbose:
            print(f"   ✅ 工具调用成功")

        return result

    def parse_response(self, mcp_result: Any) -> str:
        """
        解析 MCP 工具调用结果

        Args:
            mcp_result: MCP 工具返回的结果对象

        Returns:
            解析后的字符串结果
        """
        # 提取结果内容
        output = ""

        if hasattr(mcp_result, 'content'):
            for content_item in mcp_result.content:
                if hasattr(content_item, 'text'):
                    output += content_item.text

        return output


def create_mcp_client(
    url: str,
    auth_token: Optional[str] = None,
    timeout: float = 120.0,
    verbose: bool = False,
) -> MCPHTTPClient:
    """
    便捷函数：创建 MCP HTTP 客户端

    Args:
        url: MCP 服务器 URL
        auth_token: 认证令牌（可选）
        timeout: 超时时间（秒）
        verbose: 是否打印详细日志

    Returns:
        MCP HTTP 客户端实例
    """
    config = MCPServerConfig(
        url=url,
        auth_token=auth_token,
        timeout=timeout
    )

    return MCPHTTPClient(config=config, verbose=verbose)


def convert_mcp_tool_to_openai(mcp_tool: dict) -> dict:
    """
    将 MCP 工具定义转换为 OpenAI function calling 格式

    Args:
        mcp_tool: MCP 工具定义（包含 name, description, inputSchema）

    Returns:
        OpenAI function calling 格式的工具定义
    """
    return {
        "type": "function",
        "function": {
            "name": mcp_tool["name"],
            "description": mcp_tool.get("description", ""),
            "parameters": mcp_tool.get("inputSchema", {
                "type": "object",
                "properties": {},
                "required": []
            })
        }
    }
