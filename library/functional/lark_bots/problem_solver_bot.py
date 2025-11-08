from ...fundamental import *


__all__ = [
    "ProblemSolverBot",
]


problem_solver_prompt_template = """
# 角色
你是一个非常聪慧的高中生“做题家”。你对解题充满热情，语气自信、清晰，带有一点点属于优等生的、友好的“小骄傲”。

# 任务
你将收到一段包含“【题目】”标签的完整消息。你的任务是：
1. 提取“【题目】”后的问题内容。
2. 仔细思考，解出这道题。
3. 用你（聪慧高中生）的口吻，**直接讲解解题方法和思路**，不要复述题目。

# 完整消息
{text_content}

# 输出格式
1.  **开场白**: 请从以下**随机**选一个作为开头：
    * "哈哈，我做出来了！"
    * "搞定！这题不难嘛。"
    * "哼哼，难不倒我！"
    * "我想出来了！"
    * "唔... 略加思索，这题的解法应该是："
    注意开头与解题过程间衔接自然，避免生硬。
2.  **解题过程**: 用清晰的、一步一步的思路来讲解你是如何解开这道题的，就像在给同学讲题一样。
3.  **最终答案**: 在过程的最后，明确给出你的最终答案，例如：“所以，答案就是 xxx。”
"""


class ProblemSolverBot(LarkBot):
    
    def __init__(
        self, 
        lark_bot_name: str
    )-> None:
        
        super().__init__(lark_bot_name)
        
        self.register_message_receive(self.handle_message_receive)
        
    
    def handle_message_receive(
        self,
        message: P2ImMessageReceiveV1,
    )-> None:
        
        print(message)
        
        if message.event is None: return
        if message.event.message is None: return

        message_id = message.event.message.message_id
        chat_type = message.event.message.chat_type
        message_content = message.event.message.content
        if not isinstance(message_id, str):
            print(f"[Handler] 收到非字符串 message_id: {message_id}")
            return
        if not isinstance(chat_type, str):
            print(f"[Handler] 收到非字符串 chat_type: {chat_type}")
            return
        if chat_type != "group":
            print("[Handler] 忽略非群聊消息")
            return
        if not isinstance(message_content, str):
            print(f"[Handler] 收到非字符串 message_content: {message_content}")
            return

        try:
            message_content_dict = deserialize_json(message_content)
            print("message content dict 里的内容有：")
            for key in message_content_dict:
                print(f"{key}: {message_content_dict[key]}")
            text_content = message_content_dict.get("text", "").strip()
        except Exception:
            print("[Handler] 忽略非纯文本消息")
            return

        print(f"[Handler] 收到群消息: {text_content}")

        keywords = ["【题目】"]
        if any(keyword in text_content for keyword in keywords):
            print("  -> [Handler] 启动后台做题家线程")
            worker_thread = threading.Thread(
                target = self._handle_message_receive_background,
                args = (message_id, text_content),
            )
            worker_thread.start()
        
        print("[Handler] 函数执行完毕并返回")
        
        
    def _handle_message_receive_background(
        self,
        message_id: str,
        text_content: str,
    )-> None:

        print(f"  -> [Worker] 收到任务: {text_content}，开始处理...")
        
        try:
            
            response = get_answer(
                prompt = problem_solver_prompt_template.format(
                    text_content = text_content,
                ),
                model = "gemini-2.5-pro",
            )
            
            reply_message_result = self.reply_message(
                response = response,
                message_id = message_id,
            )
            
            if reply_message_result.success():
                print("  -> [Worker] 已发送最终答案")
            else:
                print(
                    "  -> [Worker] 最终答案发送失败: "
                    f"{reply_message_result.code}, {reply_message_result.msg}"
                )

        except Exception as error:
            print(f"  -> [Worker] 处理时发生严重错误: {error}")
