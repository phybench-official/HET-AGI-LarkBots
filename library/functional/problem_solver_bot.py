from ..fundamental import *


__all__ = [
    "problem_solver_worker",
]


def problem_solver_worker(
    lark_client: lark.Client,
    message_id: str,
    text_content: str,
)->None:

    print(f"  -> [Worker] 收到任务: {text_content}，开始处理...")
    
    try:
        
        final_answer = f"【调试中】嚯嚯，这都有题做的喔！"

        reply_content = serialize_json({"text": final_answer})
        request_body: ReplyMessageRequestBody = ReplyMessageRequestBody.builder() \
            .content(reply_content) \
            .msg_type("text") \
            .build()
        request: ReplyMessageRequest = ReplyMessageRequest.builder() \
            .message_id(message_id) \
            .request_body(request_body) \
            .build()
        
        response = lark_client.im.v1.message.reply(request) # type: ignore
        
        if response.success():
            print("  -> [Worker] 已发送最终答案")
        else:
            print(f"  -> [Worker] 最终答案发送失败: {response.code}, {response.msg}")

    except Exception as error:
        print(f"  -> [Worker] 处理时发生严重错误: {error}")