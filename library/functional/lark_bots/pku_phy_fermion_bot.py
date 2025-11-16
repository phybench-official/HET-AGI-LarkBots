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
            
            raise NotImplementedError
            
            return await self._try_to_confirm_problem(
                context = context,
                prompt = context["history"]["prompt"],
                images = context["history"]["images"],
                problem_text = problem_text,
                problem_images = problem_images,
                answer = answer,
            )

        elif not context["problem_confirmed"]:
            
            raise NotImplementedError
            
            return await self._try_to_confirm_problem(
                context = context,
                prompt = context["history"]["prompt"],
                images = context["history"]["images"],
                problem_text = context["problem_text"],
                problem_images = context["problem_images"],
                answer = context["answer"],
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
            print(f"这一次的 response 是：\n{response}")
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
    
    
    async def _try_to_confirm_problem(
        self,
        context: Dict[str, Any],
        message_id: str,
        all_prompts: List[str],
        all_images: List[bytes],
        problem_text: str,
        problem_images: List[bytes],
        answer: str,
    )-> Dict[str, Any]:
        
        # 1. 准备 Prompt 输入
        
        # 格式化当前的题目图片
        formatted_problem_images = ""
        if not problem_images:
            formatted_problem_images = "无"
        else:
            # 注意：这里的索引是相对于 'problem_images' 列表的，
            # 而 'all_images' 包含了更多图片。LLM 只能看到 'all_images'。
            # 这是一个有风险的设计，但我们暂时只能如此。
            # 我们假设 LLM 足够聪明，能区分。
            formatted_problem_images = f"（包含 {len(problem_images)} 张图片）"

        # 格式化用户回复历史
        original_prompt = all_prompts[0]
        
        formatted_user_replies = ""
        if len(all_prompts) <= 1:
            formatted_user_replies = "（暂无后续补充）"
        else:
            # 合并后续回复
            reply_text = "\n---\n".join(all_prompts[1:])
            # 我们无法安全地将 'all_images' 中的图片与 'all_prompts[1:]' 
            # 对应起来，只能将所有图片传递给 LLM。
            formatted_user_replies = reply_text

        # 2. 定义 Prompt
        prompt = f"""
您是一个严谨的物理问题审查助手。
您的任务是与用户互动，以确认从他们那里收集到的题目信息是否完整、正确，并且适合 AI 解答。

# 1. 核心规则
- **严禁解题**：您的工作是审查，不是解答。
- **严禁画图**：AI 无法创建或绘制图像。如果题目或答案要求画图，必须拒绝。
- **答案中不能有图**：答案（answer）必须是纯文本。

# 2. 当前已整理的信息

## 题干 (problem_text)
{problem_text}

## 题干图片 (problem_images)
{formatted_problem_images}

## 参考答案 (answer)
{answer}

# 3. 用户互动历史 (用于本次审查)

## 用户的原始问题（已处理）
{original_prompt}

## 用户的后续补充/回复
{formatted_user_replies}

# 4. 您的审查与行动任务

请分析 "当前已整理的信息" 和 "用户的后续补充/回复"，然后决定您的行动。
注意：用户传入的图片（<图片内容>）可能包含了题干图片和后续补充的图片。

## 任务 A：审查 AI 解答可行性
1.  **画图检查**：`problem_text` 是否要求 AI **画图**？（例如：“请画出受力分析图”）如果要求，AI 无法完成。
2.  **答案形式检查**：`answer` 是否是“暂无”？如果是，用户的新回复（`后续补充/回复`）是否正在提供答案？
3.  **内容匹配检查**：`problem_text` 和 `answer` 的形式是否匹配？（例如：`problem_text` 要求“计算 A 和 B”，但 `answer` 只提供了 A）。

## 任务 B：解析用户回复
1.  **用户是否在确认？**：如果 `后续补充/回复` 明显表示“是”、“确认”、“没问题”，并且您认为信息已完整，请设置 `succeeded = True`。
2.  **用户是否在修正？**：如果 `后续补充/回复` 提供了新的题干或答案，请使用 `update_problem` 或 `update_answer`。

## 任务 C：决定下一步行动

1.  **如果用户确认 (例如回复 "是的", "ok")**：
    - `succeeded = True`
    - `actions = []` (不要回复)

2.  **如果 AI 无法解答 (例如 "画图题")**：
    - `succeeded = False`
    - `actions = [{{"reply_message": "抱歉，我无法处理需要画图的题目。请您提供一个新题目，或修改当前题目为不需画图的描述。"}} ]`

3.  **如果信息不匹配 (例如 "问题与答案不符")**：
    - `succeeded = False`
    - `actions = [{{"reply_message": "我发现题干和答案似乎不匹配（例如，问题数量与答案数量不符）。您能检查一下吗？"}} ]`

4.  **如果用户提供了修正 (例如提供了新答案)**：
    - `succeeded = False`
    - **重要**：在 `update_problem` 和 `update_answer` 中，您**必须**包含所有必要的数学公式标记 `{self.begin_of_equation}` 和 `{self.end_of_equation}`。
    - （示例）`actions = [
        {{ "update_answer": "这是用户提供的新答案..." }},
        {{"reply_message": "感谢您的补充/修正，请问现在信息完整且正确吗？"}}
      ]`

5.  **如果一切看起来都很好（首次审查）**：
    - `succeeded = False`
    - `actions = [{{"reply_message": "我已经将您的题目整理完毕（如上所示）。请问题干、图片和答案是否都正确且完整？如果不是，请您补充。"}} ]`

# 5. 严格的输出格式

您必须只返回一个 JSON 代码块，结构如下。

```json
{{
  "succeeded": bool,
  "actions": [
    {{ "reply_message": "string" }},
    {{ "update_problem": "string" }},
    {{ "update_answer": "string" }}
  ]
}}
````

  - `succeeded=True` 时 `actions` 必须为 `[]`。

  - `succeeded=False` 时 `actions` 必须包含至少一个 `reply_message`。
    """

      # 3. 定义 check_and_accept
        result: Dict[str, Any] = {}
        def check_and_accept_confirm(
            response: str,
        )-> bool:
            nonlocal result
            print(f"这一次的 response (confirm) 是：\n{response}")
            try:
                halfway_result: Dict[str, Any] = {}
                json_pattern = r'```json\s*(.*?)\s*```'
                # 优先使用 search，如果LLM返回裸JSON也能处理
                matches = re.search(json_pattern, response, re.DOTALL)
                
                json_string = ""
                if matches:
                    json_string = matches.group(1).strip()
                else:
                    if response.strip().startswith("{"):
                        json_string = response.strip()
                    else:
                        assert False, "Response is not JSON or JSON code block"
                
                json_dict = deserialize_json(json_string)
                
                # 检查根键
                assert "succeeded" in json_dict
                assert "actions" in json_dict
                assert isinstance(json_dict["succeeded"], bool)
                assert isinstance(json_dict["actions"], list)
                
                succeeded: bool = json_dict["succeeded"]
                actions: List[Dict[str, Any]] = json_dict["actions"]
                
                halfway_result["succeeded"] = succeeded
                halfway_result["actions"] = actions
                
                # 验证 Action 列表
                has_reply = False
                valid_keys = {"reply_message", "update_problem", "update_answer"}
                
                for action in actions:
                    assert isinstance(action, dict)
                    assert len(action.keys()) == 1, "Action dict must have exactly one key"
                    action_key = list(action.keys())[0]
                    action_value = list(action.values())[0]
                    
                    assert action_key in valid_keys, f"Invalid action key: {action_key}"
                    assert isinstance(action_value, str), f"Action value must be string"
                    
                    if action_key == "reply_message":
                        has_reply = True
                
                if succeeded:
                    assert len(actions) == 0, "actions must be empty when succeeded=True"
                else:
                    assert has_reply, "reply_message is required when succeeded=False"
                
                result = halfway_result
                return True
            except Exception as error:
                print(f"[check_and_accept_confirm] 验证失败: {error}")
                return False

        # 4. 调用 LLM
        _ = await get_answer_async(
            prompt = prompt,
            model = self._confirm_problem_model,
            images = all_images, # 传入所有历史图片
            image_placeholder = self.image_placeholder,
            temperature = self._confirm_problem_temperature,
            timeout = self._confirm_problem_timeout,
            trial_num = self._confirm_problem_trial_num,
            trial_interval = self._confirm_problem_trial_interval,
            check_and_accept = check_and_accept_confirm,
        )
        
        # 5. 执行 Actions
        
        actions: List[Dict[str, Any]] = result.get("actions", [])
        
        if result.get("succeeded", False):
            print("[PkuPhyFermionBot] Problem confirmation succeeded.")
            context["problem_confirmed"] = True
        
        # (无论是否 succeeded，都执行 actions)
        
        reply_message: Optional[str] = None
        
        for action in actions:
            if "update_problem" in action:
                new_problem_text = action["update_problem"]
                print(f"[PkuPhyFermionBot] Updating problem_text to: {new_problem_text}")
                context["problem_text"] = new_problem_text
                # 警告：更新文档的逻辑很复杂，这里只更新了 context
                # 理想情况下，还需要重新生成 problem_images
            
            if "update_answer" in action:
                new_answer = action["update_answer"]
                print(f"[PkuPhyFermionBot] Updating answer to: {new_answer}")
                context["answer"] = new_answer
                # 警告：需要更新文档
            
            if "reply_message" in action:
                reply_message = action["reply_message"]

        if reply_message:
            await self.reply_message_async(
                response = reply_message,
                message_id = message_id,
                reply_in_thread = True,
            )
        
        return context
    
    
    