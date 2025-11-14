from ...fundamental import *
import asyncio
from typing import Coroutine


__all__ = [
    "ReflectorBot",
]


class ReflectorBot(LarkBot):
    
    def __init__(
        self, 
        lark_bot_name: str
    )-> None:
        
        super().__init__(
            lark_bot_name = lark_bot_name,
        )
        
        self.register_message_receive(self.handle_message_receive)
        self._mention_me_text = f"@{self._name}"
    
    
    def handle_message_receive(
        self,
        message: P2ImMessageReceiveV1,
    )-> None:
        
        parsed_message: Dict[str, Any] = self.parse_message(message)
        if not parsed_message["success"]: return
        if parsed_message["chat_type"] == "group":
            if not parsed_message["mentioned_me"]: return
        if parsed_message["message_type"] not in [
            "simple_message",
            "complex_message",
            "single_image",
        ]: return
        
        message_id: str = parsed_message["message_id"]
        text: str = parsed_message["text"]
        image_keys: List[str] = parsed_message["image_keys"]
        hyperlinks: List[str] = parsed_message["hyperlinks"]
        
        response_text: str = f"Reflecting: {text.replace(self._mention_me_text, '')}"
        
        coro: Coroutine[Any, Any, ReplyMessageResponse] = self.reply_message_async(
            response = response_text,
            message_id = message_id,
            reply_in_thread = False,
            image_keys = image_keys,
            hyperlinks = hyperlinks,
        )
        
        try:
            loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
            loop.create_task(self._async_task_wrapper(coro))
        except RuntimeError:
            print("[ReflectorBot] Error: No running event loop found in callback thread.")


    async def _async_task_wrapper(
        self,
        coro: Coroutine[Any, Any, ReplyMessageResponse],
    )-> None:
        """
        [异步] 包装器，用于安全地执行异步回复并捕获任何异常。
        """
        try:
            response: ReplyMessageResponse = await coro
            if not response.success():
                print(f"[ReflectorBot] Failed to reply: {response.code} {response.msg}")
        except Exception as e:
            print(f"[ReflectorBot] Exception during async reply: {e}\n{traceback.format_exc()}")