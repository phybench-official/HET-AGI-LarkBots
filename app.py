from library import *


problem_solver_app_id, problem_solver_app_secret = \
    get_lark_app_token("ProblemSolver")

http_client = lark.Client.builder() \
    .app_id(problem_solver_app_id) \
    .app_secret(problem_solver_app_secret) \
    .log_level(lark.LogLevel.INFO) \
    .build()


def solve_problem_worker(
    message_id: str,
    text_content: str
)->None:

    print(f"  -> [Worker] 收到任务: {text_content}，开始处理...")
    
    try:
        
        final_answer: str = f"「做题家」处理完毕！\n你提交的题目是: {text_content}"
        
        # (澄清) 这里使用 API 模型来构建 *回复* 请求
        reply_content: str = json.dumps({"text": final_answer})
        request_body: ReplyMessageRequestBody = ReplyMessageRequestBody.builder() \
            .content(reply_content) \
            .msg_type("text") \
            .build()
        request: ReplyMessageRequest = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(request_body) \
            .build()

        # Worker 处理完毕后，使用 http_client 主动回复
        response = http_client.im.v1.message.reply(request) # type: ignore
        
        
        if response.success():
            print("  -> [Worker] 5 秒后，已发送最终答案")
        else:
            print(f"  -> [Worker] 最终答案发送失败: {response.code}, {response.msg}")

    except Exception as error:
        print(f"  -> [Worker] 处理时发生严重错误: {error}")


def handle_message_receive(
    data: P2ImMessageReceiveV1
)-> None:

    if data.event is None: return
    if data.event.message is None: return

    message_id = data.event.message.message_id
    chat_type = data.event.message.chat_type

    if chat_type != "group":
        print("[Handler] 忽略非群聊消息")
        return

    try:
        content_data: Dict[str, Any] = json.loads(data.event.message.content)
        text_content: str = content_data.get("text", "").strip()
    except Exception:
        print("[Handler] 忽略非纯文本消息")
        return

    print(f"[Handler] 收到群消息: {text_content}")

    # 核心逻辑：只处理 "【题目】"
    if text_content.startswith("【题目】"):
        
        # 1. 立即回复 "收到" (ACK)
        try:
            ack_text: str = "「做题家」已收到题目，正在处理中 (可能需几秒) ..."
            ack_content: str = json.dumps({"text": ack_text})
            ack_request_body = ReplyMessageRequestBody.builder().content(ack_content).msg_type("text").build()
            ack_request = ReplyMessageRequest.builder().message_id(message_id).request_body(ack_request_body).build()
            
            http_client.im.v1.message.reply(ack_request) # type: ignore
            print("  -> [Handler] 立即回复'处理中' (ACK)")
        except Exception as e:
            print(f"  -> [Handler] 快速回复 ACK 失败: {e}")

        # 2. 启动后台线程处理耗时任务
        print("  -> [Handler] 启动后台 Worker 线程")
        worker_thread: threading.Thread = threading.Thread(
            target=solve_problem_worker,
            args=(message_id, text_content)
        )
        worker_thread.start()

    # 3. Handler 立即返回
    print("[Handler] 函数执行完毕并返回")
    
    
def main():
    
    event_handler = lark.EventDispatcherHandler.builder(
        encrypt_key = "",
        verification_token = "",
        level = lark.LogLevel.DEBUG
    ).register_p2_im_message_receive_v1(handle_message_receive).build()

    cli = lark.ws.Client(
        app_id = problem_solver_app_id,
        app_secret = problem_solver_app_secret,
        event_handler = event_handler,
        log_level = lark.LogLevel.DEBUG
    )
    
    print("机器人开始启动（长连接 WebSocket 模式）...")
    cli.start()


if __name__ == "__main__":
    
    main()