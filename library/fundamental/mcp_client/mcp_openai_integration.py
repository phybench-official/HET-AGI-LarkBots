"""
MCP OpenAI 集成模块

提供使用 OpenAI SDK 调用 MCP 工具的高层封装。
基于 test_mcp_tool_calling.py 的实现，适配到 Lark Bot 中使用。
"""

import json
from typing import Dict, Any, List, Optional
from openai import AsyncOpenAI

from .mcp_http_client import MCPHTTPClient
from .mcp_config import get_server_config
from ..json_tools import load_from_json


__all__ = [
    "convert_mcp_tool_to_openai",
    "MCPOpenAISession",
    "get_model_config",
]


def get_model_config(model_name: str) -> Dict[str, str]:
    """
    从 api_keys.json 加载模型配置

    Args:
        model_name: 模型名称（如 "GPT-5", "Gemini-2.5-Flash" 等）

    Returns:
        包含 api_key, base_url, model 的字典

    Raises:
        KeyError: 如果模型名称不存在
        FileNotFoundError: 如果 api_keys.json 文件不存在
    """
    api_keys_dict = load_from_json("api_keys.json")

    if model_name not in api_keys_dict:
        raise KeyError(
            f"模型 '{model_name}' 不存在于 api_keys.json 中。\n"
            f"可用的模型: {list(api_keys_dict.keys())}"
        )

    # 返回第一个配置（通常每个模型只有一个配置）
    config = api_keys_dict[model_name][0]

    return {
        "api_key": config["api_key"],
        "base_url": config["base_url"],
        "model": config["model"],
    }


def convert_mcp_tool_to_openai(mcp_tool: Any) -> Dict[str, Any]:
    """
    将 MCP 工具定义转换为 OpenAI function calling 格式

    Args:
        mcp_tool: MCP 工具对象

    Returns:
        OpenAI function calling 格式的工具定义
    """
    return {
        "type": "function",
        "function": {
            "name": mcp_tool.name,
            "description": mcp_tool.description or "",
            "parameters": mcp_tool.inputSchema if hasattr(mcp_tool, 'inputSchema') else {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }


class MCPOpenAISession:
    """
    MCP OpenAI 会话管理器

    封装了使用 OpenAI SDK 调用 MCP 工具的完整流程：
    1. 从 api_keys.json 加载 API 配置
    2. 连接到 MCP 服务器并获取工具列表
    3. 将 MCP 工具转换为 OpenAI 格式
    4. 使用 OpenAI SDK 进行对话，支持多轮工具调用
    5. 自动处理工具调用和结果返回
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
        初始化 MCP OpenAI 会话

        Args:
            model_name: 模型名称（在 api_keys.json 中定义，如 "GPT-5"）
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

        # 从 api_keys.json 加载模型配置
        model_config = get_model_config(model_name)
        self.openai_api_key = model_config["api_key"]
        self.openai_base_url = model_config["base_url"]
        self.openai_model = model_config["model"]

        if self.verbose:
            print(f"[MCPOpenAISession] 加载模型配置: {model_name}")
            print(f"[MCPOpenAISession] Base URL: {self.openai_base_url}")
            print(f"[MCPOpenAISession] Model: {self.openai_model}")

        # OpenAI 客户端
        self.openai_client = AsyncOpenAI(
            api_key=self.openai_api_key,
            base_url=self.openai_base_url,
        )

        # MCP 客户端（延迟初始化）
        self.mcp_client: Optional[MCPHTTPClient] = None
        self.openai_tools: List[Dict[str, Any]] = []

    async def __aenter__(self):
        """进入异步上下文管理器"""
        # 初始化 MCP 客户端
        config = get_server_config(self.mcp_server_name, self.mcp_config_path)
        self.mcp_client = MCPHTTPClient(config, verbose=self.verbose)

        # 连接到 MCP 服务器
        await self.mcp_client.__aenter__()

        # 获取 MCP 工具列表
        mcp_tools = await self.mcp_client.list_tools()

        # 转换为 OpenAI 格式
        self.openai_tools = [convert_mcp_tool_to_openai(tool) for tool in mcp_tools]

        if self.verbose:
            print(f"[MCPOpenAISession] 已连接到 MCP 服务器，获取 {len(self.openai_tools)} 个工具")

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
        使用 OpenAI SDK 和 MCP 工具获取回答

        Args:
            prompt: 用户问题
            system_prompt: 系统提示词（可选）

        Returns:
            AI 的最终回答

        注意：
            工具调用循环会一直进行，直到 AI 决定不再调用工具为止。
            max_tool_iterations 仅作为安全限制，防止无限循环。
        """
        # 构建消息列表
        messages = []

        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        messages.append({"role": "user", "content": prompt})

        # 工具调用循环 - 由 AI 决定何时停止
        iteration = 0

        while iteration < self.max_tool_iterations:
            iteration += 1

            if self.verbose:
                print(f"[MCPOpenAISession] 第 {iteration} 轮调用")

            # 调用 OpenAI API
            response = await self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=messages,
                tools=self.openai_tools,
                tool_choice="auto",
            )

            assistant_message = response.choices[0].message
            messages.append(assistant_message)

            # 检查是否有工具调用
            if not assistant_message.tool_calls:
                # AI 决定不再调用工具，返回最终答案
                if self.verbose:
                    print(f"[MCPOpenAISession] AI 完成回答")
                break

            # 处理工具调用
            if self.verbose:
                print(f"[MCPOpenAISession] AI 请求调用 {len(assistant_message.tool_calls)} 个工具")

            for tool_call in assistant_message.tool_calls:
                tool_name = tool_call.function.name
                tool_args = json.loads(tool_call.function.arguments)

                if self.verbose:
                    print(f"[MCPOpenAISession]   工具: {tool_name}")
                    print(f"[MCPOpenAISession]   参数: {json.dumps(tool_args, ensure_ascii=False)}")

                # 通过 MCP 客户端调用工具
                try:
                    mcp_result = await self.mcp_client.call_tool(tool_name, tool_args)
                    tool_output = self.mcp_client.parse_response(mcp_result)

                    if self.verbose:
                        print(f"[MCPOpenAISession]   ✓ 成功")

                except Exception as e:
                    tool_output = f"工具调用失败: {e}"
                    if self.verbose:
                        print(f"[MCPOpenAISession]   ✗ 失败: {e}")

                # 将工具结果添加到消息历史
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": tool_output,
                })

        # 返回最终结果
        final_response = messages[-1]

        if hasattr(final_response, 'content') and final_response.content:
            return final_response.content
        elif isinstance(final_response, dict) and final_response.get('content'):
            return final_response['content']
        else:
            # 如果最后一条消息是工具调用结果，再调用一次 API 获取总结
            if self.verbose:
                print("[MCPOpenAISession] 获取最终总结...")

            final_completion = await self.openai_client.chat.completions.create(
                model=self.openai_model,
                messages=messages,
            )
            return final_completion.choices[0].message.content
