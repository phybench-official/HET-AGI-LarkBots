from ..typing import *
from ..externals import *
from ._lark_sdk import *
from ..json_tools import *
from ..backoff_decorators import *
from ..image_tools import *
from ..yaml_tools import *


__all__ = [
    "get_lark_document_url",
    "LarkBot",
    "P2ImMessageReceiveV1",
    "ReplyMessageResponse",
]


def get_lark_document_url(
    tenant: str,
    document_id: str,
)-> str:
    
    lark_document_url = f"https://{tenant}.feishu.cn/docx/{document_id}"
    return lark_document_url


never_used_string = f"never_used"
class LarkBot:
    
    text_block_type = 2
    first_heading_block_type = 3
    second_heading_block_type = 4
    third_heading_block_type = 5
    forth_heading_block_type = 6
    fifth_heading_block_type = 7
    list_block_type = 12
    code_block_type = 14
    divider_block_type = 22
    image_block_type = 27
    
    language_text_style = {
        "Plain Text": 0,
        "Python": 9,
    }
    
    image_placeholder = f"<image_{never_used_string}>"
    divider_placeholder = f"<divider_{never_used_string}>"
    begin_of_hyperlink = f"<hyperlink_{never_used_string}>"
    end_of_hyperlink = f"</hyperlink_{never_used_string}>"
    begin_of_equation = f"<equation_{never_used_string}>"
    end_of_equation = f"</equation_{never_used_string}>"
    begin_of_bold = f"<bold_{never_used_string}>"
    end_of_bold = f"</bold_{never_used_string}>"
    begin_of_first_heading = f"<first_heading_{never_used_string}>"
    end_of_first_heading = f"</first_heading_{never_used_string}>"
    begin_of_second_heading = f"<second_heading_{never_used_string}>"
    end_of_second_heading = f"</second_heading_{never_used_string}>"
    begin_of_third_heading = f"<third_heading_{never_used_string}>"
    end_of_third_heading = f"</third_heading_{never_used_string}>"
    begin_of_forth_heading = f"<forth_heading_{never_used_string}>"
    end_of_forth_heading = f"</forth_heading_{never_used_string}>"
    begin_of_fifth_heading = f"<fifth_heading_{never_used_string}>"
    end_of_fifth_heading = f"</fifth_heading_{never_used_string}>"
    begin_of_code = f"<code_{never_used_string}>"
    end_of_code = f"</code_{never_used_string}>"
    begin_of_language = f"<language_{never_used_string}>"
    end_of_language = f"</language_{never_used_string}>"
    begin_of_content = f"<content_{never_used_string}>"
    end_of_content = f"</content_{never_used_string}>"
    
    document_blocks_pattern = re.compile(
        # image
        f"({re.escape(image_placeholder)})|"
        # divider
        f"({re.escape(divider_placeholder)})|"
        # first heading
        f"({re.escape(begin_of_first_heading)}"
        f".*?"
        f"{re.escape(end_of_first_heading)})|"
        # second heading
        f"({re.escape(begin_of_second_heading)}"
        f".*?"
        f"{re.escape(end_of_second_heading)})|"
        # third heading
        f"({re.escape(begin_of_third_heading)}"
        f".*?"
        f"{re.escape(end_of_third_heading)})|"
        # forth heading
        f"({re.escape(begin_of_forth_heading)}"
        f".*?"
        f"{re.escape(end_of_forth_heading)})|"
        # fifth heading
        f"({re.escape(begin_of_fifth_heading)}"
        f".*?"
        f"{re.escape(end_of_fifth_heading)})|"
        # code
        f"({re.escape(begin_of_code)}"
        f".*?"
        f"{re.escape(end_of_code)})",
        re.DOTALL,
    )
    text_elements_pattern = re.compile(
        # equation
        f"({re.escape(begin_of_equation)}"
        f".*?"
        f"{re.escape(end_of_equation)})|"
        # bold
        f"({re.escape(begin_of_bold)}"
        f".*?"
        f"{re.escape(end_of_bold)})",
        re.DOTALL,
    )
    code_pattern = re.compile(
        r"\s*"
        rf"{re.escape(begin_of_language)}([\s\S]*){re.escape(end_of_language)}"
        r"\s*"
        rf"{re.escape(begin_of_content)}([\s\S]*){re.escape(end_of_content)}"
        r"\s*"
    )
    
    create_document_backoff_seconds = [1.0] * 32 + [2.0] * 32 + [4.0] * 32 + [8.0] * 32
    overwrite_document_backoff_seconds = [1.0] * 32 + [2.0] * 32 + [4.0] * 32 + [8.0] * 32
    append_document_blocks_backoff_seconds = [1.0] * 32 + [2.0] * 32 + [4.0] * 32 + [8.0] * 32
    delete_file_backoff_seconds = [1.0] * 32 + [2.0] * 32 + [4.0] * 32 + [8.0] * 32
    
    _spawned_processes: List[multiprocessing.Process] = []
    _process_lock: threading.Lock = threading.Lock()
    
    def __init__(
        self,
        config_path: str,
        image_cache_size: int = 128,
    )-> None:
        
        self._init_arguments: Dict[str, Any] = {
            "config_path": config_path,
            "image_cache_size": image_cache_size,
        }
        
        self._load_config(config_path)
        
        lark_client_builder = lark.Client.builder()
        lark_client_builder = lark_client_builder.app_id(
            app_id = self._config["app_id"],
        )
        lark_client_builder = lark_client_builder.app_secret(
            app_secret = self._config["app_secret"],
        )
        lark_client_builder = lark_client_builder.log_level(lark.LogLevel.INFO)
        self._lark_client = lark_client_builder.build()

        self._event_handler_builder = lark.EventDispatcherHandler.builder(
            encrypt_key = "",
            verification_token = "",
            level = lark.LogLevel.DEBUG,
        )
        
        # TODO: 改造这里，使之支持加粗（bold）
        # 并且正则的编译移到类公有的里面，使得避免不同类反复编译
        
        
        self._image_cache_size = image_cache_size
        self._image_cache: OrderedDict[str, bytes] = OrderedDict()
        self._image_cache_lock = asyncio.Lock()
    
    
    def _load_config(
        self,
        config_path: str,
    )-> None:
        
        self._config = load_from_yaml(config_path)
        self._config_path = config_path
        
        
    async def _reload_config_async(
        self,
        config_path: str,
    )-> str:

        try:
            new_config, new_config_content = await load_from_yaml_async(
                file_path = config_path,
            )
            self._config = new_config
            self._config_path = config_path
            return new_config_content
        except Exception as error:
            return f"配置更新失败！\n错误信息:\n{str(error)}\n调用栈：\n{traceback.format_exc()}"
    
    
    @staticmethod
    def _run_in_process(
        bot_class: type,
        init_args: Dict[str, Any],
    )-> None:
        """
        [静态方法] 此方法在独立的子进程中执行。
        它重新实例化 Bot，并调用其内部启动逻辑。
        """
        bot_name = init_args.get("lark_bot_name", "UnknownBot")
        print(f"[Process-{os.getpid()}] Starting bot: {bot_name}")
        
        try:
            bot_instance = bot_class(**init_args)
            bot_instance._start_internal_logic()
        except KeyboardInterrupt:
            print(f"[Process-{os.getpid()}] Shutdown signal for {bot_name}")
        except Exception as e:
            print(f"[Process-{os.getpid()}] Bot {bot_name} crashed: {e}\n{traceback.format_exc()}")
    

    def _start_internal_logic(
        self
    )-> None:
        """
        [实例方法] 内部的、真正的机器人启动逻辑。
        子类 (如 ParallelThreadLarkBot) 应该覆盖此方法以添加它们的特定逻辑
        (例如，启动它们自己的异步工作线程)。
        
        这是 LarkBot 原始的 start() 方法的内容。
        """
        print(f"[LarkBot-{self._config['name']}] Starting synchronous Lark WS client (blocking process)...")
        event_handler = self._event_handler_builder.build()
        lark.ws.Client(
            app_id = self._config["app_id"],
            app_secret = self._config["app_secret"],
            event_handler = event_handler,
            log_level = lark.LogLevel.DEBUG
        ).start()
        print(f"[LarkBot-{self._config['name']}] WS client shut down.")
    
    
    def start(
        self,
        block: bool = False,
    )-> None:
        """
        [主进程] 启动 Bot。
        
        启动器：此方法现在在子进程中启动 Bot 的实际工作负载，
        以规避 lark.ws.Client 的全局状态限制。
        
        :param block: 
          - False (默认): 启动子进程并立即返回 (非阻塞)。
          - True: 启动子进程，然后阻塞主线程以等待 Ctrl+C。
            收到 Ctrl+C 时，将终止所有已启动的 Bot 进程。
        """
        
        proc = multiprocessing.Process(
            target = self._run_in_process,
            args = (
                self.__class__,
                self._init_arguments,
            ),
            daemon = False,
        )
        
        with self._process_lock:
            self._spawned_processes.append(proc)
        
        proc.start()
        print(f"[Main] Started process {proc.pid} for {self._config['name']}")

        if block:
            print("[Main] All bot processes started. MainThread is waiting (Press Ctrl+C to exit).")
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\n[Main] Shutdown signal received. Terminating bot processes.")
                with self._process_lock:
                    for process in self._spawned_processes:
                        if process.is_alive():
                            process.terminate()
                    for process in self._spawned_processes:
                        process.join()
                print("[Main] All processes terminated.")
        else:
            return
    
    
    def register_message_receive(
        self,
        handler: Callable[[P2ImMessageReceiveV1], None],
    )-> None:
        
        self._event_handler_builder.register_p2_im_message_receive_v1(handler)
        
    
    def register_user_created(
        self,
        handler: Callable[[P2ContactUserCreatedV3], None],
    )-> None:
        
        self._event_handler_builder.register_p2_contact_user_created_v3(handler)
    
    
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
            assert message.event.sender
            assert message.event.sender.sender_id
            sender = message.event.sender.sender_id.open_id
        except:
            sender = None
        
        if message.event.message.root_id:
            thread_root_id = message.event.message.root_id
            is_thread_root = False
        else:
            thread_root_id = message_id
            is_thread_root = True
        
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
            mention.id.open_id == self._config["open_id"]
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
                "sender": sender,
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
                "sender": sender,
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
                "sender": sender,
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
                "sender": sender,
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
    
    
    def download_message_images(
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
            results_dict = run_tasks_concurrently(
                task = self.get_message_resource,
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
    
    
    async def download_message_images_async(
        self,
        message_id: str,
        image_keys: List[str],
    )-> List[bytes]:
        
        if not image_keys: return []
        
        missing_keys: List[str] = []
        async with self._image_cache_lock:
            for key in image_keys:
                if key in self._image_cache:
                    self._image_cache.move_to_end(key)
                else:
                    missing_keys.append(key)
        
        if missing_keys:
            task_inputs: List[Tuple[Any, ...]] = [
                (message_id, image_key, "image") 
                for image_key in missing_keys
            ]
            results_dict = await run_tasks_concurrently_async(
                task = self.get_message_resource_async,
                task_indexers = missing_keys,
                task_inputs = task_inputs,
                show_progress_bar = False,
            )
            async with self._image_cache_lock:
                for image_key in missing_keys:
                    result = results_dict[image_key]
                    if not result.success():
                        raise RuntimeError(
                            f"下载图片资源 {image_key} 失败: {result.code}, {result.msg}"
                        )
                    image_data = result.file.read()
                    self._image_cache[image_key] = image_data
                    self._image_cache.move_to_end(image_key)
                while len(self._image_cache) > self._image_cache_size:
                    self._image_cache.popitem(last=False)

        final_images: List[bytes] = []
        async with self._image_cache_lock:
            for key in image_keys:
                if key in self._image_cache:
                    final_images.append(self._image_cache[key])
                else:
                    raise RuntimeError(f"Cache miss during assembly for {key}")
              
        return final_images
    
    
    def _build_create_image_request(
        self,
        image_type: str,
        image: bytes,
    )-> CreateImageRequest:
        
        request_body_builder = CreateImageRequestBody.builder()
        request_body_builder = request_body_builder.image_type(image_type)
        request_body_builder = request_body_builder.image(io.BytesIO(image))
        request_body = request_body_builder.build()
        request_builder = CreateImageRequest.builder()
        request_builder = request_builder.request_body(request_body)
        request = request_builder.build()
        return request
    
    
    def create_image(
        self,
        image_type: str,
        image: Any,
    )-> str:
        
        image = align_image_to_bytes(image)
        request = self._build_create_image_request(
            image_type = image_type,
            image = image,
        )
        assert self._lark_client.im
        create_image_result = self._lark_client.im.v1.image.create(request)
        if not create_image_result.success():
            raise RuntimeError
        else:
            assert create_image_result.data
            assert create_image_result.data.image_key
            return create_image_result.data.image_key
        
        
    async def create_image_async(
        self,
        image_type: str,
        image: Any,
    )-> str:
        
        image = await align_image_to_bytes_async(image)
        request = self._build_create_image_request(
            image_type = image_type,
            image = image,
        )
        assert self._lark_client.im
        create_image_result = await self._lark_client.im.v1.image.acreate(request)
        if not create_image_result.success():
            raise RuntimeError
        else:
            assert create_image_result.data
            assert create_image_result.data.image_key
            return create_image_result.data.image_key
    
    
    def _check_reply_message_input(
        self,
        response: str,
        images: List[bytes],
        hyperlinks: List[str],
    )-> None:
        
        image_count = response.count(self.image_placeholder)
        assert image_count == len(images), (
            f"图片占位符数量 ({image_count}) "
            f"与 images 列表长度 ({len(images)}) 不匹配"
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
    
    
    def _build_reply_message_request(
        self,
        response: str,
        message_id: str,
        reply_in_thread: bool,
        image_keys: List[str],
        hyperlinks: List[str],
    )-> ReplyMessageRequest:
        
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
        images: List[bytes] = [],
        hyperlinks: List[str] = [],
    )-> ReplyMessageResponse:
        
        self._check_reply_message_input(
            response = response,
            images = images,
            hyperlinks = hyperlinks,
        )
        
        image_keys = []
        if images:
            image_type = "message"
            create_image_results = run_tasks_concurrently(
                task = self.create_image,
                task_indexers = list(range(len(images))),
                task_inputs = [(image_type, image) for image in images],
                show_progress_bar = False,
            )
            for index in range(len(images)):
                image_keys.append(create_image_results[index])
        
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
        images: List[Any] = [],
        hyperlinks: List[str] = [],
    )-> ReplyMessageResponse:
        
        self._check_reply_message_input(
            response = response,
            images = images,
            hyperlinks = hyperlinks,
        )
        
        image_keys = []
        if images:
            image_type = "message"
            create_image_results = await run_tasks_concurrently_async(
                task = self.create_image_async,
                task_indexers = list(range(len(images))),
                task_inputs = [(image_type, image) for image in images],
                show_progress_bar = False,
            )
            for index in range(len(images)):
                image_keys.append(create_image_results[index])
        
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
    
    
    # https://open.feishu.cn/document/server-docs/docs/drive-v1/media/introduction
    def _build_upload_image_for_document_request(
        self,
        image: bytes,
        document_id: str,
        block_id: str,
    )-> UploadAllMediaRequest:
        
        request_body_builder = UploadAllMediaRequestBody.builder()
        request_body_builder = request_body_builder.file(io.BytesIO(image))
        request_body_builder = request_body_builder.file_name(
            f"{get_time_stamp(show_minute=True, show_second=True)}.png"
        )
        request_body_builder = request_body_builder.size(len(image))
        request_body_builder = request_body_builder.parent_node(block_id)
        request_body_builder = request_body_builder.parent_type("docx_image")
        request_body_builder = request_body_builder.extra(
            serialize_json({"drive_route_token": document_id})
        )
        request_body = request_body_builder.build()
        
        request_builder = UploadAllMediaRequest.builder()
        request_builder = request_builder.request_body(request_body)
        request = request_builder.build()
        
        return request
    
    
    def upload_image_for_document(
        self,
        image: Any,
        document_id: str,
        block_id: str,
    )-> str:
        
        image = align_image_to_bytes(image)
        request = self._build_upload_image_for_document_request(
            image = image,
            document_id = document_id,
            block_id = block_id,
        )
        assert self._lark_client.drive
        create_image_result = self._lark_client.drive.v1.media.upload_all(request)
        if not create_image_result.success():
            raise RuntimeError
        else:
            assert create_image_result.data
            assert create_image_result.data.file_token
            return create_image_result.data.file_token
    
    
    def build_text_elements(
        self,
        content: str,
    )-> List[TextElement]:
        
        elements: List[TextElement] = []
        parts: List[str] = self.text_elements_pattern.split(content)
        for part in parts:
            if not part: continue
            # equation
            if part.startswith(self.begin_of_equation):
                eq_content = part[len(self.begin_of_equation):-len(self.end_of_equation)]
                eq_content = eq_content.strip()
                equation = Equation.builder().content(eq_content).build()
                text_element = TextElement.builder().equation(equation).build()
                elements.append(text_element)
            # bold
            elif part.startswith(self.begin_of_bold):
                text = part[len(self.begin_of_bold):-len(self.end_of_bold)]
                text_element_style = TextElementStyle.builder().bold(True).build()
                text_run = TextRun.builder().content(text).text_element_style(text_element_style).build()
                text_element = TextElement.builder().text_run(text_run).build()
                elements.append(text_element)
            # plain text
            else:
                text = part
                text_run = TextRun.builder().content(text).build()
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
    
    
    def build_code_block(
        self,
        content: str,
    )-> Block:
        
        code_pattern_match = self.code_pattern.fullmatch(content)
        assert code_pattern_match
        language = code_pattern_match.group(1)
        code_content = code_pattern_match.group(2)

        elements = self.build_text_elements(
            content = code_content,
        )
        
        text_style = TextStyle.builder().language(self.language_text_style[language]).build()
        text = Text.builder().elements(elements).style(text_style).build()
        block = Block.builder().block_type(self.code_block_type).code(text).build()
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
        elif level == 4:
            block = Block.builder().block_type(self.forth_heading_block_type).heading4(text).build()
            return block
        elif level == 5:
            block = Block.builder().block_type(self.fifth_heading_block_type).heading5(text).build()
            return block
        else:
            raise NotImplementedError

    
    # 幽默飞书，先传空块、再对块传素材、再更新云素材至块，这逻辑诗人握持
    def build_image_block(
        self,
        image_key: Optional[str] = None,
    )-> Block:
        
        image_builder = Image.builder()
        if image_key: image_builder = image_builder.token(image_key)
        image = image_builder.build()
        
        block_builder = Block.builder()
        block_builder = block_builder.block_type(self.image_block_type)
        block_builder = block_builder.image(image)
        block = block_builder.build()
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
    )-> List[Block]:
        
        blocks: List[Block] = []
        
        parts: List[str] = self.document_blocks_pattern.split(content)
        for part in parts:
            if not part: continue
            # image
            if part == self.image_placeholder:
                blocks.append(self.build_image_block())
            elif part == self.divider_placeholder:
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
            # H4 title
            elif part.startswith(self.begin_of_forth_heading):
                text = part[len(self.begin_of_forth_heading):-len(self.end_of_forth_heading)]
                blocks.append(self.build_heading_block(text, level=4))
            # H5 title
            elif part.startswith(self.begin_of_fifth_heading):
                text = part[len(self.begin_of_fifth_heading):-len(self.end_of_fifth_heading)]
                blocks.append(self.build_heading_block(text, level=5))
            # code
            elif part.startswith(self.begin_of_code):
                content = part[len(self.begin_of_code):-len(self.end_of_code)]
                blocks.append(self.build_code_block(content))
            # text
            else:
                blocks.append(self.build_text_block(part))
        
        return blocks
    
    
    async def upload_image_for_document_async(
        self,
        image: Any,
        document_id: str,
        block_id: str,
    )-> str:
        
        image = await align_image_to_bytes_async(image)
        request = self._build_upload_image_for_document_request(
            image = image,
            document_id = document_id,
            block_id = block_id,
        )
        assert self._lark_client.drive
        create_image_result = await self._lark_client.drive.v1.media.aupload_all(request)
        if not create_image_result.success():
            raise RuntimeError
        else:
            assert create_image_result.data
            assert create_image_result.data.file_token
            return create_image_result.data.file_token
    
    
    @backoff_async(overwrite_document_backoff_seconds)
    async def overwrite_document_async(
        self,
        document_id: str,
        blocks: List[Block],
        images: List[bytes],
        existing_block_num: Optional[int] = None,
    )-> None:
        
        document_root_block_id: str = document_id
        assert self._lark_client.docx
        
        first_deletion_attempt = False
        if existing_block_num is not None:
            delete_body_builder = BatchDeleteDocumentBlockChildrenRequestBody.builder()
            delete_body_builder = delete_body_builder.start_index(0)
            delete_body_builder = delete_body_builder.end_index(existing_block_num)
            delete_request_body = delete_body_builder.build()
            
            delete_request_builder = BatchDeleteDocumentBlockChildrenRequest.builder()
            delete_request_builder = delete_request_builder.document_id(document_id)
            delete_request_builder = delete_request_builder.block_id(document_root_block_id)
            delete_request_builder = delete_request_builder.request_body(delete_request_body)
            delete_request = delete_request_builder.build()
            
            delete_response = await self._lark_client.docx.v1.document_block_children.abatch_delete(delete_request)
            if delete_response.success(): first_deletion_attempt = True
        
        if first_deletion_attempt != True:
            while True:
                delete_body_builder = BatchDeleteDocumentBlockChildrenRequestBody.builder()
                delete_body_builder = delete_body_builder.start_index(0)
                delete_body_builder = delete_body_builder.end_index(1)
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
        insert_request_body: CreateDocumentBlockChildrenRequestBody = insert_body_builder.build()
        
        insert_request_builder = CreateDocumentBlockChildrenRequest.builder()
        insert_request_builder = insert_request_builder.document_id(document_id)
        insert_request_builder = insert_request_builder.block_id(document_root_block_id) 
        insert_request_builder = insert_request_builder.request_body(insert_request_body)
        insert_request = insert_request_builder.build()
        
        insert_response = await self._lark_client.docx.v1.document_block_children.acreate(insert_request)
        
        if not insert_response.success():
            raise RuntimeError(f"Failed to insert new blocks: {insert_response.code} {insert_response.msg}")
        
        assert insert_response.data
        assert insert_response.data.children
        created_blocks: List[Block] = insert_response.data.children

        image_block_ids: List[str] = []
        for block in created_blocks:
            if block.block_type == self.image_block_type:
                assert block.block_id is not None
                image_block_ids.append(block.block_id)
        if not images and not image_block_ids: return None

        if len(image_block_ids) != len(images):
            print(
                f"[LarkBot] 警告: 文档中创建了 {len(image_block_ids)} 个图片块, "
                f"但只提供了 {len(images)} 张图片。将只填充前面的图片。"
            )

        upload_tasks: List[Coroutine[Any, Any, str]] = []
        paired_uploads = zip(image_block_ids, images)
        for block_id, image_bytes in paired_uploads:
            task = self.upload_image_for_document_async(
                image = image_bytes,
                document_id = document_id,
                block_id = block_id,
            )
            upload_tasks.append(task)
        
        if not upload_tasks: return None

        image_tokens: List[str] = await asyncio.gather(*upload_tasks)
        update_requests: List[UpdateBlockRequest] = []
        valid_block_ids_to_update = image_block_ids[:len(image_tokens)]
        for block_id, image_token in zip(valid_block_ids_to_update, image_tokens):
            replace_image_req_builder = ReplaceImageRequest.builder()
            replace_image_req_builder = replace_image_req_builder.token(image_token)
            replace_image_req = replace_image_req_builder.build()
            update_req_builder = UpdateBlockRequest.builder()
            update_req_builder = update_req_builder.block_id(block_id)
            update_req_builder = update_req_builder.replace_image(replace_image_req)
            update_req = update_req_builder.build()
            update_requests.append(update_req)

        request_body_builder = BatchUpdateDocumentBlockRequestBody.builder()
        request_body_builder = request_body_builder.requests(update_requests)
        request_body = request_body_builder.build()
        
        batch_update_request_builder = BatchUpdateDocumentBlockRequest.builder()
        batch_update_request_builder = batch_update_request_builder.document_id(document_id)
        batch_update_request_builder = batch_update_request_builder.request_body(request_body)
        batch_update_request = batch_update_request_builder.build()
        
        assert self._lark_client.docx
        update_response = await self._lark_client.docx.v1.document_block.abatch_update(batch_update_request)
        
        if not update_response.success(): 
            print(f"[LarkBot] Failed to batch update image blocks: "
                f"{update_response.code} {update_response.msg}")
            raise RuntimeError

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
    
    
    @backoff_async(append_document_blocks_backoff_seconds)
    async def append_document_blocks_async(
        self,
        document_id: str,
        blocks: List[Block],
        images: List[bytes] = [],
    )-> None:
        
        if not blocks: return

        document_root_block_id = document_id
        assert self._lark_client.docx

        insert_body_builder = CreateDocumentBlockChildrenRequestBody.builder()
        insert_body_builder = insert_body_builder.children(blocks)
        insert_body_builder = insert_body_builder.index(-1)
        insert_request_body = insert_body_builder.build()
        
        insert_request_builder = CreateDocumentBlockChildrenRequest.builder()
        insert_request_builder = insert_request_builder.document_id(document_id)
        insert_request_builder = insert_request_builder.block_id(document_root_block_id)
        insert_request_builder = insert_request_builder.request_body(insert_request_body)
        insert_request = insert_request_builder.build()
        
        insert_response = await self._lark_client.docx.v1.document_block_children.acreate(insert_request)
        
        if not insert_response.success():
            raise RuntimeError(f"Failed to append blocks: {insert_response.code} {insert_response.msg}")
        
        assert insert_response.data
        assert insert_response.data.children
        created_blocks: List[Block] = insert_response.data.children

        image_block_ids: List[str] = []
        for block in created_blocks:
            if block.block_type == self.image_block_type:
                assert block.block_id is not None
                image_block_ids.append(block.block_id)
        if not images and not image_block_ids: return

        if len(image_block_ids) != len(images):
            print(f"[LarkBot] Warning: Appended {len(image_block_ids)} image blocks but provided {len(images)} images.")
        
        upload_tasks: List[Coroutine[Any, Any, str]] = []
        paired_uploads = zip(image_block_ids, images) 
        for block_id, image_bytes in paired_uploads:
            task = self.upload_image_for_document_async(
                image = image_bytes,
                document_id = document_id,
                block_id = block_id,
            )
            upload_tasks.append(task)
        if not upload_tasks: return

        image_tokens: List[str] = await asyncio.gather(*upload_tasks)

        update_requests: List[UpdateBlockRequest] = []
        valid_block_ids_to_update = image_block_ids[:len(image_tokens)]
        
        for block_id, image_token in zip(valid_block_ids_to_update, image_tokens):
            replace_image_req_builder = ReplaceImageRequest.builder()
            replace_image_req_builder = replace_image_req_builder.token(image_token)
            replace_image_req = replace_image_req_builder.build()
            
            update_req_builder = UpdateBlockRequest.builder()
            update_req_builder = update_req_builder.block_id(block_id)
            update_req_builder = update_req_builder.replace_image(replace_image_req)
            update_req = update_req_builder.build()
            
            update_requests.append(update_req)

        if update_requests:
            request_body_builder = BatchUpdateDocumentBlockRequestBody.builder()
            request_body_builder = request_body_builder.requests(update_requests)
            request_body = request_body_builder.build()
            
            batch_update_request_builder = BatchUpdateDocumentBlockRequest.builder()
            batch_update_request_builder = batch_update_request_builder.document_id(document_id)
            batch_update_request_builder = batch_update_request_builder.request_body(request_body)
            batch_update_request = batch_update_request_builder.build()
            
            update_response = await self._lark_client.docx.v1.document_block.abatch_update(batch_update_request)
            
            if not update_response.success():
                raise RuntimeError(f"[LarkBot] Failed to batch update appended image blocks: {update_response.code} {update_response.msg}")

        return None
    
    
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
        
        
    async def add_members_to_chat_async(
        self,
        chat_id: str,
        member_ids: List[str],
        member_id_type: Literal["user_id", "open_id", "union_id"] = "user_id",
    )-> None:
        
        request_body_builder = CreateChatMembersRequestBody.builder()
        request_body_builder = request_body_builder.id_list(member_ids)
        request_body = request_body_builder.build()

        request_builder = CreateChatMembersRequest.builder()
        request_builder = request_builder.chat_id(chat_id)
        request_builder = request_builder.member_id_type(member_id_type)
        request_builder = request_builder.request_body(request_body)
        request = request_builder.build()

        assert self._lark_client.im
        response = await self._lark_client.im.v1.chat_members.acreate(request)
        
        if response.success():
            return None
        else:
            raise RuntimeError(f"[LarkBot] 异步拉人入群失败: {response.code} {response.msg} | chat_id: {chat_id}")