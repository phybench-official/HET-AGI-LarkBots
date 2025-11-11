from ...fundamental import *


__all__ = [
    "AccumulatorBot",
]


class AccumulatorBot(ParallelThreadLarkBot):
    
    def __init__(
        self, 
        lark_bot_name: str,
        worker_timeout: float = 600.0,
    )-> None:
        
        super().__init__(
            lark_bot_name = lark_bot_name,
            worker_timeout = worker_timeout,
        )
    
    
    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        
        message_type = parsed_message.get("message_type")
        target_message_types = [
            "simple_message",
            "complex_message",
            "single_image",
        ]
        if message_type not in target_message_types:
            print(f"  -> [Filter] 跳过一条类型为 {message_type} 的消息")
            return False
        
        text: str = parsed_message.get("text", "")
        try:
            _ = int(text)
            return True
        except:
            return False
    
    
    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:

        return {"numbers": [], "sum": 0}


    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        
        try:
            message_id = parsed_message["message_id"]
            text = parsed_message["text"]
            current_number = int(text)
        except:
            print("  -> [Worker] 累加器出现未知异常")
            return context
          
        context = deepcopy(context)
        context["numbers"].append(current_number)
        context["sum"] += current_number
        
        response = f"{' + '.join(str(number) for number in context['numbers'])} = {context['sum']}"
        reply_message_result = await self.reply_message_async(
            response = response,
            message_id = message_id,
            reply_in_thread = True,
        )
        
        if reply_message_result.success():
            print("  -> [Worker] 已发送最终答案")
        else:
            print(
                "  -> [Worker] 最终答案发送失败: "
                f"{reply_message_result.code}, {reply_message_result.msg}"
            )
        
        return context

