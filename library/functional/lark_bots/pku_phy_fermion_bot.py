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
        context["history"]["roles"].append("user")
        
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
        
        message = message.replace(self._mention_me_text, "")
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
用户输入将包含文本和图片，图片旁会有索引（如 0.png、1.png）。

# 2. 您的任务
1.  **提取题干 (problem_text)**：从输入中分离出完整的题目描述。
2.  **提取答案 (answer)**：从输入中分离出参考答案。如果输入中**未提供**参考答案，请使用字符串 "暂无"。
3.  **筛选图片 (problem_image_indices)**：识别出**仅与题干或答案相关的图片**，并以**列表**形式返回它们的**0-based 索引**。如果没有任何图片相关，请返回空列表 `[]`。
4.  **生成标题 (problem_title)**：根据题干内容，生成一个简短、概括性的标题（例如：“电磁感应中的洛伦兹力”）。重要注意事项：你只应粗略判断题目的领域和大概知识点，**严禁深入解题**；在**作出一定区分度**的前提下，标题应**尽量简短**。

# 3. 严格的输出格式

您**必须**将所有提取和生成的内容组合成一个**JSON 代码块**。

## 3.1 核心要求
1.  **JSON 有效性**：生成的 JSON 代码块**必须**是一个严格有效的 JSON 对象，可以被标准解析器（例如 Python 的 `json.loads`）直接解析。请确保所有字符串都正确使用了双引号，并且文本内部的特殊字符（如双引号 `"`、换行符 `\\n`）都已正确转义（`\\"`, `\\\\n`）。
2.  **语言一致性**：`problem_title`、`problem_text` 和 `answer` 中的文本**必须**使用与用户输入完全相同的语言。**严禁**将中文翻译成英文，或将英文翻译成中文。

## 3.2 JSON 结构
```json
{{
  "problem_title": "string: 您的标题",
  "problem_text": "string: 提取并格式化后的题干",
  "problem_image_indices": [int: 索引1, int: 索引2, ...],
  "answer": "string: 提取并格式化后的答案 或 '暂无'"
}}
```

## 3.3 关键格式要求：数学公式与排版

这是**最重要**的规则：

**A. 公式包裹**：
在输出 `problem_text` 和 `answer` 字符串时，**所有**数学公式、单个变量、希腊字母、方程等，都**必须**被包裹在 {self.begin_of_equation} 和 {self.end_of_equation} 之间。

**B. 排版对齐 (换行)**：
飞书的格式不区分行内公式和行间公式。因此，在处理换行时，您**可以**对排版进行微调，使其在飞书上显示更自然（例如，将原题中的独立行间公式，在包裹后自然地并入文本行中，使其成为行内公式）。

**C. 严格约束**：
排版调整**仅限于换行**。您**必须**在语言、数学内容和文本内容方面严格遵循原题，不得以任何理由修改、翻译或增删内容（严格遵循 3.1 核心要求）。

**错误**的例子：
"一个质量为 m 的小球..."
"公式是 F = ma"
"其中 $\\alpha$ 和 $\\beta$ 是角度。"

**正确**的例子：
"一个质量为 {self.begin_of_equation}m{self.end_of_equation} 的小球..."
"公式是 {self.begin_of_equation}F = ma{self.end_of_equation}"
"其中 {self.begin_of_equation}\\alpha{self.end_of_equation} 和 {self.begin_of_equation}\\beta{self.end_of_equation} 是角度。"

# 4. 执行

请立即开始处理用户接下来提供的图文信息，并只返回一个 JSON 代码块；注意：请显式地将 JSON 代码块包裹在 ```json 和 ``` 之间。
{message}
"""

        result = {}
        def check_and_accept(
            response: str,
        )-> bool:
            nonlocal result
            print(f"Understand Problem: checking the following response now\n{response}")
            try:
                halfway_result = {}
                json_pattern = r'```json\s*(.*?)\s*```'
                matches = re.findall(json_pattern, response, re.DOTALL)
                assert matches
                json_string = matches[0].strip()
                required_keys = ["problem_title", "problem_text", "problem_image_indices", "answer"]
                required_types = [str, str, list, str]
                json_dict = deserialize_json(json_string)
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
        result["problem_images"] = problem_images
        
        result["problem_text"] = result["problem_text"] + \
            len(result["problem_image_indices"]) * self.image_placeholder
        
        del result["problem_image_indices"]
        
        return result
    
    
    async def _sync_document_content_with_context(
        self,
        context: Dict[str, Any],
    )-> None:
        
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
    
    
    async def _try_to_confirm_problem(
        self,
        context: Dict[str, Any],
        message_id: str,
    )-> Dict[str, Any]:
        
        document_id = context["document_id"]
        document_url = context["document_url"]
        problem_text = context["problem_text"]
        problem_images = context["problem_images"]
        answer = context["answer"]
        history_prompts = context["history"]["prompt"]
        history_images = context["history"]["images"]
        history_roles = context["history"]["roles"]
        
        problem_image_num = len(problem_images)
        former_multi_round_conversations = ""
        for prompt, role in zip(history_prompts, history_roles):
            if role == "user":
                former_multi_round_conversations += f"[用户]\n{prompt}\n"
            elif role == "assistant":
                former_multi_round_conversations += f"[您]\n{prompt}\n"
            else:
                raise RuntimeError

        prompt = f"""
