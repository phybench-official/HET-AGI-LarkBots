from ....fundamental import *
from .equation_rendering import *
from .problem_understanding import *
from .problem_confirming import *
from .problem_solving import *
from .problem_archiving import *


__all__ = [
    "PkuPhyFermionBot",
]


class PkuPhyFermionBot(ParallelThreadLarkBot):

    def __init__(
        self,
        lark_bot_name: str,
        worker_timeout: float = 600.0,
        context_cache_size: int = 1024,
        max_workers: Optional[int] = None,
        config_path: str = f"configs{seperator}pku_phy_fermion_config.yaml",
    )-> None:

        super().__init__(
            lark_bot_name = lark_bot_name,
            worker_timeout = worker_timeout,
            context_cache_size = context_cache_size,
            max_workers = max_workers,
        )
        
        self._acceptance_cache_size: int = context_cache_size
        self._acceptance_cache: OrderedDict[str, bool] = OrderedDict()
        
        self._mention_me_text = f"@{self._name}"
        self._render_equation_async = lambda text: render_equation_async(
            text = text,
            begin_of_equation = self.begin_of_equation,
            end_of_equation = self.end_of_equation,
        )
        
        self._next_problem_no = 1
        self._next_problem_no_lock = asyncio.Lock()
        
        self._load_config(config_path)
        
        
    def _load_config(
        self,
        config_path: str,
    )-> None:
        
        pku_phy_fermion_config = load_from_yaml(config_path)
        self._association_tenant = pku_phy_fermion_config["association_tenant"]
        self._problem_set_folder_token = pku_phy_fermion_config["problem_set_folder_token"]
        self._understand_problem_model = pku_phy_fermion_config["problem_understanding"]["model"]
        self._understand_problem_temperature = pku_phy_fermion_config["problem_understanding"]["temperature"]
        self._understand_problem_timeout = pku_phy_fermion_config["problem_understanding"]["timeout"]
        self._understand_problem_trial_num = pku_phy_fermion_config["problem_understanding"]["trial_num"]
        self._understand_problem_trial_interval = pku_phy_fermion_config["problem_understanding"]["trial_interval"]
        self._confirm_problem_model = pku_phy_fermion_config["problem_confirming"]["model"]
        self._confirm_problem_temperature = pku_phy_fermion_config["problem_confirming"]["temperature"]
        self._confirm_problem_timeout = pku_phy_fermion_config["problem_confirming"]["timeout"]
        self._confirm_problem_trial_num = pku_phy_fermion_config["problem_confirming"]["trial_num"]
        self._confirm_problem_trial_interval = pku_phy_fermion_config["problem_confirming"]["trial_interval"]
        self._solve_problem_model = pku_phy_fermion_config["problem_solving"]["model"]
        self._solve_problem_temperature = pku_phy_fermion_config["problem_solving"]["temperature"]
        self._solve_problem_timeout = pku_phy_fermion_config["problem_solving"]["timeout"]
        self._solve_problem_trial_num = pku_phy_fermion_config["problem_solving"]["trial_num"]
        self._solve_problem_trial_interval = pku_phy_fermion_config["problem_solving"]["trial_interval"]
        self._solve_problem_tool_use_trial_num = pku_phy_fermion_config["problem_solving"]["tool_use_trial_num"]
        self._archive_problem_model = pku_phy_fermion_config["problem_archiving"]["model"]
        self._archive_problem_temperature = pku_phy_fermion_config["problem_archiving"]["temperature"]
        self._archive_problem_timeout = pku_phy_fermion_config["problem_archiving"]["timeout"]
        self._archive_problem_trial_num = pku_phy_fermion_config["problem_archiving"]["trial_num"]
        self._archive_problem_trial_interval = pku_phy_fermion_config["problem_archiving"]["trial_interval"]
    
    
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
        # 私聊消息，返回教程
        else:
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
            "AI_solution": None,
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
        
        content = ""
        content += f"{self.begin_of_third_heading}题目{self.end_of_third_heading}"
        content += problem_text.strip()
        content += self.divider_placeholder
        content += f"{self.begin_of_third_heading}参考答案{self.end_of_third_heading}"
        content += answer.strip()
        content += self.divider_placeholder
        content += f"{self.begin_of_third_heading}AI 解答过程{self.end_of_third_heading}"
        content += "暂无"
        content += self.divider_placeholder
        content += f"{self.begin_of_third_heading}备注{self.end_of_third_heading}"
        content += f"暂无"
        
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
        # 私聊消息，返回教程
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
            
            assert len(context["history"]["prompt"]) == 1
            message = context["history"]["prompt"][0]
            problem_images = context["history"]["images"]
            understand_problem_result = await understand_problem_async(
                message = message,
                problem_images = problem_images,
                model = self._understand_problem_model,
                temperature = self._understand_problem_temperature,
                timeout = self._understand_problem_timeout,
                trial_num = self._understand_problem_trial_num,
                trial_interval = self._understand_problem_trial_interval,
            )
            problem_title = understand_problem_result["problem_title"]
            problem_text = understand_problem_result["problem_text"]
            answer = understand_problem_result["answer"]
            
            problem_text_rendering_coroutine = self._render_equation_async(problem_text)
            answer_rendering_coroutine = self._render_equation_async(answer)
            problem_text = await problem_text_rendering_coroutine
            answer = await answer_rendering_coroutine
            
            problem_no = await self._get_problem_no()
            document_title = f"[题目 {problem_no}] {problem_title}"
            document_id = await self.create_document_async(
                title = document_title,
                folder_token = self._problem_set_folder_token,
            )
            document_url = get_lark_document_url(
                tenant = self._association_tenant,
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
            raise NotImplementedError
        
        else:
            await self.reply_message_async(
                response = "感谢您的参与！此话题将不再被受理；如有任何疑问，请联系志愿者~",
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
        
        confirm_problem_result = await confirm_problem_async(
            problem_text = problem_text,
            problem_images = problem_images,
            answer = answer,
            history = history,
            model = self._confirm_problem_model,
            temperature = self._confirm_problem_temperature,
            timeout = self._confirm_problem_timeout,
            trial_num = self._confirm_problem_trial_num,
            trial_interval = self._confirm_problem_trial_interval,
        )
        
        new_problem_text = confirm_problem_result["new_problem_text"]
        new_answer = confirm_problem_result["new_answer"]
        succeeded = confirm_problem_result["succeeded"]
        response = confirm_problem_result["response"]
        
        problem_text_rendering_coroutine = self._render_equation_async(new_problem_text) \
            if new_problem_text else None
        answer_rendering_coroutine = self._render_equation_async(new_answer) \
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
            )
        else:
            return context
    
    
    async def _try_to_solve_problem(
        self,
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        
        message_id = context["message_id"]
        
        await self._reply_message_in_context(
            context = context,
            response = "暂时没有实现 AI 解题功能，敬请期待",
            message_id = message_id,
        )
        
        return context