from typing import Dict, Any, List, Optional
from collections import OrderedDict
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

    群聊规则：
    - 只有在话题顶层消息 @ 机器人时才会开始处理该话题
    - 话题内的后续消息会自动处理（无需再次 @）
    - 未被接受的话题中 @ 机器人会提示用户在顶层消息 @ 机器人
    """

    def __init__(
        self,
        config_path: str,
        image_cache_size: int = 128,
        model_name: str = "GPT-5",
        mcp_server_name: str = "mathematica",
        mcp_config_path: str = "mcp_servers_config.json",
        api_keys_path: str = "api_keys.json",
        worker_timeout: float = 600.0,
        context_cache_size: int = 1024,
        max_workers: Optional[int] = None,
    )-> None:

        super().__init__(
            config_path = config_path,
            image_cache_size = image_cache_size,
            worker_timeout = worker_timeout,
            context_cache_size = context_cache_size,
            max_workers = max_workers,
        )
        
        # start 动作的逻辑是会在子进程中再跑一个机器人
        # 这样可以暴露简洁的 API，把不同机器人隔离在不同进程中，防止底层库报错
        # 这背后依赖属性 _init_arguments
        # 所以子类如果签名改变，有义务自行维护 _init_arguments
        # 另外，由于会被运行两次，所以 __init__ 方法应是轻量级且幂等的
        self._init_arguments: Dict[str, Any] = {
            "config_path": config_path,
            "image_cache_size": image_cache_size,
            "model_name": model_name,
            "mcp_server_name": mcp_server_name,
            "mcp_config_path": mcp_config_path,
            "api_keys_path": api_keys_path,
            "worker_timeout": worker_timeout,
            "context_cache_size": context_cache_size,
            "max_workers": max_workers,
        }

        # 模型和 MCP 配置
        self.model_name = model_name
        self.mcp_server_name = mcp_server_name
        self.mcp_config_path = mcp_config_path
        self.api_keys_path = api_keys_path

        # 标记 API keys 是否已加载
        self._api_keys_loaded = False

        # 接受的话题缓存（用于群聊 @ 逻辑）
        self._acceptance_cache_size: int = context_cache_size
        self._acceptance_cache: OrderedDict[str, bool] = OrderedDict()


    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        """
        判断是否应该处理此消息

        群聊处理策略：
        1. 如果是顶层消息（is_thread_root=True）：
           - 必须 @ 机器人才会处理并加入接受缓存
           - 未 @ 的顶层消息会被忽略
        2. 如果是话题内消息（is_thread_root=False）：
           - 总是返回 True，交给 process_message_in_context 判断

        私聊处理策略：
        - 总是返回 True
        """
        chat_type: str = parsed_message.get("chat_type", "")
        is_thread_root: bool = parsed_message.get("is_thread_root", False)
        mentioned_me: bool = parsed_message.get("mentioned_me", False)
        message_id: str = parsed_message.get("message_id", "")

        # 群聊消息
        if chat_type == "group":
            # 顶层消息（话题根消息）
            if is_thread_root:
                # @了机器人，加入接受缓存并处理
                if mentioned_me:
                    thread_root_id: Optional[str] = parsed_message.get("thread_root_id")
                    assert thread_root_id is not None

                    print(f" -> [TestMCPBot Filter] 顶层消息 {message_id} 已接受（已 @），加入接受缓存")

                    self._acceptance_cache[thread_root_id] = True
                    self._acceptance_cache.move_to_end(thread_root_id)

                    # 缓存溢出时移除最旧的条目
                    if len(self._acceptance_cache) > self._acceptance_cache_size:
                        evicted_key, _ = self._acceptance_cache.popitem(last=False)
                        print(f" -> [TestMCPBot Filter] 接受缓存已满，移除 {evicted_key}")

                    return True
                # 没有@机器人，忽略
                else:
                    print(f" -> [TestMCPBot Filter] 顶层消息 {message_id} 已忽略（未 @）")
                    return False
            # 话题内消息，总是返回 True（在 process_message_in_context 中判断是否处理）
            else:
                return True
        # 私聊消息，总是处理
        else:
            return True


    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:
        """
        初始化会话上下文

        检查该话题是否在接受缓存中（即是否通过顶层 @ 启动）
        """
        is_accepted: bool = thread_root_id in self._acceptance_cache

        if not is_accepted:
            print(f" -> [TestMCPBot Context] 话题 {thread_root_id} 不在接受缓存中")

        return {
            "is_accepted": is_accepted,
        }


    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        """
        处理消息的核心逻辑

        群聊逻辑对齐 pku_phy_fermion_bot：
        1. 群聊顶层消息：如果被接受则进入业务逻辑，否则抛出异常
        2. 群聊话题内消息：如果话题被接受则进入业务逻辑，否则提示用户
        3. 私聊消息：正常处理，不强制要求用户去群聊
        """
        message_id: str = parsed_message["message_id"]
        chat_type: str = parsed_message["chat_type"]
        is_thread_root: bool = parsed_message["is_thread_root"]
        mentioned_me: bool = parsed_message["mentioned_me"]
        text: str = parsed_message["text"]
        image_keys: List[str] = parsed_message["image_keys"]

        # 群聊消息
        if chat_type == "group":
            # 是顶层消息
            if is_thread_root:
                # 进入业务逻辑
                if context["is_accepted"]:
                    pass  # 继续执行业务逻辑
                # 应该到不了这里（should_process 已经过滤了未 @ 的顶层消息）
                else:
                    raise RuntimeError(
                        f"[TestMCPBot] 顶层消息 {message_id} 未被接受，但进入了 process_message_in_context"
                    )
            # 是话题内消息
            else:
                # 顶层消息 @了，进入业务逻辑
                if context["is_accepted"]:
                    pass  # 继续执行业务逻辑
                # 顶层消息没有 @，但这条消息 @ 了机器人
                # 也应该正常处理并进入业务逻辑
                elif mentioned_me:
                    pass  # 继续执行业务逻辑
                # 顶层消息没有 @，这条消息也没有 @
                # 不进入业务逻辑
                else:
                    return context
        # 私聊消息，正常处理（不强制要求用户去群聊）
        else:
            pass  # 继续执行业务逻辑

        # 业务逻辑：处理消息并调用 MCP 工具
        response: str = ""

        try:
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