您是一个严谨的物理问题审查助手。
您的任务是与用户互动，以确认从他们那里收集到的题目信息是否完整、正确，并且适合 AI 解答，最终传入飞书。

# 1. 核心规则
- **严禁解题**：您的工作是审查，不是解答。
- **严禁画图**：AI 无法创建或绘制图像。如果题目或答案要求画图，必须拒绝。
- **答案应当整全**：答案（answer）必须是纯文本、不能有图，并且在小问的数量和形式上应该和题目相对应（如果题目有多小问）。
- **图文组合**：`problem_text`（题干文本）和 `problem_images`（题干图片）共同构成了完整的题目。图片将按顺序附加在文本下方。
- **图片数量固定**：题目相关的图片（problem_images）一经上传，其数量（当前为 {problem_image_num} 张）和顺序便已固定，AI 无法增删或修改。

# 2. 当前已整理的信息

## 题干图片 (problem_images)
当前共有 {problem_image_num} 张图片。它们将按顺序附加在题干文本之后。

## 题干 (problem_text)
{problem_text}

## 参考答案 (answer)
{answer}

**公式格式提醒**：
以上 `problem_text` 和 `answer` 中的所有数学公式（无论行内或行间）都必须用 {self.begin_of_equation} 和 {self.end_of_equation} 包裹。
飞书的格式不区分行内公式和行间公式。因此，在处理换行时，您**可以**对排版进行微调，使其在飞书上显示更自然（例如，将原题中的独立行间公式，在包裹后自然地并入文本行中，使其成为行内公式）。

# 3. 之前的与用户互动历史

{former_multi_round_conversations}

# 4. 您的审查与行动任务

请分析 "当前已整理的信息" 和 "用户的后续补充/回复"，然后决定您的行动。

## 任务 A：审查 AI 解答可行性
1.  **画图检查**：`problem_text` 是否要求 AI **画图**？（例如：“请画出受力分析图”）如果要求，AI 无法完成。
2.  **答案形式检查**：`answer` 是否是“暂无”？如果是，用户的新回复是否正在提供答案？
3.  **内容匹配检查 (题干 vs 答案)**：`problem_text` 和 `answer` 的形式是否匹配？（例如：`problem_text` 要求“计算 A 和 B”，但 `answer` 只提供了 A）。
4.  **内容匹配检查 (题干 vs 图片)**：`problem_text` 和 `problem_images` 的组合是否在语义上完整？（例如：`problem_text` 是“如图所示”，但 `problem_image_num` 为 0）。

## 任务 B：解析用户回复
1.  **用户是否在确认？**：如果 `后续补充/回复` 明显表示“是”、“确认”、“没问题”，并且您认为信息已完整（通过任务 A 审查），请设置 `succeeded = True`。
2.  **用户是否在修正？**：如果 `后续补充/回复` 提供了新的题干或答案，请使用 `overwrite_problem_text` 或 `overwrite_answer`。

## 任务 C：决定下一步行动

1.  **如果用户确认 (例如回复 "是的", "ok") 且任务 A 审查通过**：
    - `succeeded = True`
    - `actions = []` (无需回复，系统会自动回复消息，并进入后续流程)

2.  **如果 AI 无法解答 (例如 "画图题")**：
    - `succeeded = False`
    - `actions = [{{"reply_message": "抱歉，我无法处理需要画图的题目。请您重新在群聊中@我以唤起新话题，或修改当前题目为不需画图的描述。"}} ]`

3.  **如果信息不匹配 (例如 "问题与答案不符" 或 "图文不符")**：
    - `succeeded = False`
    - (示例：图文不符) `actions = [{{"reply_message": "我发现题干中提到了图片（例如“如图”），但当前没有上传任何图片。您可以修改当前题目为不需画图的描述，或重新在群聊中@我以唤起新话题，并在创建话题时上传图片"}} ]`
    - (示例：内容不符) `actions = [{{"reply_message": "我发现题干和答案似乎不匹配（例如，问题数量与答案数量不符）。您能检查一下吗？"}} ]`

