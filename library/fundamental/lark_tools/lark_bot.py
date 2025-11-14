from ..typing import *
from ..externals import *
from ._lark_sdk import *
from ..json_tools import *
from ..backoff_decorators import *


__all__ = [
    "get_lark_bot_token",
    "get_lark_document_url",
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


def get_lark_document_url(
    tenant: str,
    document_id: str,
)-> str:
    
    lark_document_url = f"https://{tenant}.feishu.cn/docx/{document_id}?from=from_copylink\\"
    return lark_document_url


never_used_string = f"114514_{get_time_stamp(show_minute=True, show_second=True)}"
class LarkBot:
    
    text_block_type = 2
    first_heading_block_type = 3
    second_heading_block_type = 4
    third_heading_block_type = 5
    divider_block_type = 22
    image_block_type = 27
    
    image_placeholder = f"<image_{never_used_string}>"
    divider_placeholder = f"<divider_{never_used_string}>"
    begin_of_hyperlink = f"<hyperlink_{never_used_string}>"
    end_of_hyperlink = f"</hyperlink_{never_used_string}>"
    begin_of_equation = f"<equation_{never_used_string}>"
    end_of_equation = f"</equation_{never_used_string}>"
    begin_of_first_heading = f"<first_heading_{never_used_string}>"
    end_of_first_heading = f"</first_heading_{never_used_string}>"
    begin_of_second_heading = f"<second_heading_{never_used_string}>"
    end_of_second_heading = f"</second_heading_{never_used_string}>"
    begin_of_third_heading = f"<third_heading_{never_used_string}>"
    end_of_third_heading = f"</third_heading_{never_used_string}>"
    
    create_document_backoff_seconds = [1.0] * 32 + [2.0] * 32 + [4.0] * 32 + [8.0] * 32
    overwrite_document_backoff_seconds = [1.0] * 32 + [2.0] * 32 + [4.0] * 32 + [8.0] * 32
    delete_file_backoff_seconds = [1.0] * 32 + [2.0] * 32 + [4.0] * 32 + [8.0] * 32
    
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
        
        self._text_elements_pattern = re.compile((
            f"({re.escape(self.begin_of_equation)}"
            f".*?"
            f"{re.escape(self.end_of_equation)})"
        ))
        img_pattern = f"({re.escape(self.image_placeholder)})"
        divider_pattern = f"({re.escape(self.divider_placeholder)})"
        h1_pattern = (
            f"({re.escape(self.begin_of_first_heading)}"
            f".*?"
            f"{re.escape(self.end_of_first_heading)})"
        )
        h2_pattern = (
            f"({re.escape(self.begin_of_second_heading)}"
            f".*?"
            f"{re.escape(self.end_of_second_heading)})"
        )
        h3_pattern = (
            f"({re.escape(self.begin_of_third_heading)}"
            f".*?"
            f"{re.escape(self.end_of_third_heading)})"
        )
        self._document_blocks_pattern = re.compile(
            f"{img_pattern}|{divider_pattern}|{h1_pattern}|{h2_pattern}|{h3_pattern}"
        )
    

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
        
        if chat_type == "group":
            if message.event.message.root_id:
                thread_root_id = message.event.message.root_id
                is_thread_root = False
            else:
                thread_root_id = message_id
                is_thread_root = True
        else:
            thread_root_id = None
            is_thread_root = False
        
        try:
            message_content_dict = deserialize_json(message_content)
        except Exception:
            return {"success": False, "error": "反序列化 message_content 失败"}
        
        try:
            mention_list = message.event.message.mentions
            assert mention_list
        except:
            mention_list = [] 
        mentioned_me = any(
            mention.id.open_id == self._open_id
            for mention in mention_list
            if mention.id is not None
        )

        message_content_dict_keys = set(key for key in message_content_dict)
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
                "hyperlinks": [],
                "mentioned_me": mentioned_me,
                "message_content_dict": message_content_dict,
            }
            return parse_message_result
        
        elif message_content_dict_keys == set(["title", "content"]):
            text = ""
            image_keys = []
            hyperlinks = []
            content_lines = message_content_dict["content"]
            for index, line_elements in enumerate(content_lines):
                if index: text += "\n"
                for line_element in line_elements:
                    tag = line_element["tag"]
                    if tag == "text":
                        text += line_element["text"]
                    elif tag == "img":
                        text += self.image_placeholder
                        image_key = line_element["image_key"]
                        image_keys.append(image_key)
                    elif tag == "a":
                        text += self.begin_of_hyperlink + line_element["text"] + self.end_of_hyperlink
                        hyperlink = line_element["href"]
                        hyperlinks.append(hyperlink)
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
                "hyperlinks": [],
                "mentioned_me": mentioned_me,
                "message_content_dict": message_content_dict,
            }
            return parse_message_result
        
        elif message_content_dict_keys == set(["file_key", "file_name"]):
            file_key = message_content_dict["file_key"]
            file_name = message_content_dict["file_name"]
            parse_message_result = {
                "success": True,
                "message_type": "single_file",
                "message_id": message_id,
                "thread_root_id": thread_root_id,
                "is_thread_root": is_thread_root,
                "chat_type": chat_type,
                "text": "",
                "image_keys": [],
                "hyperlinks": [],
                "mentioned_me": mentioned_me,
                "message_content_dict": message_content_dict,
                "file_key": file_key,
                "file_name": file_name,
            }
            return parse_message_result
        
        else:
            return {
                "success": False, 
                "error": f"message_content 不合预期，包含字段：{', '.join(message_content_dict_keys)}"
            }
    
    
    def _build_get_message_resource_request(
        self,
        message_id: str,
        resource_key: str,
        resource_type: Literal["image", "file"],
    )-> GetMessageResourceRequest:
        
        request_builder = GetMessageResourceRequest.builder()
        request_builder = request_builder.message_id(message_id)
        request_builder = request_builder.file_key(resource_key)
        request_builder = request_builder.type(resource_type)
        request = request_builder.build()
        return request
    
    
    def get_message_resource(
        self,
        message_id: str,
        resource_key: str,
        resource_type: Literal["image", "file"],
    )-> Any:

        request = self._build_get_message_resource_request(
            message_id = message_id,
            resource_key = resource_key,
            resource_type = resource_type,
        )
        assert self._lark_client.im
        get_message_resource_result = self._lark_client.im.v1.message_resource.get(request)
        return get_message_resource_result
    
    
    async def get_message_resource_async(
        self,
        message_id: str,
        resource_key: str,
        resource_type: Literal["image", "file"],
    )-> Any:
        
        request = self._build_get_message_resource_request(
            message_id = message_id,
            resource_key = resource_key,
            resource_type = resource_type,
        )
        assert self._lark_client.im
        get_message_resource_result = await self._lark_client.im.v1.message_resource.aget(request)
        return get_message_resource_result
    
    
    async def download_message_images(
        self,
        message_id: str,
        image_keys: List[str],
    )-> List[bytes]:
        
        image_bytes_list: List[bytes] = []
        if image_keys:
            task_inputs: List[Tuple[Any, ...]] = [
                (message_id, image_key, "image") 
                for image_key in image_keys
            ]
            results_dict = await run_tasks_concurrently_async(
                task = self.get_message_resource_async,
                task_indexers = image_keys,
                task_inputs = task_inputs,
                show_progress_bar = False,
            )
            for image_key in image_keys:
                result = results_dict[image_key]
                if not result.success():
                    raise RuntimeError(
                        f"下载图片资源 {image_key} 失败: {result.code}, {result.msg}"
                    )
                image_bytes_list.append(result.file.read())
        return image_bytes_list
    
    
    def _build_reply_message_request(
        self,
        response: str,
        message_id: str,
        reply_in_thread: bool,
        image_keys: List[str],
        hyperlinks: List[str],
    )-> ReplyMessageRequest:
        
        image_count = response.count(self.image_placeholder)
        assert image_count == len(image_keys), (
            f"图片占位符数量 ({image_count}) "
            f"与 image_keys 列表长度 ({len(image_keys)}) 不匹配"
        )
        link_begin_count = response.count(self.begin_of_hyperlink)
        link_end_count = response.count(self.end_of_hyperlink)
        assert link_begin_count == link_end_count, (
            f"超链接开始标记 ({link_begin_count}) "
            f"和结束标记 ({link_end_count}) 数量不匹配"
        )
        assert link_begin_count == len(hyperlinks), (
            f"超链接标记数量 ({link_begin_count}) "
            f"与 hyperlinks 列表长度 ({len(hyperlinks)}) 不匹配"
        )

        image_key_iter = iter(image_keys)
        hyperlink_iter = iter(hyperlinks)
        
        image_pattern = f"({re.escape(self.image_placeholder)})"
        hyperlink_pattern = (
            f"({re.escape(self.begin_of_hyperlink)}"
            f".*?"
            f"{re.escape(self.end_of_hyperlink)})"
        )
        combined_pattern = re.compile(f"{image_pattern}|{hyperlink_pattern}")
        line_elements_list: List[List[Dict[str, Any]]] = []
        for content_line in response.split("\n"):
            line_elements: List[Dict[str, Any]] = []
            parts: List[str] = combined_pattern.split(content_line)
            for part in parts:
                if not part: continue
                if part == self.image_placeholder:
                    line_elements.append({
                        "tag": "img",
                        "image_key": next(image_key_iter)
                    })
                elif part.startswith(self.begin_of_hyperlink):
                    start_len = len(self.begin_of_hyperlink)
                    end_len = len(self.end_of_hyperlink)
                    link_text = part[start_len:-end_len]
                    line_elements.append({
                        "tag": "a",
                        "text": link_text,
                        "href": next(hyperlink_iter)
                    })
                else:
                    line_elements.append({
                        "tag": "text",
                        "text": part
                    })
            line_elements_list.append(line_elements)

        post_i18n_content = {
            "title": "", 
            "content": line_elements_list
        }
        post_content_body = {
            "zh_cn": post_i18n_content,
            "en_us": post_i18n_content,
        }
        reply_content = serialize_json(post_content_body)
        
        request_body_builder = ReplyMessageRequestBody.builder()
        request_body_builder = request_body_builder.content(reply_content)
        request_body_builder = request_body_builder.msg_type("post")
        request_body_builder = request_body_builder.reply_in_thread(reply_in_thread)
        request_body = request_body_builder.build()
        
        request_builder = ReplyMessageRequest.builder()
        request_builder = request_builder.request_body(request_body)
        request_builder = request_builder.message_id(message_id)
        request = request_builder.build()
        
        return request
    
    
    def reply_message(
        self,
        response: str,
        message_id: str,
        reply_in_thread: bool = False,
        image_keys: List[str] = [],
        hyperlinks: List[str] = [],
    )-> ReplyMessageResponse:
        
        request = self._build_reply_message_request(
            response = response, 
            message_id = message_id, 
            reply_in_thread = reply_in_thread, 
            image_keys = image_keys, 
            hyperlinks = hyperlinks,
        )
        assert self._lark_client.im
        reply_message_result = self._lark_client.im.v1.message.reply(request)
        return reply_message_result
    
    
    async def reply_message_async(
        self,
        response: str,
        message_id: str,
        reply_in_thread: bool = False,
        image_keys: List[str] = [],
        hyperlinks: List[str] = [],
    )-> ReplyMessageResponse:
        
        request = self._build_reply_message_request(
            response = response, 
            message_id = message_id,
            reply_in_thread = reply_in_thread, 
            image_keys = image_keys, 
            hyperlinks = hyperlinks,
        )
        assert self._lark_client.im
        reply_message_result = await self._lark_client.im.v1.message.areply(request)
        return reply_message_result
    
    
    def _build_send_message_request(
        self,
        receive_id_type: Literal["chat_id", "open_id", "user_id"],
        receive_id: str,
        content: str,
    )-> CreateMessageRequest:
        
        message_content = serialize_json({"text": content})
        
        request_body_builder = CreateMessageRequestBody.builder()
        request_body_builder = request_body_builder.receive_id(receive_id)
        request_body_builder = request_body_builder.content(message_content)
        request_body_builder = request_body_builder.msg_type("text")
        request_body = request_body_builder.build()
        
        request_builder = CreateMessageRequest.builder()
        request_builder = request_builder.receive_id_type(receive_id_type)
        request_builder = request_builder.request_body(request_body)
        request = request_builder.build()
        
        return request
    
    
    def send_message(
        self,
        receive_id_type: Literal["chat_id", "open_id", "user_id"],
        receive_id: str,
        content: str,
    )-> CreateMessageResponse:
        
        request = self._build_send_message_request(
            receive_id_type = receive_id_type,
            receive_id = receive_id,
            content = content,
        )
        assert self._lark_client.im
        create_message_result = self._lark_client.im.v1.message.create(request)
        return create_message_result
    
    
    async def send_message_async(
        self,
        receive_id_type: Literal["chat_id", "open_id", "user_id"],
        receive_id: str,
        content: str,
    )-> CreateMessageResponse:

        request = self._build_send_message_request(
            receive_id_type = receive_id_type,
            receive_id = receive_id,
            content = content,
        )
        assert self._lark_client.im
        create_message_result = await self._lark_client.im.v1.message.acreate(request)
        return create_message_result
    
    
    # https://open.feishu.cn/document/server-docs/docs/docs/docx-v1/document/create?appId=cli_a98f4b47a778100c
    def _build_create_document_request(
        self,
        title: str,
        folder_token: str,
    )-> CreateDocumentRequest:
        
        request_body_builder = CreateDocumentRequestBody.builder()
        request_body_builder = request_body_builder.title(title)
        request_body_builder = request_body_builder.folder_token(folder_token)
        request_body = request_body_builder.build()
        request_builder = CreateDocumentRequest.builder()
        request_builder = request_builder.request_body(request_body)
        request = request_builder.build()
        return request
    
    
    @backoff(create_document_backoff_seconds)
    def create_document(
        self,
        title: str,
        folder_token: str,
    )-> str:
        
        request = self._build_create_document_request(
            title = title,
            folder_token = folder_token,
        )
        assert self._lark_client.docx
        create_document_result = self._lark_client.docx.v1.document.create(request)
        if create_document_result.success():
            assert create_document_result.data
            assert create_document_result.data.document
            assert create_document_result.data.document.document_id
            return create_document_result.data.document.document_id
        else:
            raise RuntimeError
    
    
    @backoff_async(create_document_backoff_seconds)
    async def create_document_async(
        self,
        title: str,
        folder_token: str,
    )-> str:
        
        request = self._build_create_document_request(
            title = title,
            folder_token = folder_token,
        )
        assert self._lark_client.docx
        create_document_result = await self._lark_client.docx.v1.document.acreate(request)
        if create_document_result.success():
            assert create_document_result.data
            assert create_document_result.data.document
            assert create_document_result.data.document.document_id
            return create_document_result.data.document.document_id
        else:
            raise RuntimeError
    
    
    def build_text_elements(
        self,
        content: str,
    )-> List[TextElement]:
        
        elements: List[TextElement] = []
        parts: List[str] = self._text_elements_pattern.split(content)
        for part in parts:
            if not part: continue
            if part.startswith(self.begin_of_equation):
                eq_content = part[len(self.begin_of_equation):-len(self.end_of_equation)]
                equation = Equation.builder().content(eq_content).build()
                text_element = TextElement.builder().equation(equation).build()
                elements.append(text_element)
            else:
                text_run = TextRun.builder().content(part).build()
                text_element = TextElement.builder().text_run(text_run).build()
                elements.append(text_element)
        
        if not elements:
            elements = [TextElement.builder().text_run(TextRun.builder().content("").build()).build()]
            
        return elements
    
    
    def build_text_block(
        self,
        content: str,
    )-> Block:
        
        elements = self.build_text_elements(
            content = content,
        )
        
        text = Text.builder().elements(elements).build()
        block = Block.builder().block_type(self.text_block_type).text(text).build()
        return block

    
    def build_heading_block(
        self,
        content: str,
        level: int,
    )-> Block:
        
        elements = self.build_text_elements(
            content = content,
        )
        text = Text.builder().elements(elements).build()
        if level == 1:
            block = Block.builder().block_type(self.first_heading_block_type).heading1(text).build()
            return block
        elif level == 2:
            block = Block.builder().block_type(self.second_heading_block_type).heading2(text).build()
            return block
        elif level == 3:
            block = Block.builder().block_type(self.third_heading_block_type).heading3(text).build()
            return block
        else:
            raise NotImplementedError

    
    def build_image_block(
        self,
        image_key: str,
    )-> Block:
        
        image = Image.builder().token(image_key).build()
        block = Block.builder().block_type(self.image_block_type).image(image).build()
        return block
    
    
    def build_divider_block(
        self,
    )-> Block:
        
        divider = Divider.builder().build()
        block = Block.builder().block_type(self.divider_block_type).divider(divider).build()
        return block
    
    
    def build_document_blocks(
        self,
        content: str,
        image_keys: List[str] = [],
    )-> List[Block]:
        
        image_key_iter = iter(image_keys)
        blocks: List[Block] = []
        
        parts: List[str] = self._document_blocks_pattern.split(content)
        for part in parts:
            if not part: continue
            # image
            if part == self.image_placeholder:
                try:
                    key = next(image_key_iter)
                    blocks.append(self.build_image_block(key))
                except StopIteration:
                    print(f"[LarkBot] 警告: 发现图片占位符，但 image_keys 已耗尽")
                    blocks.append(self.build_text_block("[图片加载失败]"))
            elif part == self.divider_placeholder:
                print("发现分隔线")
                blocks.append(self.build_divider_block())
            # H1 title
            elif part.startswith(self.begin_of_first_heading):
                text = part[len(self.begin_of_first_heading):-len(self.end_of_first_heading)]
                blocks.append(self.build_heading_block(text, level=1))
            # H2 title
            elif part.startswith(self.begin_of_second_heading):
                text = part[len(self.begin_of_second_heading):-len(self.end_of_second_heading)]
                blocks.append(self.build_heading_block(text, level=2))
            # H3 title
            elif part.startswith(self.begin_of_third_heading):
                text = part[len(self.begin_of_third_heading):-len(self.end_of_third_heading)]
                blocks.append(self.build_heading_block(text, level=3))
            # text (possibly including equations)
            else:
                blocks.append(self.build_text_block(part))
        
        return blocks
    
    
    @backoff_async(overwrite_document_backoff_seconds)
    async def overwrite_document_async(
        self,
        document_id: str,
        blocks: List[Block],
    )-> None:
        
        document_root_block_id = document_id
        assert self._lark_client.docx

        while True:
            delete_body_builder = BatchDeleteDocumentBlockChildrenRequestBody.builder()
            delete_body_builder = delete_body_builder.start_index(0)
            delete_body_builder = delete_body_builder.end_index(500)
            delete_request_body = delete_body_builder.build()
            delete_request_builder = BatchDeleteDocumentBlockChildrenRequest.builder()
            delete_request_builder = delete_request_builder.document_id(document_id)
            delete_request_builder = delete_request_builder.block_id(document_root_block_id)
            delete_request_builder = delete_request_builder.request_body(delete_request_body)
            delete_request = delete_request_builder.build()
            delete_response = await self._lark_client.docx.v1.document_block_children.abatch_delete(delete_request)
            if not delete_response.success(): break
        
        if not blocks: return None
        insert_body_builder = CreateDocumentBlockChildrenRequestBody.builder()
        insert_body_builder = insert_body_builder.children(blocks)
        insert_body_builder = insert_body_builder.index(0)
        insert_request_body = insert_body_builder.build()

        insert_request_builder = CreateDocumentBlockChildrenRequest.builder()
        insert_request_builder = insert_request_builder.document_id(document_id)
        insert_request_builder = insert_request_builder.block_id(document_root_block_id) 
        insert_request_builder = insert_request_builder.request_body(insert_request_body)
        insert_request = insert_request_builder.build()
        
        insert_response = await self._lark_client.docx.v1.document_block_children.acreate(insert_request)
        
        if not insert_response.success():
            raise RuntimeError(f"Failed to insert new blocks: {insert_response.code} {insert_response.msg}")

        return None
    
    
    def _build_delete_file_request(
        self,
        file_token: str,
        file_type: Literal["file", "docx", "sheet", "bitable", "folder"],
    )-> DeleteFileRequest:
        
        request_builder = DeleteFileRequest.builder()
        request_builder = request_builder.type(file_type)
        request_builder = request_builder.file_token(file_token)
        request = request_builder.build()
        return request
    
    
    @backoff(delete_file_backoff_seconds)
    def delete_file(
        self,
        file_token: str,
        file_type: Literal["docx", "sheet", "bitable", "folder", "file"] = "docx",
    )-> None:
        
        request = self._build_delete_file_request(
            file_token = file_token,
            file_type = file_type,
        )
        assert self._lark_client.drive
        delete_file_response = self._lark_client.drive.v1.file.delete(request)
        if not delete_file_response.success():
            raise RuntimeError
        else:
            return None
    
    
    @backoff_async(delete_file_backoff_seconds)
    async def delete_file_async(
        self,
        file_token: str,
        file_type: Literal["docx", "sheet", "bitable", "folder", "file"] = "docx",
    )-> None:
        
        request = self._build_delete_file_request(
            file_token = file_token,
            file_type = file_type,
        )
        
        assert self._lark_client.drive
        delete_file_response = await self._lark_client.drive.v1.file.adelete(request)
        if not delete_file_response.success():
            raise RuntimeError
        else:
            return None