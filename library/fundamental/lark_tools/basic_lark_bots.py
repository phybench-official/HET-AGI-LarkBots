from ..typing import *
from ..externals import *
from .lark_sdk import *
from ..json_tools import *


__all__ = [
    "get_lark_bot_token",
    "LarkBot",
]


def get_lark_bot_token(
    lark_bot_name: str,
)-> Tuple[str, str, str]:
    
    app_token_dict = load_from_json("lark_api_keys.json")
    app_id = app_token_dict[lark_bot_name]["app_id"]
    app_secret = app_token_dict[lark_bot_name]["app_secret"]
    open_id = app_token_dict[lark_bot_name]["open_id"]
    return app_id, app_secret, open_id


class LarkBot:
    
    def __init__(
        self,
        lark_bot_name: str,
    )-> None:
        
        app_id, app_secret, open_id = get_lark_bot_token(lark_bot_name)
        self._name = lark_bot_name
        self._app_id = app_id
        self._app_secret = app_secret
        self._open_id = open_id
        
        lark_client_builder = lark.Client.builder()
        lark_client_builder = lark_client_builder.app_id(app_id)
        lark_client_builder = lark_client_builder.app_secret(app_secret)
        lark_client_builder = lark_client_builder.log_level(lark.LogLevel.INFO)
        self._lark_client = lark_client_builder.build()

        self._event_handler_builder = lark.EventDispatcherHandler.builder(
            encrypt_key = "",
            verification_token = "",
            level = lark.LogLevel.DEBUG
        )
        
        self._image_placeholder = "<image_never_used_1145141919810abcdef>"
    
    
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
        thread_root_id = message.event.message.root_id
        is_thread_root = False
        if not isinstance(message_id, str):
            return {"success": False, "error": f"收到非字符串 message_id: {message_id}"}
        if not isinstance(chat_type, str):
            return {"success": False, "error": f"收到非字符串 chat_type: {chat_type}"}
        if not isinstance(message_content, str):
            return {"success": False, "error": f"收到非字符串 message_content: {message_content}"}
        if not thread_root_id:
            thread_root_id = message_id
            is_thread_root = True
        
        try:
            message_content_dict = deserialize_json(message_content)
        except Exception:
            return {"success": False, "error": "反序列化 message_content 失败"}
        
        try:
            mention_list = message_content = message.event.message.mentions
            assert mention_list
        except:
            mention_list = []
        mentioned_me = any(
            mention.id.open_id == self._open_id
            for mention in mention_list
            if mention.id is not None
        ) # Very pythonic.

        message_content_dict_keys = set(key for key in message_content_dict)
        # simple message
        if message_content_dict_keys == set(["text"]):
            text = message_content_dict["text"]
            mention_map = {
                mention.key: f"@{mention.name}"
                for mention in mention_list
                if mention.key is not None and mention.name is not None
            }
            if mention_map:
                sorted_keys: List[str] = sorted(mention_map.keys(), key=len, reverse=True)
                pattern = re.compile("|".join(re.escape(k) for k in sorted_keys))
                text = pattern.sub(lambda m: mention_map[m.group(0)], text)
            parse_message_result = {
                "success": True,
                "message_type": "simple_message",
                "message_id": message_id,
                "thread_root_id": thread_root_id,
                "is_thread_root": is_thread_root,
                "chat_type": chat_type,
                "text": text,
                "image_keys": [],
                "mentioned_me": mentioned_me,
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
                    # mention element
                    elif tag == "at":
                        text += "@" + line_element["user_name"]
                    else:
                        return {
                            "success": False,
                            "error": f"message line element 不合预期：tag 为 {tag}",
                        }
            parse_message_result = {
                "success": True,
                "message_type": "complex_message",
                "message_id": message_id,
                "thread_root_id": thread_root_id,
                "is_thread_root": is_thread_root,
                "chat_type": chat_type,
                "text": text,
                "image_keys": image_keys,
                "hyperlinks": hyperlinks,
                "mentioned_me": mentioned_me,
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
                "thread_root_id": thread_root_id,
                "is_thread_root": is_thread_root,
                "chat_type": chat_type,
                "text": "",
                "image_keys": [image_key],
                "mentioned_me": mentioned_me,
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
                "message_id": message_id,
                "thread_root_id": thread_root_id,
                "is_thread_root": is_thread_root,
                "file_key": file_key,
                "file_name": file_name,
                "chat_type": chat_type,
                "mentioned_me": mentioned_me,
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
        message_id: str,
        # reply_in_thread 的逻辑似乎是：
        # 如果为 True，则一定在话题里回复（没有话题也会自动建一个新的话题）
        # 如果为 False，如果消息下没有话题，就在群聊里回复，援引消息
        # 即使为 False，如果消息下已有话题，就在话题里回复
        reply_in_thread: bool = False,
    )-> ReplyMessageResponse:
        
        reply_content = serialize_json({"text": response})
        request_body_builder = ReplyMessageRequestBody.builder()
        request_body_builder = request_body_builder.content(reply_content)
        request_body_builder = request_body_builder.msg_type("text")
        request_body_builder = request_body_builder.reply_in_thread(reply_in_thread)
        request_body = request_body_builder.build()
        request_builder = ReplyMessageRequest.builder()
        request_builder = request_builder.request_body(request_body)
        request_builder = request_builder.message_id(message_id)
        request = request_builder.build()
        assert self._lark_client.im
        reply_message_result = self._lark_client.im.v1.message.reply(request)
        return reply_message_result
    
    
    # TODO: 这有啥用？
    def send_message(
        self,
        receive_id_type: Literal["chat_id", "open_id", "user_id"],
        receive_id: str,
        content: str,
        msg_type: str = "text",
    )-> CreateMessageResponse:
        
        message_content = serialize_json({"text": content})
        
        request_body_builder = CreateMessageRequestBody.builder()
        request_body_builder = request_body_builder.receive_id(receive_id)
        request_body_builder = request_body_builder.content(message_content)
        request_body_builder = request_body_builder.msg_type(msg_type)
        request_body = request_body_builder.build()
        
        request_builder = CreateMessageRequest.builder()
        request_builder = request_builder.receive_id_type(receive_id_type)
        request_builder = request_builder.request_body(request_body)
        request = request_builder.build()
        
        assert self._lark_client.im
        create_message_result = self._lark_client.im.v1.message.create(request)
        return create_message_result
