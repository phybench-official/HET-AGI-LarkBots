from ...fundamental import *


__all__ = [
    "ParallelThreadChatBot",
]


class ParallelThreadChatBot(ParallelThreadLarkBot):

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
    
    
    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        
        if parsed_message["chat_type"] == "group":
            if parsed_message["is_thread_root"]:
                if parsed_message["mentioned_me"]:
                    thread_root_id: Optional[str] = parsed_message["thread_root_id"]
                    assert thread_root_id
                    print(f"[ParallelThreadChatBot] Root message {parsed_message['message_id']} accepted, adding to acceptance cache.")
                    self._acceptance_cache[thread_root_id] = True
                    self._acceptance_cache.move_to_end(thread_root_id)
                    if len(self._acceptance_cache) > self._acceptance_cache_size:
                        evicted_key, _ = self._acceptance_cache.popitem(last=False)
                        print(f"[ParallelThreadChatBot] Evicted {evicted_key} from acceptance cache.")
                    return True
                else:
                    print(f"[ParallelThreadChatBot] Dropping root message {parsed_message['message_id']} (not mentioned).")
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
            print(f"[ParallelThreadChatBot] Thread {thread_root_id} not in acceptance cache. Ignoring.")

        return {
            "is_accepted": is_accepted,
            "history": {
                "prompt": [],
                "images": [],
            }, 
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
            image_keys: List[str] = parsed_message["image_keys"]
            mentioned_me: bool = parsed_message["mentioned_me"]
            
            if chat_type == "group":
                if not is_thread_root and not context["is_accepted"]:
                    if mentioned_me:
                        await self.reply_message_async(
                            response = "请在群聊中@我以发起一个聊天话题~",
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
            
            image_bytes_list = await self.download_message_images(
                message_id = message_id,
                image_keys = image_keys,
            )
            context = deepcopy(context)
            context["history"]["prompt"].append(text)
            context["history"]["images"].extend(image_bytes_list)
            
            response = await get_answer_async(
                prompt = context["history"]["prompt"],
                model = "Qwen-VL-Max",
                images = context["history"]["images"],
                image_placeholder = self.image_placeholder,
                tools = [
                    python_tool(timeout=30, verbose=True),
                ],
                tool_use_trial_num = 10,
            )
            
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
            
            context["history"]["prompt"].append(response)

        except Exception as error:
            print(
                f"[ParallelThreadChatBot] Error during processing message: {error}\n"
                f"{traceback.format_exc()}"
            )
        
        return context
    