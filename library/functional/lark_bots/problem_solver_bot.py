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


class ProblemSolverBot(ParallelThreadLarkBot):
    
    def __init__(
        self, 
        config_path: str,
        worker_timeout: float = 600.0,
        context_cache_size: int = 1024,
        max_workers: Optional[int] = None,
    )-> None:
        
        super().__init__(
            config_path = config_path, 
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
            "worker_timeout": worker_timeout,
            "context_cache_size": context_cache_size,
            "max_workers": max_workers,
        }
        
        problem_solver_config = load_from_yaml(f"configs{seperator}problem_solver_config.yaml")
        self._association_tenant = problem_solver_config["association_tenant"]
        self._solve_problem_model = problem_solver_config["problem_solving"]["model"]
        self._solve_problem_temperature = problem_solver_config["problem_solving"]["temperature"]
        self._solve_problem_timeout = problem_solver_config["problem_solving"]["timeout"]
        self._solve_problem_trial_num = problem_solver_config["problem_solving"]["trial_num"]
        self._solve_problem_trial_interval = problem_solver_config["problem_solving"]["trial_interval"]
        self._solve_problem_tool_use_trial_num = problem_solver_config["problem_solving"]["tool_use_trial_num"]
    
    
    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        
        text: str = parsed_message.get("text", "")
        mentioned_me: bool = parsed_message.get("mentioned_me", False)

        keywords = ["【题目】"]
        if mentioned_me or any(keyword in text for keyword in keywords):
            print(f" -> [Filter] 消息命中，转交给 Worker")
            return True
        
        return False
    
    
    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:

        return {}

    
    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        
        message_id: str = parsed_message["message_id"]
        response: str = ""
        
        try:
            text: str = parsed_message["text"]
            image_keys: List[str] = parsed_message["image_keys"]
            
            print(f" -> [Worker] 收到任务: {text}，开始处理")
            
            image_bytes_list = await self.download_message_images_async(
                message_id = message_id,
                image_keys = image_keys,
            )
            prompt = problem_solver_prompt_template.format(text=text)
            response = await get_answer_async(
                prompt = prompt,
                model = self._solve_problem_model,
                temperature = self._solve_problem_temperature,
                images = image_bytes_list,
                image_placeholder = self.image_placeholder,
                trial_num = self._solve_problem_trial_num,
                trial_interval = self._solve_problem_trial_interval,
                tools = [
                    python_tool(timeout=30, verbose=True),
                    wolfram_tool(timeout=60, verbose=True),
                ],
                tool_use_trial_num = self._solve_problem_tool_use_trial_num,
            )
        
        except Exception as error:
            print(f" -> [Worker] 任务执行失败: {error}\n调用栈：\n{traceback.format_exc()}")
            response = f"哎呀，我好像算错了... 出了个小 bug: {error}"
        
        reply_message_result = await self.reply_message_async(
            response = response,
            message_id = message_id,
            reply_in_thread = True,
        )

        if reply_message_result.success():
            print(" -> [Worker] 已发送最终答案")
        else:
            print(
                " -> [Worker] 最终答案发送失败: "
                f"{reply_message_result.code}, {reply_message_result.msg}"
            )
        
        return context