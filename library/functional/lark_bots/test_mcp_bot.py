from typing import Dict, Any, List, Optional
import traceback

from ...fundamental.lark_tools import ParallelThreadLarkBot
from ...fundamental.function_call_tools import mathematica_tool
from pywheels.llm_tools.get_answer import get_answer_async, load_api_keys_async

__all__ = [
    "TestMCPBot",
]


test_mcp_prompt_template = """
# 角色
你是一个智能助手，具备强大的数学计算能力。你可以进行日常对话，也可以使用 Mathematica 等工具解决复杂数学问题。

# 用户消息
{text}

# 可用工具
你可以根据需要使用以下工具：

**Mathematica 工具**（用于数学计算，功能强大）:
- evaluate_mathematica: 执行 Mathematica 代码，适合符号计算、方程求解、微积分、高能物理计算、矩阵运算等
- evaluate_batch: 批量执行多个 Mathematica 表达式，适合多步骤计算
- get_package_info: 查询 Mathematica 包（如 FeynCalc）的信息和用法

# 工作流程
1. **理解用户意图**: 判断用户是想聊天还是需要数学计算
2. **选择合适方式**:
   - 如果是简单问候、闲聊 → 直接友好回复，不需要调用工具
   - 如果涉及数学计算、公式推导 → 选择合适的工具
3. **使用工具时**: 清晰说明计算过程和结果

# 工具选择建议
- 符号计算（积分、求导、因式分解）→ Mathematica
- 方程求解（代数方程、微分方程）→ Mathematica
- 高精度数值计算 → Mathematica
- 高能物理计算（使用 FeynCalc 包）→ Mathematica
- 多步骤计算 → Mathematica batch

# 示例

**用户**: 你好
**你**: 你好！我是数学计算助手，可以帮你解决各种数学问题，包括符号计算、方程求解、高能物理计算等。有什么我可以帮助你的吗？

**用户**: 计算 ∫x²sin(x)dx
**你**: 我来用 Mathematica 计算这个积分。
[调用 evaluate_mathematica 工具]
结果是: -x²cos(x) + 2xsin(x) + 2cos(x) + C

**用户**: 今天天气怎么样？
**你**: 抱歉，我是数学计算助手，主要负责数学和物理计算问题。关于天气信息，建议你查看天气应用或网站哦！

# 注意事项
- 对于非数学问题，礼貌地说明你的专长，不要随意调用工具
- 使用工具前，简单说明你要做什么
- 计算结果要清晰易懂
- Mathematica 语法：函数首字母大写，如 Integrate, Solve, D 等
"""


class TestMCPBot(ParallelThreadLarkBot):
    """
    测试 MCP (Model Context Protocol) 集成的机器人

    使用 pywheels get_answer_async + mathematica_tool 进行 MCP 工具调用。
    不再需要 MCPOpenAISession 包装器，直接使用 mathematica_tool。
    """

    def __init__(
        self,
        lark_bot_name: str,
        model_name: str = "Deepseek-V3",
        mcp_server_name: str = "mathematica",
        mcp_config_path: str = "mcp_servers_config.json",
        api_keys_path: str = "api_keys.json",
        worker_timeout: float = 600.0,
        context_cache_size: int = 1024,
        max_workers: Optional[int] = None,
    )-> None:

        super().__init__(
            lark_bot_name = lark_bot_name,
            worker_timeout = worker_timeout,
            context_cache_size = context_cache_size,
            max_workers = max_workers,
        )

        # 模型和 MCP 配置
        self.model_name = model_name
        self.mcp_server_name = mcp_server_name
        self.mcp_config_path = mcp_config_path
        self.api_keys_path = api_keys_path

        # 标记 API keys 是否已加载
        self._api_keys_loaded = False


    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        """
        判断是否应该处理此消息

        处理策略：处理所有消息，让 AI 自己决定是否调用工具
        """
        try:
            text: str = parsed_message.get("text", "")
            chat_type: str = parsed_message.get("chat_type", "")

            # 调试日志
            print(f" -> [TestMCPBot Filter] 收到消息")
            print(f"    聊天类型: {chat_type}")
            print(f"    文本: {text[:50]}..." if len(text) > 50 else f"    文本: {text}")

            # 处理所有消息，让 AI 决定如何响应
            print(f" -> [TestMCPBot Filter] 消息已接受，转交给 Worker")
            return True

        except Exception as e:
            print(f" -> [TestMCPBot Filter] should_process 异常: {e}")
            import traceback
            traceback.print_exc()
            return False


    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:
        """
        初始化会话上下文

        对于测试机器人，我们不需要保存复杂的历史记录
        """
        return {}


    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        """
        处理消息的核心逻辑

        1. 提取消息内容（文本和图片）
        2. 使用 get_answer_async + mathematica_tool 调用 MCP 工具
        3. 返回计算结果
        """
        message_id: str = parsed_message["message_id"]
        response: str = ""

        try:
            text: str = parsed_message["text"]
            image_keys: List[str] = parsed_message["image_keys"]

            print(f" -> [TestMCPBot Worker] 收到任务: {text[:100]}...")

            # 确保 API keys 已加载
            if not self._api_keys_loaded:
                print(f" -> [TestMCPBot Worker] 正在加载 API keys...")
                await load_api_keys_async(self.api_keys_path)
                self._api_keys_loaded = True

            # 构建提示词
            prompt = test_mcp_prompt_template.format(text=text)

            # 使用 pywheels get_answer_async + mathematica_tool
            print(f" -> [TestMCPBot Worker] 正在调用 get_answer_async 与 Mathematica MCP 工具...")

            response = await get_answer_async(
                prompt=prompt,
                model=self.model_name,
                tools=[
                    mathematica_tool(
                        timeout=60,
                        verbose=True,
                        mcp_server_name=self.mcp_server_name,
                        mcp_config_path=self.mcp_config_path,
                    )
                ],
                tool_use_trial_num=10,
            )

            print(f" -> [TestMCPBot Worker] 获得 AI 回答，准备发送回复")

        except Exception as error:
            print(f" -> [TestMCPBot Worker] 任务执行失败: {error}\n调用栈：\n{traceback.format_exc()}")
            response = (
                f"抱歉，执行过程中遇到了错误：\n\n"
                f"```\n{error}\n```\n\n"
                f"这可能是因为：\n"
                f"1. MCP 服务器连接失败（请检查 mcp_servers_config.json 配置）\n"
                f"2. API 调用失败（请检查 api_keys.json 配置）\n"
                f"3. 工具调用超时（计算可能过于复杂）\n"
                f"4. 代码执行出错（请检查语法）\n\n"
                f"请检查配置和网络连接，然后重试。"
            )

        # 发送回复到飞书
        reply_message_result = await self.reply_message_async(
            response = response,
            message_id = message_id,
            reply_in_thread = True,  # 在话题中回复
        )

        if reply_message_result.success():
            print(" -> [TestMCPBot Worker] 已成功发送回复")
        else:
            print(
                f" -> [TestMCPBot Worker] 回复发送失败: "
                f"{reply_message_result.code}, {reply_message_result.msg}"
            )

        return context
