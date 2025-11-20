from ....fundamental import *
from .equation_rendering import *
from .problem_understanding import *

# 注意：已移除所有 _former 模块引用，业务逻辑完全重构

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
        
        # 维护多进程启动所需的参数
        self._init_arguments: Dict[str, Any] = {
            "config_path": config_path,
            "worker_timeout": worker_timeout,
            "context_cache_size": context_cache_size,
            "max_workers": max_workers,
        }
        
        self._acceptance_cache_size: int = context_cache_size
        self._acceptance_cache: OrderedDict[str, bool] = OrderedDict()
        
        self._mention_me_text = f"@{self._config['name']}"
        
        # 复用 equation rendering 逻辑，作为工具函数保留
        self._render_equation_async = lambda text, **inference_arguments: render_equation_async(
            text = text,
            begin_of_equation = self.begin_of_equation,
            end_of_equation = self.end_of_equation,
            **inference_arguments,
        )
        
        self._next_problem_no = 1
        self._next_problem_no_lock = asyncio.Lock()
        
        # 用于管理员查看的 Context 镜像
        self._problem_id_to_context: Dict[int, Dict[str, Any]] = {}

        # Workflow 注册中心
        self._workflows: Dict[str, Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = {
            "default": self._workflow_default,
            "deep_think": self._workflow_deep_think,
        }
    
    
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
            "thread_root_id": thread_root_id,
            "is_accepted": is_accepted,
            "owner": None, # 话题发起者 OpenID
            "history": {
                "prompt": [],
                "images": [],
                "roles": [],
            },
            # 题目元数据
            "problem_no": None,
            "problem_text": None,
            "problem_images": [],
            "answer": "暂无",
            "AI_solution": "暂无",
            
            # Workflow 相关
            "trials": [], 
            
            # 文档相关
            "document_created": False,
            "document_id": None,
            "document_title": None,
            "document_url": None,
            "document_block_num": None,
            
            # 状态标记
            "is_archived": False,
        }
    
    
    async def _maintain_context_history(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> None:
        
        message_id: str = parsed_message["message_id"]
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
    
    
    async def _sync_document_content_with_context(
        self,
        context: Dict[str, Any],
    )-> None:
        """
        将内存中 context 的文档内容推至飞书云文档
        要求 document_id、problem_text、problem_images 和 answer 已设置
        会自动维护 context["document_block_num"]
        """
        
        document_id = context["document_id"]
        document_block_num = context["document_block_num"]
        problem_text = context["problem_text"]
        problem_images = context["problem_images"]
        answer = context["answer"]
        AI_solution = context["AI_solution"]
        
        content = ""
        content += f"{self.begin_of_third_heading}题目{self.end_of_third_heading}"
        content += problem_text.strip()
        content += self.divider_placeholder
        content += f"{self.begin_of_third_heading}参考答案{self.end_of_third_heading}"
        content += answer.strip()
        content += self.divider_placeholder
        content += f"{self.begin_of_third_heading}AI 解答{self.end_of_third_heading}"
        content += AI_solution.strip()
        content += self.divider_placeholder
        content += f"{self.begin_of_third_heading}备注{self.end_of_third_heading}"
        content += f"暂无；未来会在这里记录解题工具调用情况、教师评价等信息"
        
        blocks = self.build_document_blocks(
            content = content,
        )
        await self.overwrite_document_async(
            document_id = document_id,
            blocks = blocks,
            images = problem_images,
            existing_block_num = document_block_num,
        )
        context["document_block_num"] = len(blocks)
        
        return None

    
    # -------------------------------------------------------------------------
    # 业务逻辑核心路由
    # -------------------------------------------------------------------------

    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:

        message_id = parsed_message["message_id"]
        chat_type = parsed_message["chat_type"]
        is_thread_root = parsed_message["is_thread_root"]
        text = parsed_message["text"]
        mentioned_me = parsed_message["mentioned_me"]
        sender = parsed_message["sender"]
        
        # 1. 群聊消息路由
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

        # 2. 私聊消息路由
        else:
            if is_thread_root:
                if text.strip().startswith("/"):
                    await self._handle_command(parsed_message, context)
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

    # -------------------------------------------------------------------------
    # 动作原语 (Action Primitives)
    # -------------------------------------------------------------------------

    async def _start_user_specific_topic(
        self,
        context: Dict[str, Any],
        parsed_message: Dict[str, Any],
        sender: Optional[str],
    ) -> None:
        """
        发起用户专属解题话题
        """
        # 强校验：进入此函数时，该 Topic 必须是全新的，Owner 必须为空
        # 如果这里触发 assert error，说明上游路由逻辑出现了严重 bug
        assert context["owner"] is None, f"Topic {context['thread_root_id']} already has owner: {context['owner']}"

        message_id = parsed_message["message_id"]
        
        context["owner"] = sender
        context["is_accepted"] = True
        
        # 记录第一条消息作为题目描述
        await self._maintain_context_history(parsed_message, context)
        
        # 临时回复
        await self.reply_message_async(
            response = "正在解析您的题目并创建云文档，请稍候...",
            message_id = message_id,
            reply_in_thread = True
        )

        # 1. 理解题目
        raw_text = context["history"]["prompt"][0]
        raw_images = context["history"]["images"]
        
        # 替换占位符以清理输入
        clean_text = raw_text.replace(self.image_placeholder, "").replace(self._mention_me_text, "")

        understand_result = await understand_problem_async(
            message = clean_text,
            problem_images = raw_images,
            model = self._config["problem_understanding"]["model"],
            temperature = self._config["problem_understanding"]["temperature"],
            timeout = self._config["problem_understanding"]["timeout"],
            trial_num = self._config["problem_understanding"]["trial_num"],
            trial_interval = self._config["problem_understanding"]["trial_interval"],
        )

        if not understand_result:
            await self.reply_message_async("题目解析失败，请重试。", message_id, reply_in_thread=True)
            return
        
        problem_title = understand_result["problem_title"]
        problem_text = understand_result["problem_text"]
        answer = understand_result["answer"]

        # 2. 渲染公式
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

        # 为图片预留位置：LarkBot 要求 placeholder 数量与 images 列表一致
        problem_text = problem_text + len(raw_images) * self.image_placeholder

        # 3. 获取编号并创建文档
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

        # 4. 更新 Context
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

        # 5. 同步文档内容
        await self._sync_document_content_with_context(context)

        # 6. 正式回复用户
        await self.reply_message_async(
            response = (
                f"已为您创建专属解题话题 #{problem_no}，文档已生成。\n"
                f"🔗 {document_url}\n"
                f"正在使用 [Default] 工作流进行解答，请稍候。"
            ),
            message_id = message_id,
            reply_in_thread = True
        )

        # 7. 启动默认 Workflow
        await self._run_workflow(context, "default")


    async def _handle_owner_input_in_topic(
        self,
        context: Dict[str, Any],
        parsed_message: Dict[str, Any],
    ) -> None:
        """
        处理 Owner 在话题内的发言
        """
        # 强校验：进入此函数时，Context 必须已有 Owner 且与 Sender 一致（在 process_message 中已判断，此处再次确保）
        assert context["owner"] == parsed_message["sender"]
        
        message_id = parsed_message["message_id"]
        text = parsed_message["text"].strip()
        
        await self._maintain_context_history(parsed_message, context)
        
        if text == "深度思考":
            await self.reply_message_async("收到，正在切换至 [Deep Think] 工作流。", message_id, reply_in_thread=True)
            await self._run_workflow(context, "deep_think")
        elif text == "默认解题":
            await self.reply_message_async("收到，正在切换至 [Default] 工作流。", message_id, reply_in_thread=True)
            await self._run_workflow(context, "default")
        else:
            # 默认回复：展示菜单 (Plain text style)
            menu = (
                "收到您的消息。\n"
                "如需切换解题模式，请回复以下关键词：\n"
                "[默认解题] 快速获取基础解答\n"
                "[深度思考] 启用慢思考模式，多角度分析\n"
                "您也可以继续补充题目信息或图片。"
            )
            await self.reply_message_async(menu, message_id, reply_in_thread=True)


    async def _send_tutorial(self, message_id: str) -> None:
        """
        发送教程
        """
        tutorial_text = (
            "简易使用说明：\n"
            "1. 发起解题：请在群聊新建消息并 @我，或直接私聊发送题目。\n"
            "2. 指令系统：私聊输入 /help 可查看可用指令。\n"
            "3. 工作流：话题建立后，可按提示切换 AI 解题模式。"
        )
        await self.reply_message_async(tutorial_text, message_id)


    async def _handle_command(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        """
        处理指令
        """
        message_id = parsed_message["message_id"]
        text = parsed_message["text"]
        sender = parsed_message["sender"]
        
        # 直接获取，不兜底
        is_admin = sender in self._config["admin_open_ids"]

        await self._execute_command(
            command_line = text,
            message_id = message_id,
            is_admin = is_admin,
            sender_id = sender
        )


    # -------------------------------------------------------------------------
    # Workflow & Trial Management
    # -------------------------------------------------------------------------

    async def _run_workflow(
        self,
        context: Dict[str, Any],
        workflow_name: str,
    ) -> None:
        """
        执行一次 Trial
        """
        # 直接获取，如果 key 不存在，直接 KeyError Fast Fail，不写 "if not func return"
        workflow_func = self._workflows[workflow_name]
        
        # 记录开始
        trial_record = {
            "workflow": workflow_name,
            "status": "running",
            "start_time": get_time_stamp(),
            "result": None
        }
        context["trials"].append(trial_record)
        
        try:
            await workflow_func(context)
            trial_record["status"] = "success"
        except Exception as e:
            trial_record["status"] = "failed"
            trial_record["error"] = str(e)
            # Worker 线程内的异常最好打印出来，防止静默失败
            print(f"[PkuPhyFermionBot] Workflow {workflow_name} failed: {e}")


    # -------------------------------------------------------------------------
    # Workflows Implementations (Stubs)
    # -------------------------------------------------------------------------

    async def _workflow_default(
        self,
        context: Dict[str, Any],
    ) -> None:
        # TODO: 实现具体的 LLM 调用、Equation Rendering、文档更新逻辑
        # 开发者可以直接从 context["problem_text"] 和 context["problem_images"] 获取输入
        # 完成解答后，更新 context["AI_solution"] 并调用 self._sync_document_content_with_context(context)
        raise NotImplementedError("Default workflow logic to be implemented.")


    async def _workflow_deep_think(
        self,
        context: Dict[str, Any],
    ) -> None:
        # TODO: 实现 Chain-of-Thought 或其他高级逻辑
        raise NotImplementedError("Deep think workflow logic to be implemented.")


    # -------------------------------------------------------------------------
    # Command Executor (Linux Console Style)
    # -------------------------------------------------------------------------

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
        
        # ---------------------------------------------------------
        # User Commands
        # ---------------------------------------------------------

        if command == "/me":
            role = "admin" if is_admin else "user"
            response_text = (
                f"```text\n"
                f"USER_PROFILE\n"
                f"------------\n"
                f"open_id: {sender_id}\n"
                f"role:    {role}\n"
                f"```"
            )
            await self.reply_message_async(response_text, message_id)
            return

        elif command == "/you":
            response_text = (
                f"```text\n"
                f"BOT_INFO\n"
                f"--------\n"
                f"id:      {self._config['open_id']}\n"
                f"version: PkuPhyFermionBot v0.2.5\n"
                f"unit:    PKU Physics\n"
                f"kernel:  linux_compat_mode\n"
                f"```"
            )
            await self.reply_message_async(response_text, message_id)
            return
        
        elif command == "/help":
            help_text = (
                "```text\n"
                "NAME\n"
                "    PkuPhyFermionBot - The physics problem organizer\n\n"
                "USER COMMANDS\n"
                "    /me     Show user profile (OpenID, Role)\n"
                "    /you    Show bot instance info\n\n"
            )
            if is_admin:
                help_text += (
                    "ADMIN COMMANDS\n"
                    "    /stats\n"
                    "        Show real-time problem collection statistics.\n\n"
                    "    /glance <start_id> <end_id>\n"
                    "        Quick overview of a range of problems.\n\n"
                    "    /view <id|-1|random> [--verbose]\n"
                    "        Inspect problem context. -1 for latest.\n\n"
                    "    /update_config [path]\n"
                    "        Hot-reload configuration. Default path used if omitted.\n"
                )
            help_text += "```"
            await self.reply_message_async(help_text, message_id)
            return

        # ---------------------------------------------------------
        # Admin Commands (Fast Fail on permission)
        # ---------------------------------------------------------

        if not is_admin:
            await self.reply_message_async("```text\nEACCES: Permission denied\n```", message_id)
            return

        if command == "/stats":
            current_total = self._next_problem_no - 1
            # 假设这里可以快速获取内存占用或其他 runtime 信息
            await self.reply_message_async(f"```text\nTOTAL_PROBLEMS: {current_total}\n```", message_id)
            return

        elif command == "/glance":
            if len(args) < 3:
                await self.reply_message_async("```text\nUsage: /glance <start> <end>\n```", message_id)
                return
            
            try:
                start_id = int(args[1])
                end_id = int(args[2])
            except ValueError:
                await self.reply_message_async("```text\nERR: IDs must be integers.\n```", message_id)
                return
            
            if end_id < start_id:
                await self.reply_message_async("```text\nERR: End ID must be >= Start ID.\n```", message_id)
                return
                
            if end_id - start_id > 50:
                await self.reply_message_async("```text\nERR: Range too large (max 50).\n```", message_id)
                return

            lines = [f"GLANCE ({start_id} -> {end_id})"]
            for pid in range(start_id, end_id + 1):
                ctx = self._problem_id_to_context.get(pid)
                if ctx:
                    title = ctx.get("document_title", "Untitled").split("|")[-1].strip()
                    status = "[ARC]" if ctx.get("is_archived") else "[ACT]"
                    lines.append(f"#{pid:<4} {status} {title[:20]}")
                else:
                    lines.append(f"#{pid:<4} [N/A]")
            
            report = "\n".join(lines)
            await self.reply_message_async(f"```text\n{report}\n```", message_id)
            return

        elif command == "/view":
            if len(args) < 2:
                await self.reply_message_async("```text\nUsage: /view <id|-1|random> [--verbose]\n```", message_id)
                return
            
            target_str = args[1]
            verbose = "--verbose" in args
            
            try:
                current_max = self._next_problem_no - 1
                if target_str == "-1":
                    target_id = current_max
                elif target_str == "random":
                    if current_max < 1:
                        await self.reply_message_async("```text\nERR: Database empty.\n```", message_id)
                        return
                    target_id = random.randint(1, current_max)
                else:
                    target_id = int(target_str)
            except ValueError:
                await self.reply_message_async("```text\nERR: Invalid ID format.\n```", message_id)
                return

            ctx = self._problem_id_to_context.get(target_id)
            if not ctx:
                await self.reply_message_async(f"```text\nERR: Problem #{target_id} not found in memory.\n```", message_id)
                return
            
            # Info View
            doc_url = ctx.get("document_url", "N/A")
            status = "Archived" if ctx.get("is_archived") else "Active"
            workflow = ctx["trials"][-1]["workflow"] if ctx["trials"] else "None"
            
            info = (
                f"PROBLEM_ID:   {target_id}\n"
                f"STATUS:       {status}\n"
                f"LAST_WORKFLOW:{workflow}\n"
                f"DOC_URL:      {doc_url}\n"
            )
            
            if verbose:
                # Deep dump for debugging
                import json
                # 过滤掉 heavy 的 history，只看状态
                debug_view = {k: v for k, v in ctx.items() if k != "history"}
                # 也可以简略显示 history 长度
                debug_view["history_len"] = len(ctx["history"].get("prompt", []))
                
                json_str = json.dumps(debug_view, indent=2, default=str, ensure_ascii=False)
                info += f"\nCONTEXT_DUMP:\n{json_str}"

            await self.reply_message_async(f"```text\n{info}\n```", message_id)
            return

        elif command == "/update_config":
            target_path = args[1] if len(args) > 1 else self._config_path
            
            await self.reply_message_async(f"Loading config from {target_path}...", message_id)
            try:
                result_content = await self._reload_config_async(target_path)
                preview = result_content[:80].replace("\n", "\\n")
                await self.reply_message_async(f"```text\nOK. Config reloaded.\nPreview: {preview}...\n```", message_id)
            except Exception as e:
                await self.reply_message_async(f"```text\nERR: Reload failed.\n{str(e)}\n```", message_id)
            return

        else:
            await self.reply_message_async(f"```text\nERR: Unknown command '{command}'\n```", message_id)
            return