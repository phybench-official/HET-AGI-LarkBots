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
        self._workflows: Dict[str, Callable[[Dict[str, Any]], Coroutine[Any, Any, Dict[str, Any]]]] = {
            "default": self._workflow_default,
            "deep_think": self._workflow_deep_think,
        }

        # Workflow 描述中心 (Key -> Description)
        self._workflow_descriptions: Dict[str, str] = {
            "default": "快速获取基础解答",
            "deep_think": "启用慢思考模式，多角度分析"
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
            
            # Workflow 相关
            "trials": [], 
            # 话题级锁，保护 trials 列表和文档追加操作的原子性
            "lock": asyncio.Lock(), 
            
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
    
    
    # -------------------------------------------------------------------------
    # 业务逻辑核心路由
    # -------------------------------------------------------------------------

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
        # Fast Fail
        assert context["owner"] is None, f"Topic {context['thread_root_id']} invariant violated: owner is {context['owner']}"

        message_id = parsed_message["message_id"]
        
        context["owner"] = sender
        context["is_accepted"] = True
        
        # 记录第一条消息
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
            await self.reply_message_async("题目解析服务暂时不可用，请稍后重试或联系管理员。", message_id, reply_in_thread=True)
            return

        if not understand_result:
            await self.reply_message_async("题目解析失败，无法识别题目内容。", message_id, reply_in_thread=True)
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

        # 为图片预留位置
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

        # 5. 初始化文档内容 (Inline)
        content = ""
        content += f"{self.begin_of_second_heading}题目{self.end_of_second_heading}"
        content += problem_text.strip()
        content += self.divider_placeholder
        content += f"{self.begin_of_second_heading}参考答案{self.end_of_second_heading}"
        content += answer.strip()
        content += self.divider_placeholder
        
        blocks = self.build_document_blocks(content)
        await self.overwrite_document_async(
            document_id = document_id,
            blocks = blocks,
            images = raw_images,
            existing_block_num = 0,
        )
        context["document_block_num"] = len(blocks)

        # 6. 正式回复用户
        await self.reply_message_async(
            response = (
                f"已为您创建专属解题话题 #{problem_no}，文档已生成。\n"
                f"🔗 {document_url}\n"
                f"正在后台启动 [default] 工作流，请您稍候..."
            ),
            message_id = message_id,
            reply_in_thread = True
        )

        # 7. 启动默认 Workflow (后台)
        asyncio.create_task(self._run_workflow(context, "default", message_id))


    async def _handle_owner_input_in_topic(
        self,
        context: Dict[str, Any],
        parsed_message: Dict[str, Any],
    ) -> None:
        """
        处理 Owner 在话题内的发言
        """
        assert context["owner"] == parsed_message["sender"], "Invariant violated: sender must be owner"
        
        message_id = parsed_message["message_id"]
        text = parsed_message["text"].strip()
        
        await self._maintain_context_history(parsed_message, context)
        
        target_workflow = None
        if text in self._workflows:
            target_workflow = text
        
        if target_workflow:
            await self.reply_message_async(f"收到，正在后台启动 [{target_workflow}] 工作流...", message_id, reply_in_thread=True)
            asyncio.create_task(self._run_workflow(context, target_workflow, message_id))
        else:
            menu_lines = ["收到您的消息。如需切换解题模式，请回复以下 Key："]
            for key, desc in self._workflow_descriptions.items():
                menu_lines.append(f"[{key}] {desc}")
            menu_lines.append("您也可以继续补充题目信息或图片。")
            
            menu = "\n".join(menu_lines)
            await self.reply_message_async(menu, message_id, reply_in_thread=True)


    async def _send_tutorial(self, message_id: str) -> None:
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
        message_id = parsed_message["message_id"]
        text = parsed_message["text"]
        sender = parsed_message["sender"]
        
        is_admin = sender in self._config["admin_open_ids"]

        await self._execute_command(
            command_line = text,
            message_id = message_id,
            is_admin = is_admin,
            sender_id = sender
        )


    # -------------------------------------------------------------------------
    # Workflow & Trial Management (Background Async)
    # -------------------------------------------------------------------------

    async def _run_workflow(
        self,
        context: Dict[str, Any],
        workflow_name: str,
        reply_message_id: str,
    ) -> None:
        """
        执行一次 Trial 的 Wrapper（运行在后台 Task 中）。
        """
        workflow_func = self._workflows[workflow_name]
        start_time = get_time_stamp()
        
        try:
            result_data = await workflow_func(context)
            
            assert isinstance(result_data, dict), f"Workflow {workflow_name} must return a dict"
            assert "document_content" in result_data, f"Workflow {workflow_name} missing 'document_content'"

            # 临界区：原子更新
            async with context["lock"]:
                trial_record = {
                    "workflow": workflow_name,
                    "status": "success",
                    "start_time": start_time,
                    "end_time": get_time_stamp(),
                    "result": result_data,
                    "document_content": result_data["document_content"],
                    "result_images": result_data.get("images", [])
                }
                context["trials"].append(trial_record)
                
                await self._push_latest_trial_to_document(context)
            
            doc_url = context.get("document_url", "")
            await self.reply_message_async(
                response = f"✅ [{workflow_name}] 工作流执行完毕，结果已追加至云文档。\n🔗 {doc_url}",
                message_id = reply_message_id,
                reply_in_thread = True
            )

        except Exception as e:
            print(f"[PkuPhyFermionBot] Workflow {workflow_name} failed: {e}\n{traceback.format_exc()}")
            async with context["lock"]:
                context["trials"].append({
                    "workflow": workflow_name,
                    "status": "failed",
                    "start_time": start_time,
                    "error": str(e)
                })
            
            await self.reply_message_async(
                response = f"❌ [{workflow_name}] 工作流执行出错: {str(e)}",
                message_id = reply_message_id,
                reply_in_thread = True
            )


    async def _push_latest_trial_to_document(
        self,
        context: Dict[str, Any],
    ) -> None:
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
        trial_no = len(context["trials"])
        doc_content = latest_trial["document_content"]
        images = latest_trial.get("result_images", [])

        content_str = ""
        content_str += f"{self.begin_of_third_heading}AI 解答 {trial_no} | {workflow_name}{self.end_of_third_heading}"
        content_str += doc_content.strip()
        content_str += self.divider_placeholder
        
        blocks = self.build_document_blocks(content_str)
        
        await self.append_document_blocks_async(
            document_id = context["document_id"],
            blocks = blocks,
            images = images
        )


    # -------------------------------------------------------------------------
    # Workflows Implementations (Stubs)
    # -------------------------------------------------------------------------

    async def _workflow_default(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        await asyncio.sleep(2)
        return {
            "document_content": "这是默认工作流生成的测试内容 (Mock)。",
            "images": []
        }

    async def _workflow_deep_think(
        self,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        await asyncio.sleep(5)
        return {
            "document_content": "这是深度思考工作流生成的详细解析 (Mock)。\n包含公式：$E=mc^2$",
            "images": []
        }


    # -------------------------------------------------------------------------
    # Command Executor (Chinese Linux Console Style)
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
        # User Commands (Translated to Chinese)
        # ---------------------------------------------------------

        if command == "/me":
            role = "管理员 (Admin)" if is_admin else "普通用户 (User)"
            response_text = (
                f"```text\n"
                f"[用户档案]\n"
                f"OpenID:   {sender_id}\n"
                f"权限身份: {role}\n"
                f"```"
            )
            await self.reply_message_async(response_text, message_id)
            return

        elif command == "/you":
            response_text = (
                f"```text\n"
                f"[系统信息]\n"
                f"机器人ID: {self._config['open_id']}\n"
                f"版本号:   PkuPhyFermionBot v0.3.1\n"
                f"所属单位: 北大物理学院\n"
                f"运行模式: Linux 兼容模式\n"
                f"```"
            )
            await self.reply_message_async(response_text, message_id)
            return
        
        elif command == "/help":
            help_text = (
                "```text\n"
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
            help_text += "```"
            await self.reply_message_async(help_text, message_id)
            return

        # ---------------------------------------------------------
        # Admin Commands (Fast Fail)
        # ---------------------------------------------------------

        if not is_admin:
            await self.reply_message_async("```text\n错误: 权限不足 (EACCES)\n```", message_id)
            return

        if command == "/stats":
            current_total = self._next_problem_no - 1
            await self.reply_message_async(f"```text\n当前题库总数: {current_total}\n```", message_id)
            return

        elif command == "/glance":
            if len(args) < 3:
                await self.reply_message_async("```text\n用法: /glance <起始ID> <结束ID>\n```", message_id)
                return
            
            try:
                start_id = int(args[1])
                end_id = int(args[2])
            except ValueError:
                await self.reply_message_async("```text\n错误: ID 必须为整数\n```", message_id)
                return
            
            if end_id < start_id:
                await self.reply_message_async("```text\n错误: 结束ID 不能小于 起始ID\n```", message_id)
                return
                
            if end_id - start_id > 50:
                await self.reply_message_async("```text\n错误: 范围过大 (最大 50)\n```", message_id)
                return

            lines = [f"题库概览 ({start_id} -> {end_id})"]
            for pid in range(start_id, end_id + 1):
                ctx = self._problem_id_to_context.get(pid)
                if ctx:
                    title = ctx.get("document_title", "无标题").split("|")[-1].strip()
                    status = "[归档]" if ctx.get("is_archived") else "[活跃]"
                    lines.append(f"#{pid:<4} {status} {title[:20]}")
                else:
                    lines.append(f"#{pid:<4} [无数据]")
            
            report = "\n".join(lines)
            await self.reply_message_async(f"```text\n{report}\n```", message_id)
            return

        elif command == "/view":
            if len(args) < 2:
                await self.reply_message_async("```text\n用法: /view <ID|-1|random> [--verbose]\n```", message_id)
                return
            
            target_str = args[1]
            verbose = "--verbose" in args
            
            try:
                current_max = self._next_problem_no - 1
                if target_str == "-1":
                    target_id = current_max
                elif target_str == "random":
                    if current_max < 1:
                        await self.reply_message_async("```text\n错误: 题库为空\n```", message_id)
                        return
                    target_id = random.randint(1, current_max)
                else:
                    target_id = int(target_str)
            except ValueError:
                await self.reply_message_async("```text\n错误: ID 格式无效\n```", message_id)
                return

            ctx = self._problem_id_to_context.get(target_id)
            if not ctx:
                await self.reply_message_async(f"```text\n错误: 内存中未找到题目 #{target_id}\n```", message_id)
                return
            
            # Info View
            doc_url = ctx.get("document_url", "N/A")
            status = "已归档" if ctx.get("is_archived") else "进行中"
            last_workflow = "无"
            if ctx["trials"]:
                 last_workflow = ctx["trials"][-1]["workflow"]
            
            info = (
                f"题目编号:   {target_id}\n"
                f"当前状态:   {status}\n"
                f"末次工作流: {last_workflow}\n"
                f"文档链接:   {doc_url}\n"
            )
            
            if verbose:
                import json
                # 过滤 heavy 对象
                debug_view = {k: v for k, v in ctx.items() if k not in ["history", "lock"]}
                debug_view["history_len"] = len(ctx["history"].get("prompt", []))
                debug_view["trials_count"] = len(ctx["trials"])
                
                json_str = json.dumps(debug_view, indent=2, default=str, ensure_ascii=False)
                info += f"\n上下文转储 (Dump):\n{json_str}"

            await self.reply_message_async(f"```text\n{info}\n```", message_id)
            return

        elif command == "/update_config":
            target_path = args[1] if len(args) > 1 else self._config_path
            
            await self.reply_message_async(f"正在重载配置 ({target_path})...", message_id)
            try:
                result_content = await self._reload_config_async(target_path)
                preview = result_content[:80].replace("\n", "\\n")
                await self.reply_message_async(f"```text\n成功 (OK)\n摘要: {preview}...\n```", message_id)
            except Exception as e:
                await self.reply_message_async(f"```text\n错误: 重载失败\n{str(e)}\n```", message_id)
            return

        else:
            await self.reply_message_async(f"```text\n错误: 未知指令 '{command}'\n```", message_id)
            return