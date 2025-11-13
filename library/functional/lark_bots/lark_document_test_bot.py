from ...fundamental import *


__all__ = [
    "LarkDocumentTestBot",
]


class LarkDocumentTestBot(ParallelThreadLarkBot):

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
        
        self._mention_me_text = "@做题家"
        self._PKU_alumni_association = "lcnt4qemj6yx"
        self._eureka_lab_bot_file_root = "AqFDfBPoRlFaREdcWPecbO6SnKe"
        self._uploaded_test_image_key = "img_v3_02s0_9c0670aa-5608-4bba-9ab0-1c89ab9478fg"
    
    
    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        
        if parsed_message["chat_type"] == "group":
            if parsed_message["is_thread_root"]:
                if parsed_message["mentioned_me"]:
                    thread_root_id: Optional[str] = parsed_message["thread_root_id"]
                    assert thread_root_id
                    print(f"[LarkDocumentTestBot] Root message {parsed_message['message_id']} accepted, adding to acceptance cache.")
                    self._acceptance_cache[thread_root_id] = True
                    self._acceptance_cache.move_to_end(thread_root_id)
                    if len(self._acceptance_cache) > self._acceptance_cache_size:
                        evicted_key, _ = self._acceptance_cache.popitem(last=False)
                        print(f"[LarkDocumentTestBot] Evicted {evicted_key} from acceptance cache.")
                    return True
                else:
                    print(f"[LarkDocumentTestBot] Dropping root message {parsed_message['message_id']} (not mentioned).")
                    return False
            else:
                return True
        else:
            return True
    
    
    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:

        is_accepted: bool = thread_root_id in self._acceptance_cache
        if not is_accepted:
            print(f"[LarkDocumentTestBot] Thread {thread_root_id} not in acceptance cache. Ignoring.")

        return {
            "is_accepted": is_accepted,
            "document_id": None,
            "document_title": None,
            "document_url": None,
        }

    
    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        
        try:
            
            message_id: str = parsed_message["message_id"]
            chat_type: str = parsed_message["chat_type"]
            is_thread_root: bool = parsed_message["is_thread_root"]
            text: str = parsed_message["text"]
            mentioned_me: bool = parsed_message["mentioned_me"]
            
            if chat_type == "group":
                if not is_thread_root and not context["is_accepted"]:
                    if mentioned_me:
                        await self.reply_message_async(
                            response = "请在群聊中@我~",
                            message_id = message_id,
                        )
                    return context
            else:
                await self.reply_message_async(
                    response = "请在群聊中与我对话~您可以拉一个我与您的小群",
                    message_id = message_id,
                )
                return context
            
            print(f" -> [Worker] 收到任务: {text}，开始处理")
            
            if text == "删除此文档":
                if context["document_id"] is not None:
                    try:
                        await self.delete_file_async(
                            file_token = context["document_id"],
                        )
                    except:
                        await self.reply_message_async(
                            response = "文档删除失败...",
                            message_id = message_id,
                            reply_in_thread = True,
                        )
                        return context
                    await self.reply_message_async(
                        response = "文档已删除~",
                        message_id = message_id,
                        reply_in_thread = True,
                    )
                    context["document_id"] = None
                    return context
                else:
                    await self.reply_message_async(
                        response = "当前话题下暂无文档，请先创建文档~",
                        message_id = message_id,
                        reply_in_thread = True,
                    )
                    return context
            
            text = text.replace(self.begin_of_hyperlink, "")
            text = text.replace(self.end_of_hyperlink, "")
            
            document_id: Optional[str] = context["document_id"]
            if document_id is None:
                on_creation = True
                document_title = f"测试文档-{get_time_stamp(show_minute=True, show_second=True)}"
                create_document_result = await self.create_document_async(
                    title = document_title,
                    folder_token = self._eureka_lab_bot_file_root,
                )
                if not create_document_result["success"]:
                    print("[LarkDocumentTestBot] 获取文档失败")
                    return context
                document_id = create_document_result["document_id"]
                assert document_id is not None
                document_url = get_lark_document_url(
                    tenant = self._PKU_alumni_association,
                    document_id = document_id,
                )
                context["document_id"] = document_id
                context["document_title"] = document_title
                context["document_url"] = document_url
            else:
                on_creation = False
                document_title = context["document_title"]
                document_url = context["document_url"]
                assert document_title is not None
                assert document_url is not None

            text = text.replace(self._mention_me_text, "")
            content = ""
            content += f"{self.begin_of_third_heading}你刚刚新发的内容{self.end_of_third_heading}"
            content += text
            content += f"{self.begin_of_third_heading}云文档图片上传展示{self.end_of_third_heading}"
            content += self.image_placeholder
            content += f"{self.begin_of_third_heading}云文档公式渲染展示{self.end_of_third_heading}"
#             content += f"""这是一个行内公式：{self.begin_of_equation}\\sqrt{{2}}\\ne\\frac{{p}}{{q}}{self.end_of_equation}，它在行内
# {self.begin_of_equation}\\boxed{{2^x+1=3^y, x, y \\in \\mathbb{{N}}^* \\Rightarrow (x,y)=(1,1) \\text{{ or }} (x,y)=(3,2)}}{self.end_of_equation}
# {self.begin_of_equation}(M^{-1})^\\dagger = \\left[ \\exp\\left(\\frac{{i}}{{2}} \\omega_{{\\mu\\nu}} \\sigma^{{\\mu\\nu}}\\right) \\right]^\\dagger = \\exp\\left( -\\frac{{i}}{{2}} \\omega_{{\\mu\\nu}} (\\sigma^{{\\mu\\nu}})^\\dagger \\right){self.end_of_equation}
# """
            content += "WIP."

            try:
                await self.overwrite_document_async(
                    document_id = document_id,
                    content = content,
                    image_keys = [self._uploaded_test_image_key],
                )
            except:
                print("[LarkDocumentTestBot] 更新文档失败")
                return context
            
            if on_creation:
                await self.reply_message_async(
                    response = f"已创建文档 {self.begin_of_hyperlink}{document_title}{self.end_of_hyperlink}",
                    message_id = message_id,
                    reply_in_thread = True,
                    hyperlinks = [document_url],
                )
            else:
                await self.reply_message_async(
                    response = f"文档 {self.begin_of_hyperlink}{document_title}{self.end_of_hyperlink} 已更新~",
                    message_id = message_id,
                    reply_in_thread = True,
                    hyperlinks = [document_url],
                )
            
            return context
        
        except Exception as error:
            print(
                f"[LarkDocumentTestBot] Error during processing message: {error}\n"
                f"{traceback.format_exc()}"
            )
        
        return context
    