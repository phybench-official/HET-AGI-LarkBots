from ....fundamental import *
from .equation_rendering import *
from .problem_understanding import *
from .workflows import *


__all__ = [
    "PkuPhyFermionBot",
]


class PkuPhyFermionBot(ParallelThreadLarkBot):

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
        
        self._acceptance_cache_size: int = context_cache_size
        self._acceptance_cache: OrderedDict[str, bool] = OrderedDict()
        
        self._mention_me_text = f"@{self._config['name']}"
        
        self._render_equation_async = lambda text, **inference_arguments: render_equation_async(
            text = text,
            begin_of_equation = self.begin_of_equation,
            end_of_equation = self.end_of_equation,
            **inference_arguments,
        )
        
        self._next_problem_no = 1
        self._next_problem_no_lock = asyncio.Lock()
        self._problem_id_to_context: Dict[int, Dict[str, Any]] = {}

        self._workflows: List[str] = [
            "Gemini-2.5-Pro with tools",
            "GPT-5-Pro with tools",
            "Gemini-2.5-Pro",
            "GPT-5-Pro",
        ]
        self._workflow_descriptions: Dict[str, str] = {
            "Gemini-2.5-Pro with tools": "允许 Gemini-2.5-Pro 调用 Python 和 Mathematica 解题",
            "GPT-5-Pro with tools": "允许 GPT-5-Pro 调用 Python 和 Mathematica 解题",
            "Gemini-2.5-Pro": "直接让 Gemini-2.5-Pro 解题",
            "GPT-5-Pro": "直接让 GPT-5-Pro 解题",
        }
        self._workflow_implementations: Dict[str, Callable[[Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]] = {
            "Gemini-2.5-Pro with tools": with_tools_func_factory("Gemini-2.5-Pro", self),
            "GPT-5-Pro with tools": with_tools_func_factory("GPT-5-Pro", self),
            "Gemini-2.5-Pro": straight_forwarding_func_factory("Gemini-2.5-Pro", self),
            "GPT-5-Pro": straight_forwarding_func_factory("GPT-5-Pro", self),
        }
        self._default_workflows: List[str] = [
            "Gemini-2.5-Pro with tools",
        ]
    
    
    async def _get_problem_no(
        self,
    )-> int:
        
        async with self._next_problem_no_lock:
            self._next_problem_no += 1
            return self._next_problem_no - 1

    
    def _mark_thread_as_accepted(
        self,
        thread_root_id: str,
    )-> None:
        
        self._acceptance_cache[thread_root_id] = True
        self._acceptance_cache.move_to_end(thread_root_id)
        
        if len(self._acceptance_cache) > self._acceptance_cache_size:
            evicted_key, _ = self._acceptance_cache.popitem(last=False)
            print(f"[PkuPhyFermionBot] Evicted {evicted_key} from acceptance cache.")


    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        
        chat_type = parsed_message["chat_type"]
        is_thread_root = parsed_message["is_thread_root"]
        mentioned_me = parsed_message["mentioned_me"]
        thread_root_id = parsed_message["thread_root_id"]
        message_id = parsed_message["message_id"]

        # 群聊消息
        if chat_type == "group":
            # 是顶层消息
            if is_thread_root:
                # @了机器人 -> 处理并标记接受
                if mentioned_me:
                    assert thread_root_id
                    print(f"[PkuPhyFermionBot] Group Root message {message_id} accepted.")
                    self._mark_thread_as_accepted(thread_root_id)
                    return True
                # 没有@机器人 -> 忽略
                else:
                    return False
            # 是话题内部消息 -> 交给 worker 判断是否是已接受的话题
            else:
                return True
        
        # 私聊消息
        else:
            if is_thread_root:
                # 只要是私聊的根消息，且@了机器人，都视为激活状态
                if mentioned_me: 
                     assert thread_root_id
                     self._mark_thread_as_accepted(thread_root_id)
            return True
    
    
    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:

        is_accepted: bool = thread_root_id in self._acceptance_cache
        
        return {
            "lock": asyncio.Lock(), 
            "thread_root_id": thread_root_id,
            "is_accepted": is_accepted,
            "owner": None,
            "history": {
                "prompt": [],
                "images": [],
                "roles": [],
            },
            "problem_no": None,
            "problem_text": None,
            "problem_images": None,
            "answer": None,
            "document_created": False,
            "document_id": None,
            "document_title": None,
            "document_url": None,
            "document_block_num": None,
            "trials": [], 
            "running_workflows": 0,
            "is_archived": False,
        }
    
    
    async def _maintain_context_history(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> None:
        
        message_id = parsed_message["message_id"]
        text: str = parsed_message["text"]
        image_keys: List[str] = parsed_message["image_keys"]
        
        if len(image_keys):
            images = await self.download_message_images_async(
                message_id = message_id,
                image_keys = image_keys,
            )
        else:
            images = []
        
        context["history"]["prompt"].append(text)
        context["history"]["images"].extend(images)
        context["history"]["roles"].append("user")
    

    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:

        message_id: str = parsed_message["message_id"]
        chat_type: str = parsed_message["chat_type"]
        is_thread_root: bool = parsed_message["is_thread_root"]
        text: str = parsed_message["text"]
        mentioned_me: bool = parsed_message["mentioned_me"]
        sender: Optional[str] = parsed_message["sender"]
        
        if chat_type == "group":
            if is_thread_root:
                if mentioned_me:
                    await self._start_user_specific_topic(context, parsed_message, sender)
                else:
                    pass
            else:
                if context["is_accepted"]:
                    if sender == context["owner"]:
                        await self._handle_owner_input_in_topic(context, parsed_message)
                    else:
                        if mentioned_me:
                            await self.reply_message_async(
                                response = f"您不是当前专属话题的发起者，请在群聊根消息 {self._mention_me_text} 以发起您自己的专属解题话题。",
                                message_id = message_id,
                                reply_in_thread = True,
                            )
                else:
                    if mentioned_me:
                        await self.reply_message_async(
                            response = f"请在群聊的【根消息】处 {self._mention_me_text} 以发起新的解题话题，系统无法处理楼层中的请求。",
                            message_id = message_id,
                            reply_in_thread = True,
                        )
                    else:
                        pass
        else:
            if is_thread_root:
                if text.strip().startswith("/"):
                    await self._handle_command(parsed_message)
                else:
                    if mentioned_me:
                        await self._start_user_specific_topic(context, parsed_message, sender)
                    else:
                        await self._send_tutorial(message_id)
            else:
                if context["is_accepted"]:
                    await self._handle_owner_input_in_topic(context, parsed_message)
                else:
                    await self._send_tutorial(message_id)

        return context
    

    async def _start_user_specific_topic(
        self,
        context: Dict[str, Any],
        parsed_message: Dict[str, Any],
        sender: Optional[str],
    ) -> None:
        
        message_id = parsed_message["message_id"]
        await self.reply_message_async(
            response = "您的题目已受理，请稍候...",
            message_id = message_id,
            reply_in_thread = True
        )
        
        assert context["owner"] is None
        context["owner"] = sender
        context["is_accepted"] = True
        
        await self._maintain_context_history(parsed_message, context)
        assert len(context["history"]["prompt"]) == 1
        raw_text = context["history"]["prompt"][0]
        raw_images = context["history"]["images"]
        clean_text = raw_text.replace(self.image_placeholder, "").replace(self._mention_me_text, "")

        try:
            understand_result = await understand_problem_async(
                message = clean_text,
                problem_images = raw_images,
                model = self._config["problem_understanding"]["model"],
                temperature = self._config["problem_understanding"]["temperature"],
                timeout = self._config["problem_understanding"]["timeout"],
                trial_num = self._config["problem_understanding"]["trial_num"],
                trial_interval = self._config["problem_understanding"]["trial_interval"],
            )
        except Exception:
            await self.reply_message_async(
                response = "非常抱歉，题目解析出错。请稍后重试或联系志愿者。", 
                message_id = message_id,
                reply_in_thread = True,
            )
            return
        
        problem_title = understand_result["problem_title"]
        problem_text = understand_result["problem_text"]
        answer = understand_result["answer"]

        problem_text_task = self._render_equation_async(
            text = problem_text,
            model = self._config["equation_rendering"]["model"],
            temperature = self._config["equation_rendering"]["temperature"],
            timeout = self._config["equation_rendering"]["timeout"],
            trial_num = self._config["equation_rendering"]["trial_num"],
            trial_interval = self._config["equation_rendering"]["trial_interval"],
        )
        answer_task = self._render_equation_async(
            text = answer,
            model = self._config["equation_rendering"]["model"],
            temperature = self._config["equation_rendering"]["temperature"],
            timeout = self._config["equation_rendering"]["timeout"],
            trial_num = self._config["equation_rendering"]["trial_num"],
            trial_interval = self._config["equation_rendering"]["trial_interval"],
        )
        
        problem_text, answer = await asyncio.gather(problem_text_task, answer_task)
        problem_text = problem_text + len(raw_images) * self.image_placeholder
        problem_no = await self._get_problem_no()
        
        document_title = f"题目 {problem_no} | {problem_title}"
        document_id = await self.create_document_async(
            title = document_title,
            folder_token = self._config["problem_set_folder_token"],
        )
        document_url = get_lark_document_url(
            tenant = self._config["association_tenant"],
            document_id = document_id,
        )

        context["problem_no"] = problem_no
        context["problem_text"] = problem_text
        context["problem_images"] = raw_images
        context["answer"] = answer
        context["document_created"] = True
        context["document_id"] = document_id
        context["document_title"] = document_title
        context["document_url"] = document_url
        context["document_block_num"] = 0
        
        self._problem_id_to_context[problem_no] = context
        
        content = ""
        content += f"{self.begin_of_second_heading}题目{self.end_of_second_heading}"
        content += problem_text.strip()
        content += self.divider_placeholder
        content += f"{self.begin_of_second_heading}参考答案{self.end_of_second_heading}"
        content += answer.strip()
        content += self.divider_placeholder
        content += f"{self.begin_of_second_heading}AI 解答{self.end_of_second_heading}"
        
        blocks = self.build_document_blocks(content)
        await self.overwrite_document_async(
            document_id = document_id,
            blocks = blocks,
            images = raw_images,
            existing_block_num = 0,
        )
        context["document_block_num"] = len(blocks)

        # 启动默认工作流
        for workflow_name in self._default_workflows:
            asyncio.create_task(self._run_workflow(context, workflow_name, message_id))
        
        # 构建菜单和响应
        workflow_menu, _ = self._get_workflow_menu_and_mapping()
        response_text = (
            f"您的题目已整理进文档 {self.begin_of_hyperlink}{document_title}{self.end_of_hyperlink}\n"
            f"已在后台启动默认工作流: {', '.join(self._default_workflows)}\n\n"
            f"您可以稍作等待，也可以调用其他工作流：\n"
            f"{workflow_menu}"
        )

        await self.reply_message_async(
            response = response_text,
            message_id = message_id,
            hyperlinks = [document_url],
            reply_in_thread = True,
        )


    async def _handle_owner_input_in_topic(
        self,
        context: Dict[str, Any],
        parsed_message: Dict[str, Any],
    ) -> None:
        
        assert context["owner"] == parsed_message["sender"]
        message_id = parsed_message["message_id"]
        if context["is_archived"]:
            await self.reply_message_async(
                response = f"题目已归档，此话题即将不再受理；您可以重新 @ 我以开启一个新的解题话题。",
                message_id = message_id,
                reply_in_thread = True
            )
            return
            
        text = parsed_message["text"].strip()
        if "归档" in text:
            context["is_archived"] = True
            await self.reply_message_async(
                response = f"题目已归档。感谢您的使用！",
                message_id = message_id,
                reply_in_thread = True
            )
            return
        
        await self._maintain_context_history(parsed_message, context)
        
        target_workflow = None
        workflow_menu, mapping = self._get_workflow_menu_and_mapping()

        if text.isdigit():
            index = int(text)
            if index in mapping:
                target_workflow = mapping[index]
        elif text in self._workflow_implementations:
            target_workflow = text
            
        async with context["lock"]:
            running_workflows = context["running_workflows"]
        
        if target_workflow:
            asyncio.create_task(self._run_workflow(context, target_workflow, message_id))
            await self.reply_message_async(
                response = f"收到。已启动 [{target_workflow}] 工作流。\n当前有 {running_workflows + 1} 个工作流正在运行。",
                message_id = message_id,
                reply_in_thread = True,
            )
        else:
            status_hint = ""
            if running_workflows == 0:
                status_hint = "\n当前无运行中的工作流。若已完成解题，您可以输入“归档”终止此解题话题。"
            else:
                status_hint = f"\n当前有 {running_workflows} 个工作流正在运行。"

            await self.reply_message_async(
                response = f"未识别指令。请回复以下序号或名称启动解题：\n{workflow_menu}{status_hint}",
                message_id = message_id,
                reply_in_thread = True
            )

    
    def _get_workflow_menu_and_mapping(
        self,
    )-> Tuple[str, Dict[int, str]]:

        lines = []
        mapping = {}
        for workflow_no, workflow in enumerate(self._workflows, 1):
            workflow_description = self._workflow_descriptions[workflow]
            lines.append(f"{workflow_no}. [{workflow}] {workflow_description}")
            mapping[workflow_no] = workflow
        return "\n".join(lines), mapping


    async def _send_tutorial(
        self, 
        message_id: str
    )-> None:
        
        tutorial_text = (
            "您好，这里是北大物院费米子 Bot。\n"
            "使用说明：\n"
            "1. 发起解题话题：请 @ 我并发送题目；题目可以带图片。\n"
            "2. 多次尝试不同工作流：话题建立后，可按提示调用 AI 工作流多次解题。\n"
            "3. 指令系统：以 '/' 开头的私聊消息会被解读为指令；输入 /help 可查看可用指令。\n"
            "如遇任何疑问，您可以随时联系志愿者。"
        )
        await self.reply_message_async(tutorial_text, message_id)


    async def _handle_command(
        self,
        parsed_message: Dict[str, Any],
    ) -> None:
        
        message_id = parsed_message["message_id"]
        text = parsed_message["text"]
        sender = parsed_message["sender"]
        
        is_admin = sender in self._config["admin_open_ids"]

        await self._execute_command(
            command_line = text,
            message_id = message_id,
            is_admin = is_admin,
            sender_id = sender,
        )
    

    async def _run_workflow(
        self,
        context: Dict[str, Any],
        workflow_name: str,
        reply_message_id: str,
    ) -> None:

        workflow_func = self._workflow_implementations[workflow_name]
        start_time = get_time_stamp()
        
        # 1. 仅更新计数器，不操作 trials 列表 (不占位)
        async with context["lock"]:
            context["running_workflows"] += 1

        try:
            # 2. 耗时操作，无锁运行
            workflow_result = await workflow_func(context)
            
            assert isinstance(workflow_result, dict), f"Workflow {workflow_name} must return a dict"
            assert "document_content" in workflow_result, f"Workflow {workflow_name} missing 'document_content'"

            # 3. 拿锁，一气呵成：写入结果 -> 追加文档 -> 更新计数器
            async with context["lock"]:
                trial_record = {
                    "workflow": workflow_name,
                    "status": "success",
                    "start_time": start_time,
                    "end_time": get_time_stamp(),
                    **workflow_result,
                }
                context["trials"].append(trial_record)
                
                # 追加刚写入的这条 (index = -1)
                await self._push_latest_trial_to_document(context)
                
                context["running_workflows"] -= 1
            
            document_title = context["document_title"]
            document_url = context["document_url"]
            
            await self.reply_message_async(
                response = f"[{workflow_name}] 工作流执行完毕，结果已追加至云文档。\n文档链接: {self.begin_of_hyperlink}{document_title}{self.end_of_hyperlink}",
                message_id = reply_message_id,
                hyperlinks = [document_url],
                reply_in_thread = True,
            )

        except Exception as error:
            print(f"[PkuPhyFermionBot] Workflow {workflow_name} failed: {error}\n{traceback.format_exc()}")
            
            # 失败也要拿锁记录并在最后减计数
            async with context["lock"]:
                context["trials"].append({
                "workflow": workflow_name,
                "status": "failed",
                "start_time": start_time,
                "end_time": get_time_stamp(),
                "error": str(error),
            })
                context["running_workflows"] -= 1
            
            await self.reply_message_async(
                response = f"[{workflow_name}] 工作流执行出错: {str(error)}\n您可以联系志愿者以排查问题。",
                message_id = reply_message_id,
                reply_in_thread = True,
            )


    async def _push_latest_trial_to_document(
        self,
        context: Dict[str, Any],
    )-> None:
        """
        将 Context 中最新的 Trial 追加到云文档。
        该方法必须在 context["lock"] 保护下调用。
        """
        if not context["trials"]:
            return

        latest_trial = context["trials"][-1]
        
        if latest_trial["status"] != "success":
            return

        workflow_name = latest_trial["workflow"]
        # trial_no 直接取列表长度
        trial_no = len(context["trials"]) 
        doc_content = latest_trial["document_content"]
        images = latest_trial.get("images", [])

        content_str = ""
        content_str += f"{self.begin_of_third_heading}AI 解答 {trial_no} | {workflow_name}{self.end_of_third_heading}"
        content_str += doc_content.strip()
        content_str += self.divider_placeholder
        
        blocks = self.build_document_blocks(content_str)
        
        await self.append_document_blocks_async(
            document_id = context["document_id"],
            blocks = blocks,
            images = images,
        )


    async def _workflow_default(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        await asyncio.sleep(2)
        return {
            "document_content": "这是默认工作流生成的测试内容 (Mock)。",
        }

    
    async def _workflow_deep_think(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        await asyncio.sleep(5)
        return {
            "document_content": f"这是深度思考工作流生成的详细解析 (Mock)。\n包含公式：{self.begin_of_equation}E=mc^2{self.end_of_equation}",
        }

    
    async def _execute_command(
        self,
        command_line: str,
        message_id: str,
        is_admin: bool,
        sender_id: Optional[str],
    )-> None:
        
        args = command_line.split()
        if not args: return
        command = args[0].lower()

        if command == "/me":
            role = "管理员 (Admin)" if is_admin else "普通用户 (User)"
            response_text = (
                f"[用户档案]\n"
                f"OpenID:   {sender_id}\n"
                f"权限身份: {role}\n"
            )
            await self.reply_message_async(response_text, message_id)
            return

        elif command == "/you":
            response_text = (
                f"[系统信息]\n"
                f"机器人ID: {self._config['open_id']}\n"
                f"所属单位: 北京大学物理学院\n"
                f"最近更新时间：2025/11/20 - 17:16\n"
            )
            await self.reply_message_async(response_text, message_id)
            return
        
        elif command == "/help":
            help_text = (
                "名称\n"
                "    PkuPhyFermionBot - 物理题目整理机器人\n\n"
                "用户指令\n"
                "    /me     查看个人档案 (OpenID, 权限)\n"
                "    /you    查看机器人实例信息\n"
                "    /help   显示本帮助信息\n\n"
            )
            if is_admin:
                help_text += (
                    "管理员指令\n"
                    "    /stats\n"
                    "        显示题库实时统计信息\n\n"
                    "    /glance <起始ID> <结束ID>\n"
                    "        批量概览题目状态\n\n"
                    "    /view <ID|-1|random> [--verbose]\n"
                    "        查看题目详情上下文 (-1 为最新，random 为随机)\n\n"
                    "    /update_config [路径]\n"
                    "        热重载配置文件 (默认使用启动路径)\n"
                )
            await self.reply_message_async(help_text, message_id)
            return

        if not is_admin:
            await self.reply_message_async("错误: 权限不足 (EACCES)", message_id)
            return

        if command == "/stats":
            current_total = self._next_problem_no - 1
            await self.reply_message_async(f"当前题库总数: {current_total}", message_id)
            return

        elif command == "/glance":
            
            if len(args) < 3:
                await self.reply_message_async("用法: /glance <起始ID> <结束ID>", message_id)
                return
            try:
                start_id = int(args[1])
                end_id = int(args[2])
            except ValueError:
                await self.reply_message_async("错误: ID 必须为整数", message_id)
                return
            if end_id < start_id:
                await self.reply_message_async("错误: 结束ID 不能小于 起始ID", message_id)
                return
            if end_id - start_id > 50:
                await self.reply_message_async("错误: 范围过大 (最大 50)", message_id)
                return

            hyperlinks = []
            lines = [f"题库概览 ({start_id} -> {end_id})"]
            for problem_id in range(start_id, end_id + 1):
                context = self._problem_id_to_context.get(problem_id, None)
                if context is not None:
                    title = context["document_title"]
                    document_url = context["document_url"]
                    status = "[归档]" if context["is_archived"] else "[活跃]"
                    lines.append(f"#{problem_id:<4} {status} {self.begin_of_hyperlink}{title}{self.end_of_hyperlink}")
                    hyperlinks.append(document_url)
                else:
                    pass
            
            report = "\n".join(lines)
            await self.reply_message_async(
                response = f"{report}",
                hyperlinks = hyperlinks,
                message_id = message_id,
                reply_in_thread = False,
            )
            return

        elif command == "/view":
            if len(args) < 2:
                await self.reply_message_async("用法: /view <ID|-1|random> [--verbose]", message_id)
                return
            
            target_str = args[1]
            verbose = "--verbose" in args
            
            try:
                current_max = self._next_problem_no - 1
                if target_str == "-1":
                    target_id = current_max
                elif target_str == "random":
                    if current_max < 1:
                        await self.reply_message_async("错误: 题库为空", message_id)
                        return
                    target_id = random.randint(1, current_max)
                else:
                    target_id = int(target_str)
            except ValueError:
                await self.reply_message_async("错误: ID 格式无效", message_id)
                return

            context = self._problem_id_to_context.get(target_id, None)
            if context is None:
                await self.reply_message_async(f"错误: 内存中未找到题目 #{target_id}", message_id)
                return
            
            # Info View
            document_title = context["document_title"]
            document_url = context["document_url"]
            status = "已归档" if context["is_archived"] else "进行中"
            last_workflow = "无"
            if context["trials"]:
                last_workflow = context["trials"][-1]["workflow"]
            
            info = (
                f"题目编号:   {target_id}\n"
                f"当前状态:   {status}\n"
                f"末次工作流: {last_workflow}\n"
                f"文档链接:   {self.begin_of_hyperlink}{document_title}{self.end_of_hyperlink}\n"
            )
            
            if verbose:
                debug_view = {k: v for k, v in context.items() if k not in ["history", "lock"]}
                debug_view["history_len"] = len(context["history"].get("prompt", []))
                debug_view["trials_count"] = len(context["trials"])
                
                json_str = json.dumps(debug_view, indent=2, default=str, ensure_ascii=False)
                info += f"\n上下文转储 (Dump):\n{json_str}"

            await self.reply_message_async(
                response = info,
                message_id = message_id,
                hyperlinks = [document_url],
                reply_in_thread = False,
            )
            return None

        elif command == "/update_config":
            target_path = args[1] if len(args) > 1 else self._config_path
            await self.reply_message_async(
                response = "正在重新加载配置文件，请稍候...",
                message_id = message_id,
            )
            new_config_content = await self._reload_config_async(
                config_path = target_path,
            )
            await self.reply_message_async(
                response = f"配置更新完成！当前内存中的配置如下：\n# {self._config_path}\n{new_config_content}",
                message_id = message_id,
                reply_in_thread = False,
            )
            return None

        else:
            await self.reply_message_async(f"错误: 未知指令 '{command}'", message_id)
            return None