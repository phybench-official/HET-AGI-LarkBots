from ..typing import *
from .lark_sdk import *
from ..json_tools import *


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
        
        self._image_placeholder = "<image>"
    
       
    def register_message_receive(
        self,
        handler: Callable[[P2ImMessageReceiveV1], None],
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
    
    
    def parse_message(
        self,
        message: P2ImMessageReceiveV1,
    )-> Dict[str, Any]:

        if message.event is None: 
            return {"success": False, "error": "event 字段为空"}
        if message.event.message is None: 
            return {"success": False, "error": "event.message 字段为空"}

        message_id = message.event.message.message_id
        chat_type = message.event.message.chat_type
        message_content = message.event.message.content
        if not isinstance(message_id, str):
            return {"success": False, "error": f"收到非字符串 message_id: {message_id}"}
        if not isinstance(chat_type, str):
            return {"success": False, "error": f"收到非字符串 chat_type: {chat_type}"}
        if not isinstance(message_content, str):
            return {"success": False, "error": f"收到非字符串 message_content: {message_content}"}

        try:
            message_content_dict = deserialize_json(message_content)
        except Exception:
            return {"success": False, "error": "反序列化 message_content 失败"}

        message_content_dict_keys = set(key for key in message_content_dict)
        # simple message
        if message_content_dict_keys == set(["text"]):
            text = message_content_dict["text"]
            parse_message_result = {
                "success": True,
                "message_type": "simple_message",
                "message_id": message_id,
                "chat_type": chat_type,
                "text": text,
                "image_bytes_list": [],
                "message_content_dict": message_content_dict,
            }
            return parse_message_result
        # complex message
        elif message_content_dict_keys == set(["title", "content"]):
            text = ""
            image_keys = []
            hyperlinks = []
            content_lines = message_content_dict["content"]
            for index, line_elements in enumerate(content_lines):
                if index: text += "\n"
                for line_element in line_elements:
                    tag = line_element["tag"]
                    # text element
                    if tag == "text":
                        text += line_element["text"]
                    # image element
                    elif tag == "img":
                        text += self._image_placeholder
                        image_key = line_element["image_key"]
                        image_keys.append(image_key)
                    # hyper link element
                    elif tag == "a":
                        text += line_element["text"]
                        hyperlink = line_element["href"]
                        hyperlinks.append(hyperlink)
                    else:
                        return {
                            "success": False,
                            "error": f"message line element 不合预期：tag 为 {tag}",
                        }
            parse_message_result = {
                "success": True,
                "message_type": "complex_message",
                "message_id": message_id,
                "chat_type": chat_type,
                "text": text,
                "image_keys": image_keys,
                "hyperlinks": hyperlinks,
                "message_content_dict": message_content_dict,
            }
            return parse_message_result
        # single image
        elif message_content_dict_keys == set(["image_key"]):
            image_key = message_content_dict["image_key"]
            parse_message_result = {
                "success": True,
                "message_type": "single_image",
                "message_id": message_id,
                "chat_type": chat_type,
                "image_key": image_key,
                "text": "",
                "message_content_dict": message_content_dict,
            }
            return parse_message_result
        # single file
        elif message_content_dict_keys == set(["file_key", "file_name"]):
            file_key = message_content_dict["file_key"]
            file_name = message_content_dict["file_name"]
            parse_message_result = {
                "success": True,
                "message_type": "single_file",
                "file_key": file_key,
                "file_name": file_name,
                "message_id": message_id,
                "chat_type": chat_type,
                "message_content_dict": message_content_dict,
            }
            return parse_message_result
        else:
            return {
                "success": False, 
                "error": f"message_content 不合预期，包含字段：{', '.join(message_content_dict_keys)}"
            }
            
            
    def get_message_resource(
        self,
        message_id: str,
        resource_key: str,
        resource_type: Literal["image", "file"],
    )-> Any:

        request_builder = GetMessageResourceRequest.builder()
        request_builder = request_builder.message_id(message_id)
        request_builder = request_builder.file_key(resource_key)
        request_builder = request_builder.type(resource_type)
        request = request_builder.build()
        assert self._lark_client.im
        get_message_resource_result = self._lark_client.im.v1.message_resource.get(request)
        return get_message_resource_result
    
    
    def reply_message(
        self,
        response: str,
        message_id: Optional[str] = None,
    )-> ReplyMessageResponse:
        
        reply_content = serialize_json({"text": response})
        request_body_builder = ReplyMessageRequestBody.builder()
        request_body_builder = request_body_builder.content(reply_content)
        request_body_builder = request_body_builder.msg_type("text")
        request_body = request_body_builder.build()
        request_builder = ReplyMessageRequest.builder()
        request_builder = request_builder.request_body(request_body)
        if message_id: request_builder = request_builder.message_id(message_id)
        request = request_builder.build()
        assert self._lark_client.im
        reply_message_result = self._lark_client.im.v1.message.reply(request)
        return reply_message_result
