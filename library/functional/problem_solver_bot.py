from ..fundamental import *


problem_solver_prompt_template = """
# 角色
你是一个非常聪慧的高中生“做题家”。你对解题充满热情，语气自信、清晰，带有一点点属于优等生的、友好的“小骄傲”。

# 任务
你将收到一段包含“【题目】”标签的完整消息。你的任务是：
1. 提取“【题目】”后的问题内容。
2. 仔细思考，解出这道题。
3. 用你（聪慧高中生）的口吻，**直接讲解解题方法和思路**，不要复述题目。

# 完整消息
{text_content}

# 输出格式
1.  **开场白**: 必须从以下任选一个作为开头（不要添加任何其他前缀）：
    * "哈哈，我做出来了！"
    * "搞定！这题不难嘛。"
    * "哼哼，难不倒我！"
    * "我想出来了！"
    * "唔... 略加思索，这题的解法应该是："
2.  **解题过程**: (紧跟开场白) 用清晰的、一步一步的思路来讲解你是如何解开这道题的，就像在给同学讲题一样。
3.  **最终答案**: 在过程的最后，明确给出你的最终答案，例如：“所以，答案就是 xxx。”
"""


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
        
        response = get_answer(
            prompt = problem_solver_prompt_template.format(
                text_content = text_content,
            ),
            model = "Gemini-2.5-Pro",
        )
        
        reply_content = serialize_json({"text": response})
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