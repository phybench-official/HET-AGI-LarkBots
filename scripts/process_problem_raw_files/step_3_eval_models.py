from library import *


print("正在加载 HET bench 题目...")
input_path = "documents/problems/final_QAs/HET_bench.parquet"
_HET_bench_problems = load_from_parquet(input_path)
HET_bench_problems = _HET_bench_problems.to_dict("records")
print("HET bench 题目已加载完成！")


model_to_api_setting_name = {
    "Gemini-2.5-Pro": "Gemini-2.5-Pro-for-HET-AGI",
    "GPT-5": "GPT-5-for-HET-AGI",
}


tools = []


rollout_coroutines = {}
rollout_results = {}
async def rollout_coroutine(
    model: str,
)-> None:
    
    task_indexers = []
    task_inputs = []
    for problem in HET_bench_problems:
        task_indexers.append(problem["question_id"])
        task_inputs.append((
            problem["question"],                  # prompt
            model_to_api_setting_name[model],     # model
            problem["system_prompt"],             # system_prompt
            problem["images"],                    # images
            problem["image_placeholder"],         # image_placeholder
            None,                                 # temperature, use default
            None,                                 # top_p, use default
            None,                                 # max_completion_tokens, use default
            (minutes := 30) * 60,                 # timeout
            20,                                    # trial_num
            5,                                    # trial_interval
            lambda _: True,                       # check_and_accept, no special needs
            tools,                                # tools
            10,                                   # tool_use_trial_num        
        ))
    
    rollout_result = await run_tasks_concurrently_async(
        task = get_answer_async,
        task_indexers = task_indexers,
        task_inputs = task_inputs,
        progress_bar_description = f"{model} rollout 中...",
        local_storage_path = f"WorkingTable{seperator}local_storage{seperator}rollout_results{seperator}{model}.pickle",
        checkpoint_threshold = 1,
    )
    rollout_results[model] = rollout_result
    
    print(f"模型 {model} 的 rollout 任务已完成")
    return None


eval_coroutines = {}
eval_results = {}
async def eval_coroutine(
    model: str,
)-> None:
    
    await rollout_coroutines[model]
    rollout_result = rollout_results[model]
    
    task_indexers = []
    task_inputs = []
    for problem in HET_bench_problems:
        task_indexers.append(problem["question_id"])
        task_inputs.append((
            problem["question"],                      # problem
            problem["answer"],                        # answer
            rollout_result[problem["question_id"]]    # response
        ))
    
    eval_result = await run_tasks_concurrently_async(
        task = HET_model_verify,
        task_indexers = task_indexers,
        task_inputs = task_inputs,
        progress_bar_description = f"{model} rollout 结果 eval 中...",
        local_storage_path = f"WorkingTable{seperator}local_storage{seperator}eval_results{seperator}{model}.pickle",
        checkpoint_threshold = 1,
    )
    eval_results[model] = eval_result
    
    print(f"模型 {model} 的 eval 任务已完成")
    return None


