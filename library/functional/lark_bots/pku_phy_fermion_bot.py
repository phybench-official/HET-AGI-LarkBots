from ...fundamental import *


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
        
        pku_phy_fermion_config = load_from_yaml(f"configs{seperator}pku_phy_fermion_config.yaml")
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
        self._archive_problem_model = pku_phy_fermion_config["problem_archiving"]["model"]
        self._archive_problem_temperature = pku_phy_fermion_config["problem_archiving"]["temperature"]
        self._archive_problem_timeout = pku_phy_fermion_config["problem_archiving"]["timeout"]
        self._archive_problem_trial_num = pku_phy_fermion_config["problem_archiving"]["trial_num"]
        self._archive_problem_trial_interval = pku_phy_fermion_config["problem_archiving"]["trial_interval"]
        
        self._next_problem_no = 1
        self._next_problem_no_lock = asyncio.Lock()
        
        
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
        
        
    # 仅简单消息、复杂消息和纯图片消息可调用
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
            
            assert len(context["history"]["prompt"]) == 0
            understand_problem_text_result = await self._understand_problem(
                message = context["history"]["prompt"][0],
                images = context["history"]["images"],
            )
            problem_title = understand_problem_text_result["problem_title"]
            problem_text = understand_problem_text_result["problem_text"]
            problem_images = understand_problem_text_result["problem_images"]
            answer = understand_problem_text_result["answer"]
            
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
            
            content = ""
            content += f"{self.third_heading_block_type}题目{self.third_heading_block_type}"
            content += problem_text.strip()
            content += self.divider_placeholder
            content += f"{self.third_heading_block_type}参考答案{self.third_heading_block_type}"
            content += answer.strip()
            content += self.divider_placeholder
            content += f"{self.third_heading_block_type}AI 解答过程{self.third_heading_block_type}"
            content += "暂无"
            content += self.divider_placeholder
            content += f"{self.third_heading_block_type}备注{self.third_heading_block_type}"
            content += f"暂无"
            
            blocks = self.build_document_blocks(
                content = content,
            )
            await self.overwrite_document_async(
                document_id = document_id,
                blocks = blocks,
                images = problem_images,
                existing_block_num = 0,
            )

            context["document_created"] = True
            context["document_id"] = document_id
            context["document_title"] = document_title
            context["document_url"] = document_url
            context["document_block_num"] = len(blocks)
            context["problem_no"] = problem_no
            context["problem_text"] = problem_text
            context["problem_images"] = problem_images
            context["answer"] = answer
            
            await self.reply_message_async(
                response = f"您的题目已整理进文档{self.begin_of_hyperlink}{document_title}{self.end_of_hyperlink}，正在进一步处理中，请稍等...",
                message_id = message_id,
                reply_in_thread = True,
                hyperlinks = [document_url]
            )
            
            return await self._try_to_confirm_problem(
                context = context,
                prompt = context["history"]["prompt"],
                images = context["history"]["images"],
                problem_text = problem_text,
                problem_images = problem_images,
                answer = answer,
            )

        elif not context["problem_confirmed"]:
            return await self._try_to_confirm_problem(
                context = context,
                prompt = context["history"]["prompt"],
                images = context["history"]["images"],
                problem_text = context["problem_text"],
                problem_images = context["problem_images"],
                answer = context["answer"]
            )
        
        elif not context["AI_solver_finished"]:
            raise RuntimeError
        
        elif not context["problem_archived"]:
            return context
            # return await self._try_to_archive_problem(
            #     context = context,
            #     **some_args_to_be_determined,
            # )
        
        else:
            await self.reply_message_async(
                response = "感谢您的参与！此话题将不再被受理；如有任何疑问，请联系志愿者~",
                message_id = message_id,
            )
            return context
    
    
    async def _understand_problem(
        self,
        message: str,
        images: List[bytes],
    )-> Dict[str, Any]:
        
        modified_message = ""
        for index, part in enumerate(message.split(self.image_placeholder)):
            if index:
                modified_message += f"({index - 1}.png: {self.image_placeholder})"
            modified_message += part
        message = modified_message
        
        prompt = f"""
您是一个专业的物理问题格式化助手。
您的任务是分析用户提供的图文混合信息，提取关键内容，并按照严格的格式要求重组。

# 1. 输入格式
用户输入将包含文本和图片。图片在文本中将以 `(索引.png: <图片内容>)` 的形式出现，例如 `(0.png: <图片内容>)`, `(1.png: <图片内容>)` 等。

# 2. 您的任务
1.  **提取题干 (problem_text)**：从输入中分离出完整的题目描述。
2.  **提取答案 (answer)**：从输入中分离出参考答案。如果输入中**未提供**参考答案，请使用字符串 "暂无"。
3.  **筛选图片 (problem_image_indices)**：识别出**仅与题干或答案相关的图片**，并以**列表**形式返回它们的**0-based 索引**。如果没有任何图片相关，请返回空列表 `[]`。
4.  **生成标题 (problem_title)**：根据题干内容，生成一个简短、概括性的标题（例如：“电磁感应中的洛伦兹力”）。

# 3. 严格的输出格式

您**必须**将所有提取和生成的内容组合成一个**JSON 代码块**。

## 3.1 JSON 结构
```json
{{
  "problem_title": "string: 您的标题",
  "problem_text": "string: 提取并格式化后的题干",
  "problem_image_indices": [int: 索引1, int: 索引2, ...],
  "answer": "string: 提取并格式化后的答案 或 '暂无'"
}}
````

## 3.2 关键格式要求：数学公式

这是**最重要**的规则：
在输出 `problem_text` 和 `answer` 字符串时，**所有**数学公式、单个变量、希腊字母、方程等，都**必须**被包裹在 `{self.begin_of_equation}` 和 `{self.end_of_equation}` 之间。
飞书的格式不区分行内和行间公式，因此**一切数学符号**都需要包裹。

**错误**的例子：
"一个质量为 m 的小球..."
"公式是 F = ma"
"其中 $\\alpha$ 和 $\\beta$ 是角度。"

**正确**的例子：
"一个质量为 {self.begin_of_equation}m{self.end_of_equation} 的小球..."
"公式是 {self.begin_of_equation}F = ma{self.end_of_equation}"
"其中 {self.begin_of_equation}\\alpha{self.end_of_equation} 和 {self.begin_of_equation}\\beta{self.end_of_equation} 是角度。"

# 4. 执行

请立即开始处理用户接下来提供的图文信息，并只返回一个 JSON 代码块。
{message}
"""

        result = {}
        def check_and_accept(
            response: str,
        )-> bool:
            nonlocal result
            try:
                halfway_result = {}
                json_pattern = r'```json\s*(.*?)\s*```'
                matches = re.findall(json_pattern, response, re.DOTALL)
                assert matches
                json_string = matches[0].strip()
                required_keys = ["problem_title", "problem_text", "problem_image_indices", "answer"]
                required_types = [str, str, list, str]
                try:
                    json_dict = deserialize_json(json_string)
                except:
                    json_dict = deserialize_json(json_string.replace("\\", "\\\\"))
                for required_key, required_type in zip(required_keys, required_types):
                    assert isinstance(json_dict[required_key], required_type)
                    halfway_result[required_key] = json_dict[required_key]
                for image_index in halfway_result["problem_image_indices"]:
                    assert isinstance(image_index, int)
                    assert 0 <= image_index < len(images)
                assert len(set(halfway_result["problem_image_indices"])) == len(halfway_result["problem_image_indices"])
                result = halfway_result
                return True
            except:
                return False
        
        _ = await get_answer_async(
            prompt = prompt,
            model = self._understand_problem_model,
            images = images,
            image_placeholder = self.image_placeholder,
            temperature = self._understand_problem_temperature,
            timeout = self._understand_problem_timeout,
            trial_num = self._understand_problem_trial_num,
            trial_interval = self._understand_problem_trial_interval,
            check_and_accept = check_and_accept,
        )
        
        problem_images = [
            images[i] for i in result["problem_image_indices"]
        ]
        del result["problem_image_indices"]
        result["problem_images"] = problem_images
        
        return result
    
    
    async def _try_to_confirm_problem(
        self,
        context: Dict[str, Any],
        prompt: List[Any],
        images: List[bytes],
        problem_text: str,
        problem_images: List[bytes],
        answer: str,
    )-> Dict[str, Any]:
        
        return context
    
    
    