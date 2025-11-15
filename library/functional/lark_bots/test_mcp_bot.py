from ...fundamental import *


__all__ = [
    "TestMCPBot",
]


test_mcp_prompt_template = """
# 角色
你是一个专业的数学计算助手，擅长使用 Mathematica 进行符号计算和数值计算。

# 任务
你将收到一个包含数学问题的消息。你的任务是：
1. 理解用户的数学问题
2. 选择合适的工具进行计算
3. 清晰地解释计算过程和结果

# 完整消息
{text}

# 可用工具说明
你可以使用以下工具：

**Mathematica 工具**（优先使用，功能最强大）:
- evaluate_mathematica: 执行 Mathematica 代码，适合符号计算、方程求解、微积分、矩阵运算等
- evaluate_mathematica_batch: 批量执行多个 Mathematica 表达式，适合多步骤计算
- get_mathematica_package_info: 查询 Mathematica 包的信息和用法

**备选工具**:
- execute_python: 执行 Python 代码，适合数值计算、数据处理等
- query_wolfram_alpha: 查询 WolframAlpha，适合快速的数学查询和事实查询

# 工具选择建议
- 对于符号计算（如积分、求导、因式分解）：优先使用 evaluate_mathematica
- 对于方程求解：优先使用 evaluate_mathematica
- 对于高精度数值计算：优先使用 evaluate_mathematica
- 对于多步骤计算：可以使用 evaluate_mathematica_batch
- 对于快速简单查询：可以使用 query_wolfram_alpha
- 对于数值模拟、绘图数据生成：可以使用 execute_python

# 输出格式
1. **问题理解**: 简要说明你对问题的理解
2. **工具选择**: 说明你选择使用哪个工具以及为什么
3. **计算过程**: 展示你使用的工具和计算步骤
4. **最终答案**: 给出清晰的最终结果和解释
"""


class TestMCPBot(ParallelThreadLarkBot):
    """
    测试 MCP (Model Context Protocol) 集成的机器人

    专门用于测试 Mathematica MCP 服务器的连接和工具调用功能。
    当用户@机器人或消息中包含【测试】、【数学】等关键词时，机器人会响应。
    """

    def __init__(
        self,
        lark_bot_name: str,
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


    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        """
        判断是否应该处理此消息

        处理条件：
        1. 用户@了机器人
        2. 消息包含特定关键词
        """
        try:
            text: str = parsed_message.get("text", "")
            mentioned_me: bool = parsed_message.get("mentioned_me", False)

            # 调试日志
            print(f" -> [TestMCPBot Filter] 收到消息")
            print(f"    文本: {text}")
            print(f"    提及我: {mentioned_me}")

            keywords = ["【测试】", "【数学】", "mathematica", "Mathematica", "MCP", "mcp"]

            if mentioned_me or any(keyword in text for keyword in keywords):
                print(f" -> [TestMCPBot Filter] 消息命中，转交给 Worker")
                return True

            print(f" -> [TestMCPBot Filter] 消息不匹配，忽略")
            return False

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
        2. 调用 LLM，提供 Mathematica MCP 工具
        3. 返回计算结果
        """
        message_id: str = parsed_message["message_id"]
        response: str = ""

        try:
            text: str = parsed_message["text"]
            image_keys: List[str] = parsed_message["image_keys"]

            print(f" -> [TestMCPBot Worker] 收到任务: {text[:100]}...")

            # 下载消息中的图片（如果有）
            image_bytes_list = await self.download_message_images_async(
                message_id = message_id,
                image_keys = image_keys,
            )

            # 构建提示词
            prompt = test_mcp_prompt_template.format(text=text)

            # 调用 LLM，提供 Mathematica MCP 工具
            print(f" -> [TestMCPBot Worker] 正在调用 LLM，提供 Mathematica MCP 工具...")
            response = await get_answer_async(
                prompt = prompt,
                model = "Qwen-VL-Max",  # 使用支持工具调用的模型
                images = image_bytes_list,
                image_placeholder = self.image_placeholder,
                tools = [
                    # 核心：Mathematica MCP 工具
                    mathematica_evaluate_tool(timeout=60, verbose=True),
                    mathematica_batch_tool(timeout=90, verbose=True),
                    mathematica_package_info_tool(timeout=30, verbose=True),
                    # 备选：Python 工具（用于数值计算）
                    python_tool(timeout=30, verbose=True),
                    # 备选：WolframAlpha 工具（用于快速查询）
                    wolfram_tool(timeout=60, verbose=True),
                ],
                tool_use_trial_num = 10,  # 允许多次工具调用
            )

            print(f" -> [TestMCPBot Worker] LLM 返回结果，准备发送回复")

        except Exception as error:
            print(f" -> [TestMCPBot Worker] 任务执行失败: {error}\n调用栈：\n{traceback.format_exc()}")
            response = (
                f"抱歉，执行过程中遇到了错误：\n\n"
                f"```\n{error}\n```\n\n"
                f"这可能是因为：\n"
                f"1. MCP 服务器连接失败（请检查 mcp_servers_config.json 配置）\n"
                f"2. 工具调用超时（计算可能过于复杂）\n"
                f"3. 代码执行出错（请检查语法）\n"
                f"4. 网络连接问题\n\n"
                f"请检查 MCP 服务器状态和网络连接，然后重试。"
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
