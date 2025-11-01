from library import *


problem_solver_app_id, problem_solver_app_secret = \
    get_lark_app_token("ProblemSolver")

lark_client = lark.Client.builder() \
    .app_id(problem_solver_app_id) \
    .app_secret(problem_solver_app_secret) \
    .log_level(lark.LogLevel.INFO) \
    .build()


def handle_message_receive(
    data: P2ImMessageReceiveV1
)-> None:

    if data.event is None: return
    if data.event.message is None: return

    message_id = data.event.message.message_id
    chat_type = data.event.message.chat_type
    data_content = data.event.message.content
    if not isinstance(message_id, str):
        print(f"[Handler] 收到非字符串 message_id: {message_id}")
        return
    if not isinstance(chat_type, str):
        print(f"[Handler] 收到非字符串 chat_type: {chat_type}")
        return
    if chat_type != "group":
        print("[Handler] 忽略非群聊消息")
        return
    if not isinstance(data_content, str):
        print(f"[Handler] 收到非字符串 data_content: {data_content}")
        return

    try:
        data_content_dict = deserialize_json(data_content)
        text_content = data_content_dict.get("text", "").strip()
    except Exception:
        print("[Handler] 忽略非纯文本消息")
        return

    print(f"[Handler] 收到群消息: {text_content}")

    keywords = ["【题目】"]
    if any(keyword in text_content for keyword in keywords):
        print("  -> [Handler] 启动后台做题家线程")
        worker_thread = threading.Thread(
            target = problem_solver_worker,
            args = (lark_client, message_id, text_content),
        )
        worker_thread.start()
    
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