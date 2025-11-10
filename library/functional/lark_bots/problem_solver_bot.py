from ...fundamental import *


__all__ = [
    "ProblemSolverBot",
]


problem_solver_prompt_template = """
# 角色
你是一个非常聪慧的高中生“做题家”。你对解题充满热情，语气自信、清晰，带有一点点属于优等生的、友好的“小骄傲”。

# 任务
你将收到一段包含题目的完整消息。你的任务是：
1. 提取消息中的题目内容。
2. 仔细思考，解出这道题。
3. 用你（聪慧高中生）的口吻，**直接讲解解题方法和思路**，不要复述题目。

# 完整消息
{text}

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
        
        try:
            parse_message_result = self.parse_message(message)
        except Exception as error:
            print(f"  -> [Handler] 解析消息出错：{error}\n调用栈：\n{traceback.format_exc()}")
            return
        if not parse_message_result["success"]:
            print(f"  -> [Handler] 解析消息出错：{parse_message_result['error']}")
            return
        
        message_id = parse_message_result["message_id"]
        message_type = parse_message_result["message_type"]
        target_message_types = [
            "simple_message",
            "complex_message",
            "single_image",
        ]
        if message_type not in target_message_types:
            print(f"  -> [Handler] 跳过一条类型为 {message_type} 的消息")
            return
        
        text = parse_message_result["text"]
        image_keys = parse_message_result["image_keys"]
        mentioned_me = parse_message_result["mentioned_me"]

        keywords = ["【题目】"]
        if mentioned_me or any(keyword in text for keyword in keywords):
            print("  -> [Handler] 启动后台做题家线程")
            worker_thread = threading.Thread(
                target = self._handle_message_receive_background,
                args = (message_id, text, image_keys),
            )
            worker_thread.start()
        
        print("  -> [Handler] 函数执行完毕并返回")
    
    
    def _handle_message_receive_background(
        self,
        message_id: str,
        text: str,
        image_keys: List[str],
    )-> None:

        print(f"  -> [Worker] 收到任务: {text}，开始处理")
        
        image_bytes_list = []
        task_indexers = list(range(len(image_keys)))
        try:
            download_image_results = run_tasks_concurrently(
                task = self.get_message_resource,
                task_indexers = task_indexers,
                task_inputs = [(message_id, image_key, "image") for image_key in image_keys],
                method = "ThreadPoolExecutor",
                max_workers = 3,
                show_progress_bar = False,
            )
        except Exception as error:
            print(
                f"  -> [Worker] 下载图片资源时报错：{error}\n"
                f"调用栈：\n{traceback.format_exc()}"
            )
            return
        for task_index in task_indexers:
            download_image_result = download_image_results[task_index]
            if not download_image_result.success():
                print(f"  -> [Worker] 下载图片资源失败")
                return
            image_bytes_list.append(download_image_result.file.read())
        
        response = get_answer(
            prompt = problem_solver_prompt_template.format(
                text = text,
            ),
            model = "Gemini-2.5-Flash",
            images = image_bytes_list,
            image_placeholder = self._image_placeholder,
            tools = [
                python_tool(timeout=30, verbose=True),
                wolfram_tool(timeout=60, verbose=True),
            ],
            tool_use_trial_num = 10,
        )
        
        reply_message_result = self.reply_message(
            response = response,
            message_id = message_id,
            reply_in_thread = True,
        )
        
        if reply_message_result.success():
            print("  -> [Worker] 已发送最终答案")
        else:
            print(
                "  -> [Worker] 最终答案发送失败: "
                f"{reply_message_result.code}, {reply_message_result.msg}"
            )