4.  **如果用户提供了修正 (例如提供了新答案或新题干)**：
    - `succeeded = False`
    - **重要：更新必须是完整的**：`overwrite_problem_text` 或 `overwrite_answer` 的值必须是**完整**的全新文本，用以**完全替换**旧的 `problem_text` 或 `answer`，而不是提供增量修改。
    - **重要：公式格式**：在 `overwrite_problem_text` 和 `overwrite_answer` 的新文本中，**所有**数学公式（不区分行内/行间）都**必须**使用 `{self.begin_of_equation}` 和 `{self.end_of_equation}` 标记。
    - **注意**：`overwrite_problem_text` 只更新文本部分。图片（{problem_image_num} 张）是固定的，无法通过此操作修改。
    - （示例）`actions = [
        {{ "overwrite_answer": "这是用户提供的{self.begin_of_equation}x=1{self.end_of_equation}新答案..." }},
        {{"reply_message": "感谢您的补充/修正，我已在文档{self.begin_of_hyperlink}{document_id}{self.end_of_hyperlink}中更新；请问现在信息完整且正确吗？"}}
      ]`

5.  **如果一切看起来都很好（首次审查）**：
    - `succeeded = False`
    - `actions = [{{"reply_message": "我已经将您的题目整理完毕（如上所示）。请问题干（、图片，如果有图片）和答案是否都正确且完整？如果不是，请您补充。"}} ]`
    
注意，当需要 reply_message 时，请阅读之前的与用户互动历史，确保向当前上下文添加的新消息是自然、符合语感的，同时尽可能保持角色设定一贯性。此外，reply_message 动作会在可能的 overwrite_problem_text 和 overwrite_answer 动作执行完后发生。

# 5. 严格的输出格式

您必须只返回一个 JSON 代码块（注意：请显式地将 JSON 代码块包裹在 ```json 和 ``` 之间），结构如下。

```json
{{
  "succeeded": bool,
  "actions": [
    {{"reply_message": "string"}},
    {{"overwrite_problem_text": "string"}},
    {{"overwrite_answer": "string"}}
  ]
}}
succeeded=True 时 actions 必须为 []。

succeeded=False 时 actions 必须包含至少一个 reply_message（可以同时包含 update 动作）。 
"""

        result = {}
        def check_and_accept(
            response: str,
        )-> bool:
            nonlocal result
            print(f"Confirm Problem: checking the following response now\n{response}")
            try:
                halfway_result = {}
                json_pattern = r'```json\s*(.*?)\s*```'
                matches = re.findall(json_pattern, response, re.DOTALL)
                assert matches
                json_string = matches[0].strip()
                required_keys = ["succeeded", "actions"]
                required_types = [bool, list]
                json_dict = deserialize_json(json_string)
                for required_key, required_type in zip(required_keys, required_types):
                    assert isinstance(json_dict[required_key], required_type)
                    halfway_result[required_key] = json_dict[required_key]
                for key in halfway_result["actions"]:
                    if key == "reply_message":
                        response = halfway_result["actions"]["reply_message"]
                        assert isinstance(response, str)
                        assert response.count(self.begin_of_hyperlink) == response.count(self.end_of_hyperlink)
                    elif key == "overwrite_problem_text":
                        assert isinstance(halfway_result["actions"]["overwrite_problem_text"], str)
                    elif key == "overwrite_answer":
                        assert isinstance(halfway_result["actions"]["overwrite_answer"], str)
                    else:
                        raise KeyError
                if halfway_result["succeeded"]:
                    assert len(halfway_result["actions"]) == 0
                else:
                    assert "reply_message" in halfway_result["actions"]
                result = halfway_result
                return True
            except:
                return False
        
        _ = await get_answer_async(
            prompt = prompt,
            model = self._confirm_problem_model,
            images = problem_images + history_images,
            image_placeholder = self.image_placeholder,
            temperature = self._confirm_problem_temperature,
            timeout = self._confirm_problem_timeout,
            trial_num = self._confirm_problem_trial_num,
            trial_interval = self._confirm_problem_trial_interval,
            check_and_accept = check_and_accept,
        )
        
        if result["succeeded"]:
            await self._reply_message_in_context(
                context = context,
                response = "您提交的题目已入库；正在调用 AI 解答此题目...",
                message_id = message_id,
            )
            return await self._try_to_solve_problem(
                context = context,
            )
        else:
            new_problem_text = result["actions"].get("overwrite_problem_text", None)
            new_answer = result["actions"].get("overwrite_answer", None)
            if new_problem_text or new_answer:
                context["problem_text"] = problem_text
                context["answer"] = new_answer
                await self._sync_document_content_with_context(
                    context = context,
                )
            response = result["actions"]["reply_message"]
            response = response.replace(self.begin_of_equation, "$")
            response = response.replace(self.end_of_equation, "$")
            hyperlink_num = response.count(self.begin_of_hyperlink)
            await self._reply_message_in_context(
                context = context,
                response = response,
                message_id = message_id,
                hyperlinks = [document_url] * hyperlink_num
            )
            return context
    
    
    async def _reply_message_in_context(
        self,
        context: Dict[str, Any],
        response: str,
        message_id: str,
        images: List[bytes] = [],
        hyperlinks: List[str] = [],
    )-> None:
        
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
    
    
    async def _try_to_solve_problem(
        self,
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        
        return context