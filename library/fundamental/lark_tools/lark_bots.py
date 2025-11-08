from ..json_tools import *
from .lark_sdk import *
from ..typing import *


__all__ = [
    "get_lark_bot_token",
    "LarkBot",
]


def get_lark_bot_token(
    lark_bot_name: str,
)-> Tuple[str, str]:
    
    app_token_dict = load_from_json("lark_api_keys.json")
    app_id = app_token_dict[lark_bot_name]["app_id"]
    app_secret = app_token_dict[lark_bot_name]["app_secret"]
    return app_id, app_secret


class LarkBot:
    
    def __init__(
        self,
        lark_bot_name: str,
    )-> None:
        
        app_id, app_secret = get_lark_bot_token(lark_bot_name)
        self._name = lark_bot_name
        self._app_id = app_id
        self._app_secret = app_secret
        
        self._lark_client = lark.Client.builder() \
            .app_id(app_id) \
            .app_secret(app_secret) \
            .log_level(lark.LogLevel.INFO) \
            .build()

        self._event_handler_builder = lark.EventDispatcherHandler.builder(
            encrypt_key = "",
            verification_token = "",
            level = lark.LogLevel.DEBUG
        )
        
        
    def register_message_receive(
        self,
        handler: Any,
    )-> None:
        
        self._event_handler_builder.register_p2_im_message_receive_v1(handler)
        
        
    def start(
        self,
    )-> None:
        
        event_handler = self._event_handler_builder.build()
        lark.ws.Client(
            app_id = self._app_id,
            app_secret = self._app_secret,
            event_handler = event_handler,
            log_level = lark.LogLevel.DEBUG
        ).start()
    
    
    def reply_message(
        self,
        response: str,
        message_id: Optional[str] = None,
    )-> Any:
        
        reply_content = serialize_json({"text": response})
        request_body: ReplyMessageRequestBody = ReplyMessageRequestBody.builder() \
            .content(reply_content) \
            .msg_type("text") \
            .build()
        request_builder = ReplyMessageRequest.builder()
        request_builder = request_builder.request_body(request_body)
        if message_id: request_builder = request_builder.message_id(message_id)
        request = request_builder.build()
        assert self._lark_client.im
        self._lark_client.im.v1.message.reply(request)
        return request

