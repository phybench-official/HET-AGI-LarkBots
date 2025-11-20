from ....fundamental import *
from .equation_rendering import *
from .problem_understanding_former import *
from .problem_confirming_former import *
from .problem_solving_former import *


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
    
    
    async def _get_problem_no(
        self,
    )-> int:
        
        async with self._next_problem_no_lock:
            self._next_problem_no += 1
            return self._next_problem_no - 1

    
    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        
        # 群聊消息
        if parsed_message["chat_type"] == "group":
            # 是顶层消息
            if parsed_message["is_thread_root"]:
                # @了机器人，需要处理
                if parsed_message["mentioned_me"]:
                    thread_root_id: Optional[str] = parsed_message["thread_root_id"]
                    assert thread_root_id
                    print(f"[PkuPhyFermionBot] Root message {parsed_message['message_id']} accepted, adding to acceptance cache.")
                    self._acceptance_cache[thread_root_id] = True
                    self._acceptance_cache.move_to_end(thread_root_id)
                    if len(self._acceptance_cache) > self._acceptance_cache_size:
                        evicted_key, _ = self._acceptance_cache.popitem(last=False)
                        print(f"[PkuPhyFermionBot] Evicted {evicted_key} from acceptance cache.")
                    return True
                # 没有@机器人，直接忽略
                else:
                    print(f"[PkuPhyFermionBot] Dropping root message {parsed_message['message_id']} (not mentioned).")
                    return False
            # 是话题内消息，不知道对应的顶层消息怎样，需要处理
            else:
                return True
        # 私聊消息，执行指令/返回教程
        else:
            # 是顶层消息
            if parsed_message["is_thread_root"]:
                # @了机器人，需要处理
                if parsed_message["mentioned_me"]:
                    thread_root_id: Optional[str] = parsed_message["thread_root_id"]
                    assert thread_root_id
                    print(f"[PkuPhyFermionBot] Root message {parsed_message['message_id']} accepted, adding to acceptance cache.")
                    self._acceptance_cache[thread_root_id] = True
                    self._acceptance_cache.move_to_end(thread_root_id)
                    if len(self._acceptance_cache) > self._acceptance_cache_size:
                        evicted_key, _ = self._acceptance_cache.popitem(last=False)
                        print(f"[PkuPhyFermionBot] Evicted {evicted_key} from acceptance cache.")
            return True
    
    
    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:

        is_accepted: bool = thread_root_id in self._acceptance_cache
        if not is_accepted:
            print(f"[PkuPhyFermionBot] Thread {thread_root_id} not in acceptance cache. Ignoring.")

        return {
            "is_accepted": is_accepted,
            "owner": None,
            "history": {
                "prompt": [],
                "images": [],
                "roles": [],
            },
            "document_created": False,
            "document_id": None,
            "document_title": None,
            "document_url": None,
            "document_block_num": None,
            "problem_no": None,
            "problem_confirmed": False,
            "problem_text": None,
            "problem_images": None,
            "answer": None,
            "AI_solver_finished": False,
            "AI_solution": "暂无",
            "problem_archived": False,
            "AI_solver_succeeded": None,
            "comment_on_AI_solution": None,
        }
    
    
    async def _maintain_context_history(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> None:
        
        """
        维护 context 中 history 的用户侧消息
        仅受理简单消息、复杂消息和纯图片消息
        """
        
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
        
        return None
    
    
    async def _reply_message_in_context(
        self,
        context: Dict[str, Any],
        response: str,
        message_id: str,
        images: List[bytes] = [],
        hyperlinks: List[str] = [],
    )-> None:
        
        """
        兼有回复消息、维护 context 中 history 两个功能
        """
        
        reply_message_result = await self.reply_message_async(
            response = response,
            message_id = message_id,
            reply_in_thread = True,
            images = images,
            hyperlinks = hyperlinks,
        )
        if reply_message_result.success():
            context["history"]["prompt"].append(response)
            context["history"]["roles"].append("assistant")
        else:
            raise RuntimeError
    
        
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
        
        # 群聊消息
        if chat_type == "group":
            # 是顶层消息
            if is_thread_root:
                # 进入业务逻辑
                if context["is_accepted"]:
                    assert context["owner"] is None
                    context["owner"] = sender
                    pass
                # 应该到不了这里
                else:
                    raise RuntimeError
            # 是话题内消息
            else:
                # 顶层消息@了，鉴权后进入业务逻辑
                if context["is_accepted"]:
                    if sender == context["owner"]:
                        pass
                    else:
                        if mentioned_me:
                            await self.reply_message_async(
                                response = "请在群聊中@我以发起我和您的专属话题~",
                                message_id = message_id,
                                reply_in_thread = True,
                            )
                            return context
                        else:
                            return context
                # 顶层消息没有@，不进入业务逻辑
                # 如果这一条消息@了，提示要在顶层消息中@
                else:
                    if mentioned_me:
                        await self.reply_message_async(
                            response = "请在群聊中@我以发起我和您的专属话题~",
                            message_id = message_id,
                            reply_in_thread = True,
                        )
                    return context
        # 私聊消息
        else:
            # 鉴权
            try:
                is_admin = parsed_message["sender"] in self._config["admin_open_ids"]
            except:
                is_admin = False
            # 指令处理
            if text.strip().startswith("/"):
                await self._execute_command(
                    command_line = text.strip(),
                    message_id = message_id,
                    is_admin = is_admin,
                    sender_id = sender,
                )
                return context
            # 私聊提交题目
            elif mentioned_me:
                # 是顶层消息
                if is_thread_root:
                    # 进入业务逻辑
                    if context["is_accepted"]:
                        assert context["owner"] is None
                        context["owner"] = sender
                        pass
                    # 应该到不了这里
                    else:
                        raise RuntimeError
                # 是话题内消息
                else:
                    # 顶层消息@了，鉴权后进入业务逻辑
                    if context["is_accepted"]:
                        if sender == context["owner"]:
                            pass
                        else:
                            if mentioned_me:
                                await self.reply_message_async(
                                    response = "请在话题根消息@我以发起我和您的专属话题~",
                                    message_id = message_id,
                                    reply_in_thread = True,
                                )
                                return context
                            else:
                                return context
                    # 顶层消息没有@，不进入业务逻辑
                    # 如果这一条消息@了，提示要在顶层消息中@
                    else:
                        if mentioned_me:
                            await self.reply_message_async(
                                response = "请在在话题根消息@我以发起我和您的专属话题~",
                                message_id = message_id,
                                reply_in_thread = True,
                            )
                        return context
            # 发送教程
            else:
                await self.reply_message_async(
                    response = "请在群聊中@我以发起我和您的专属话题~您可以拉一个我和您的小群，正在向您发送教程...",
                    message_id = message_id,
                )
                await self.reply_message_async(
                    response = self.image_placeholder * 5,
                    message_id = message_id,
                    images = [
                        f"pictures{seperator}PKU_PHY_fermion{seperator}create_group_instructions{seperator}{no}.png"
                        for no in range(1, 6)
                    ],
                )
                await self.reply_message_async(
                    response = "相关教程已发送，请您查阅！",
                    message_id = message_id,
                )
                return context
        
        print(f" -> [Worker] 收到任务: {text}，开始处理")
        await self._maintain_context_history(
            parsed_message = parsed_message,
            context = context,
        )
        
        if not context["document_created"]:
            
            # 这句话不记录在会话历史中
            await self.reply_message_async(
                response = "您的题目已受理，请稍候...",
                message_id = message_id,
                reply_in_thread = True,
            )
            
            assert len(context["history"]["prompt"]) == 1
            message = context["history"]["prompt"][0]
            message = message.replace(self.image_placeholder, "")
            message = message.replace(self._mention_me_text, "")
            problem_images = context["history"]["images"]
            understand_problem_result = await understand_problem_async_former(
                message = message,
                problem_images = problem_images,
                model = self._config["problem_understanding"]["model"],
                temperature = self._config["problem_understanding"]["temperature"],
                timeout = self._config["problem_understanding"]["timeout"],
                trial_num = self._config["problem_understanding"]["trial_num"],
                trial_interval = self._config["problem_understanding"]["trial_interval"],
            )
            problem_title = understand_problem_result["problem_title"]
            problem_text = understand_problem_result["problem_text"]
            answer = understand_problem_result["answer"]
            
            problem_text_rendering_coroutine = self._render_equation_async(
                text = problem_text,
                model = self._config["equation_rendering"]["model"],
                temperature = self._config["equation_rendering"]["temperature"],
                timeout = self._config["equation_rendering"]["timeout"],
                trial_num = self._config["equation_rendering"]["trial_num"],
                trial_interval = self._config["equation_rendering"]["trial_interval"],
            )
            answer_rendering_coroutine = self._render_equation_async(
                text = answer,
                model = self._config["equation_rendering"]["model"],
                temperature = self._config["equation_rendering"]["temperature"],
                timeout = self._config["equation_rendering"]["timeout"],
                trial_num = self._config["equation_rendering"]["trial_num"],
                trial_interval = self._config["equation_rendering"]["trial_interval"],
            )
            problem_text = await problem_text_rendering_coroutine
            answer = await answer_rendering_coroutine
            
            problem_text = problem_text + len(problem_images) * self.image_placeholder
            
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
            
            context["document_created"] = True
            context["document_id"] = document_id
            context["document_title"] = document_title
            context["document_url"] = document_url
            context["document_block_num"] = 0
            context["problem_no"] = problem_no
            context["problem_text"] = problem_text
            context["problem_images"] = problem_images
            context["answer"] = answer
            
            self._problem_id_to_context[problem_no] = context
            
            await self._sync_document_content_with_context(
                context = context,
            )

            await self._reply_message_in_context(
                context = context,
                response = f"您的题目已整理进文档{self.begin_of_hyperlink}{document_title}{self.end_of_hyperlink}，正在进一步处理中，请稍等...",
                message_id = message_id,
                hyperlinks = [document_url],
            )

            return await self._try_to_confirm_problem(
                context = context,
                message_id = message_id,
            )
        
        elif not context["problem_confirmed"]:
            return await self._try_to_confirm_problem(
                context = context,
                message_id = message_id,
            )
        
        elif not context["AI_solver_finished"]:
            raise RuntimeError
        
        elif not context["problem_archived"]:
            return await self._try_to_archive_problem(
                context = context,
                message_id = message_id,
            )
        
        else:
            await self.reply_message_async(
                response = "感谢您的参与！此话题即将不被受理；如有任何疑问，请联系志愿者~",
                message_id = message_id,
            )
            return context
    
    
    async def _try_to_confirm_problem(
        self,
        context: Dict[str, Any],
        message_id: str,
    )-> Dict[str, Any]:
        
        problem_text = context["problem_text"]
        problem_images = context["problem_images"]
        answer = context["answer"]
        history = context["history"]
        
        confirm_problem_result = await confirm_problem_async_former(
            problem_text = problem_text,
            problem_images = problem_images,
            answer = answer,
            history = history,
            model = self._config["problem_confirming"]["model"],
            temperature = self._config["problem_confirming"]["temperature"],
            timeout = self._config["problem_confirming"]["timeout"],
            trial_num = self._config["problem_confirming"]["trial_num"],
            trial_interval = self._config["problem_confirming"]["trial_interval"],
        )
        
        new_problem_text = confirm_problem_result["new_problem_text"]
        new_answer = confirm_problem_result["new_answer"]
        succeeded = confirm_problem_result["succeeded"]
        response = confirm_problem_result["response"]
        
        response = response.replace(self.begin_of_equation, "$")
        response = response.replace(self.end_of_equation, "$")
        
        problem_text_rendering_coroutine = self._render_equation_async(
            text = new_problem_text,
            model = self._config["equation_rendering"]["model"],
            temperature = self._config["equation_rendering"]["temperature"],
            timeout = self._config["equation_rendering"]["timeout"],
            trial_num = self._config["equation_rendering"]["trial_num"],
            trial_interval = self._config["equation_rendering"]["trial_interval"],
        ) \
            if new_problem_text else None
        answer_rendering_coroutine = self._render_equation_async(
            text = new_answer,
            model = self._config["equation_rendering"]["model"],
            temperature = self._config["equation_rendering"]["temperature"],
            timeout = self._config["equation_rendering"]["timeout"],
            trial_num = self._config["equation_rendering"]["trial_num"],
            trial_interval = self._config["equation_rendering"]["trial_interval"],
        ) \
            if new_answer else None
        if problem_text_rendering_coroutine or answer_rendering_coroutine:
            if problem_text_rendering_coroutine:
                context["problem_text"] = await problem_text_rendering_coroutine
            if answer_rendering_coroutine:
                context["answer"] = await answer_rendering_coroutine
            await self._sync_document_content_with_context(
                context = context,
            )
        
        await self._reply_message_in_context(
            context = context,
            response = response,
            message_id = message_id,
        )
        
        if succeeded:
            context["problem_confirmed"] = True
            return await self._try_to_solve_problem(
                context = context,
                message_id = message_id,
            )
        else:
            return context
    
    
    async def _try_to_solve_problem(
        self,
        context: Dict[str, Any],
        message_id: str,
    ) -> Dict[str, Any]:
        
        """
        调用 AI 进行解题，并渲染结果
        """
        
        problem_text = context["problem_text"]
        problem_images = context["problem_images"]
        
        await self._reply_message_in_context(
            context = context,
            response = "正在调用 AI 解题，请稍候...如果您的题目困难，AI 可能需要较长时间思考",
            message_id = message_id,
        )
        
        solve_problem_result = await solve_problem_async_former(
            problem_text = problem_text,
            problem_images = problem_images,
            model = self._config["problem_solving"]["model"],
            temperature = self._config["problem_solving"]["temperature"],
            timeout = self._config["problem_solving"]["timeout"],
            trial_num = self._config["problem_solving"]["trial_num"],
            trial_interval = self._config["problem_solving"]["trial_interval"],
        )
        AI_solution = solve_problem_result["AI_solution"]
        
        AI_solution = await self._render_equation_async(
            text = AI_solution,
            model = self._config["equation_rendering"]["model"],
            temperature = self._config["equation_rendering"]["temperature"],
            timeout = self._config["equation_rendering"]["timeout"],
            trial_num = self._config["equation_rendering"]["trial_num"],
            trial_interval = self._config["equation_rendering"]["trial_interval"],
        )
        
        context["AI_solution"] = AI_solution
        context["AI_solver_finished"] = True

        await self._sync_document_content_with_context(
            context = context,
        )
        
        await self._reply_message_in_context(
            context = context,
            response = "AI 已完成解答，云文档内容已更新，请您查阅！",
            message_id = message_id,
        )
        
        return context


    async def _try_to_archive_problem(
        self,
        context: Dict[str, Any],
        message_id: str,
    ) -> Dict[str, Any]:
        
        await self._reply_message_in_context(
            context = context,
            response = "题目归档功能暂时未实现，流程到此结束。感谢您的使用！",
            message_id = message_id,
        )

        context["problem_archived"] = True
        
        return context
    
    
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
            contribution_count = "N/A (暂无数据库)" 
            role = "👑 管理员" if is_admin else "👤 普通用户"
            response_text = (
                f"📋 **用户档案 (User Profile)**\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🆔 **Open ID**: `{sender_id}`\n"
                f"🛡️ **身份权限**: {role}\n"
                f"🏆 **贡献题目**: `{contribution_count}`\n"
                f"━━━━━━━━━━━━━━━━"
            )
            await self.reply_message_async(response_text, message_id)
            return

        elif command == "/you":
            response_text = (
                f"🤖 **北大物院-费米子活动机器人**\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"🆔 **Bot ID**: `{self._config['open_id']}`\n"
                f"🧠 **内核版本**: PkuPhyFermionBot v0.1.0\n"
                f"🏫 **所属单位**: 北京大学物理学院\n"
                f"✨ **Slogan**: 像费米子一样，虽独一无二，却共同构建物质世界。\n"
                f"━━━━━━━━━━━━━━━━"
            )
            await self.reply_message_async(response_text, message_id)
            return
        
        elif command == "/help":
            help_text = (
                "🛠️ **指令帮助列表**\n"
                "━━━━━━━━━━━━━━━━\n"
                "**用户指令**:\n"
                "• `/me`: 查看个人档案与权限\n"
                "• `/you`: 查看机器人信息\n"
                "• `/help`: 获取此帮助菜单\n"
            )
            if is_admin:
                help_text += (
                    "\n**管理员指令**:\n"
                    "• `/stats`: 查看题库统计\n"
                    "• `/update_config`: 热更新配置\n"
                    "• `/glance <start> <end>`: 批量概览题目\n"
                    "• `/view {id|-1|random} [--verbose]`: 查看题目详情\n"
                )
            help_text += "━━━━━━━━━━━━━━━━"
            await self.reply_message_async(help_text, message_id)
            return

        elif command == "/stats":
            if not is_admin:
                await self.reply_message_async("🚫 **权限拒绝**: 该指令仅限管理员使用。", message_id)
                return
            
            current_total = self._next_problem_no - 1
            response_text = (
                f"📊 **题库统计面板 (Admin)**\n"
                f"━━━━━━━━━━━━━━\n"
                f"🔢 **入库总数**: `{current_total}` 题\n"
                f"🆕 **最新编号**: `#{current_total}`\n"
                f"📉 **今日新增**: N/A\n"
                f"━━━━━━━━━━━━━━"
            )
            await self.reply_message_async(response_text, message_id)
            return

        elif command == "/update_config":
            if not is_admin:
                await self.reply_message_async("🚫 **权限拒绝**: 该指令仅限管理员使用。", message_id)
                return
            
            await self.reply_message_async("🔄 正在重新加载配置文件，请稍候...", message_id)
            result_content = await self._reload_config_async(self._config_path)
            
            if len(result_content.splitlines()) > 100:
                truncated_result_content = "\n".join(
                    result_content.splitlines()[:100] + ["..."]
                )
            else:
                truncated_result_content = result_content
            response_text = (
                f"✅ **配置更新完成！**\n"
                f"📂 **来源**: `{self._config_path}`\n"
                f"📄 **当前内容摘要**:\n"
                f"{truncated_result_content}\n"
                f"(已加载至内存)"
            )
            await self.reply_message_async(response_text, message_id)
            return

        elif command == "/glance":
            if not is_admin:
                await self.reply_message_async("🚫 **权限拒绝**: 该指令仅限管理员使用。", message_id)
                return
            
            if len(args) < 3:
                await self.reply_message_async("⚠️ 参数错误。用法: `/glance <start_id> <end_id>`", message_id)
                return
            
            try:
                start_id = int(args[1])
                end_id = int(args[2])
            except ValueError:
                await self.reply_message_async("⚠️ ID 必须是整数。", message_id)
                return
            
            if end_id - start_id > 20:
                await self.reply_message_async("⚠️ 为了避免消息过长，单次概览请不要超过 20 条。", message_id)
                return
            
            response_lines = [f"📑 **题目概览 (#{start_id} - #{end_id})**"]
            
            for pid in range(start_id, end_id + 1):
                ctx = self._problem_id_to_context.get(pid)
                if ctx:
                    doc_url = ctx.get("document_url", "链接未知")
                    title = ctx.get("document_title", "无标题").split("|")[-1].strip()
                    response_lines.append(f"• `#{pid}`: [{title}]({doc_url})")
                else:
                    response_lines.append(f"• `#{pid}`: ⚠️ (暂无数据，可能尚未加载)")
                
            await self.reply_message_async("\n".join(response_lines), message_id)
            return

        elif command == "/view":
            if not is_admin:
                await self.reply_message_async("🚫 **权限拒绝**: 该指令仅限管理员使用。", message_id)
                return
            
            if len(args) < 2:
                await self.reply_message_async("⚠️ 参数错误。用法: `/view {id|-1|random}`", message_id)
                return
            
            target = args[1]
            verbose = "--verbose" in args
            
            target_id = -1
            if target == "-1":
                target_id = self._next_problem_no - 1
            elif target == "random":
                if self._next_problem_no > 1:
                    target_id = random.randint(1, self._next_problem_no - 1)
                else:
                    await self.reply_message_async("⚠️ 题库为空。", message_id)
                    return
            else:
                try:
                    target_id = int(target)
                except ValueError:
                    await self.reply_message_async("⚠️ ID 格式错误。", message_id)
                    return
            
            if target_id >= self._next_problem_no or target_id <= 0:
                await self.reply_message_async(f"⚠️ 题目 `#{target_id}` 不存在。", message_id)
                return
            target_context = self._problem_id_to_context.get(target_id)
            
            if target_context:
                doc_title = target_context.get("document_title", "未知标题")
                doc_url = target_context.get("document_url", "#")
                status_icon = "✅" if target_context.get("problem_archived") else "⏳"
                
                response_text = (
                    f"📄 **题目详情 #{target_id}**\n"
                    f"━━━━━━━━━━━━━━\n"
                    f"📑 **标题**: {doc_title}\n"
                    f"🔗 **文档**: [点击跳转]({doc_url})\n"
                    f"🚦 **状态**: {status_icon}\n"
                    f"━━━━━━━━━━━━━━"
                )
                
                if verbose:
                    debug_view = {k: v for k, v in target_context.items() if k != "history"}
                    json_str = json.dumps(debug_view, indent=2, ensure_ascii=False, default=str)
                    response_text += f"\n\n🔧 **Context Dump (Verbose)**:\n```json\n{json_str}\n```"
            else:
                response_text = f"⚠️ **查询失败**: 编号 `#{target_id}` 虽然在范围内，但内存中无此记录 (可能重启丢失)。"
            
            await self.reply_message_async(response_text, message_id)
            return

        else:
            await self.reply_message_async(
                response = f"⚠️ **未知指令**: `{command}`\n请输入 `/help` 查看可用指令列表。",
                message_id = message_id,
            )
            return