def generate_report_html(
    model: str, 
    problems: List[Dict[Hashable, Any]], 
    rollout_data: Dict[str, str], 
    eval_data: Dict[str, Dict[str, Any]],
) -> str:
    """生成包含 LaTeX 渲染的 HTML 报告内容"""

    # MathJax 配置，用于渲染 LaTeX 公式
    html_header = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>HET Bench Evaluation Report - {model}</title>
        <script type="text/javascript" async
          src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-mml-chtml.js">
        </script>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; }}
            .problem {{ border: 2px solid #ccc; padding: 15px; margin-bottom: 20px; border-radius: 8px; }}
            .section {{ margin-top: 10px; padding-left: 10px; border-left: 4px solid #eee; }}
            .question-text {{ font-weight: bold; margin-bottom: 5px; }}
            .score-box {{ float: right; padding: 8px; font-size: 1.2em; font-weight: bold; border-radius: 5px; }}
            .score-PASS {{ background-color: #d4edda; color: #155724; border: 1px solid #c3e6cb; }}
            .score-FAIL {{ background-color: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }}
            .justification {{ font-style: italic; color: #666; margin-top: 5px; }}
            img {{ max-width: 100%; height: auto; margin: 10px 0; border: 1px solid #ddd; }}
        </style>
    </head>
    <body>
    <h1>HET Bench 评测报告 - {model}</h1>
    <h2>总计题目数: {len(problems)}</h2>
    """

    html_content = []
    
    for problem in problems:
        q_id = problem["question_id"]
        response_text = rollout_data.get(q_id, "【ROLLOUT FAILED】")
        eval_data_item = eval_data.get(q_id, {"score": 0.0, "justification": "Evaluation Failed or Timeout."})
        
        score = eval_data_item["score"]
        justification = eval_data_item["justification"]
        
        # 判断分数级别
        score_class = "score-PASS" if score >= 80 else "score-FAIL"

        # ------------------- 图片处理 -------------------
        question_html = problem["question"]
        
        # 将原始问题中的图片 bytes 转换为 Base64 嵌入 HTML
        # 假设问题中的图片是按顺序存储的
        image_bytes_list = problem.get("images", [])
        
        for i, img_bytes in enumerate(image_bytes_list):
            try:
                base64_img = base64.b64encode(img_bytes).decode('utf-8')
                img_tag = f'<img src="data:image/png;base64,{base64_img}" alt="Diagram {i+1}">'
                # 替换问题中的占位符 <image> 为实际图片
                question_html = question_html.replace(problem["image_placeholder"], img_tag, 1)
            except Exception:
                # 图像编码失败时，保留占位符或提示错误
                question_html = question_html.replace(problem["image_placeholder"], "[IMAGE ENCODING ERROR]", 1)

        # ------------------- 核心内容布局 -------------------
        
        html_content.append(f"""
        <div class="problem">
            <div class="{score_class} score-box">分数: {score:.1f} / 100</div>
            <h3>问题 ID: {q_id}</h3>
            
            <div class="section">
                <h4>原始题目 (Q)</h4>
                <div class="question-text">{question_html}</div>
            </div>

            <div class="section">
                <h4>标准答案 (A)</h4>
                <div>{problem["answer"]}</div>
            </div>
            
            <div class="section">
                <h4>模型输出 (R)</h4>
                <pre>{response_text}</pre>
            </div>
            
            <div class="section">
                <h4>裁判判分意见</h4>
                <div class="justification">{justification}</div>
            </div>
        </div>
        """)

    return html_header + "".join(html_content) + "</body></html>"


def save_report_pdf(html_content: str, output_path: str) -> None:
    """
    保存 HTML 内容为 PDF。
    注意: 此函数仅作为外部依赖的占位符。
    
    推荐使用 WeasyPrint 或 wkhtmltopdf (需要安装系统依赖)
    e.g., pip install weasyprint
    """
    
    # 确保输出目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # 1. 临时保存 HTML 文件
    html_path = output_path.replace(".pdf", ".html")
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html_content)
    
    # 2. 转换为 PDF (需要外部依赖，此处仅为提示)
    print(f"\n[INFO] HTML 报告已保存至 {html_path}")
    print(f"[ACTION REQUIRED] 请使用外部工具将该 HTML 文件转换为 PDF ({output_path})，以获得正确渲染的公式。")
    
    # 示例: 如果安装了 WeasyPrint，可以取消注释以下代码块
    try:
        from weasyprint import HTML
        HTML(html_path).write_pdf(output_path)
        print(f"[SUCCESS] PDF 报告已生成: {output_path}")
    except ImportError:
        print("[WARNING] WeasyPrint 未安装，跳过 PDF 转换。")


async def main():

    for model in model_to_api_setting_name:
        rollout_coroutines[model] = rollout_coroutine(model)
        print(f"模型 {model} 的 rollout 任务已启动")
    
    for model in model_to_api_setting_name:
        eval_coroutines[model] = eval_coroutine(model)
        print(f"模型 {model} 的 eval 任务已启动")
    
    print(f"正在等待所有模型的 eval 任务完成...")
    await asyncio.gather(*list(eval_coroutines.values()))
    print(f"所有模型的 eval 任务已完成！")
    
    print("--- 启动报告生成 ---")
    for model in model_to_api_setting_name:
        print(f"生成模型 {model} 的报告...")
        
        # 1. 生成 HTML 内容
        html_report = generate_report_html(
            model = model,
            problems = HET_bench_problems,
            rollout_data = rollout_results[model],
            eval_data = eval_results[model],
        )
        
        # 2. 保存为 PDF/HTML
        output_pdf_path = f"documents{seperator}problems{seperator}verified_answer_sheet_{model}.pdf"
        save_report_pdf(html_report, output_pdf_path)

    print("报告生成流程结束。")


if __name__ == "__main__":
    
    asyncio.run(main())