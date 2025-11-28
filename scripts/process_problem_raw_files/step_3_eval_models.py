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


async def upload_model_answer_sheet(
    model: str,
    lark_bot: LarkBot,
)-> None:
    
    print(f"上传 {model} 的 Answer sheet 中...")
    
    task_indexers = []
    task_inputs = []
    for problem in HET_bench_problems:
        question_id = problem["question_id"]
        question = problem["question"]
        solution = problem["solution"]
        answer = problem["answer"]
        response = rollout_results[model][question_id]
        eval_result = eval_results[model][question_id]
        justification = eval_result["justification"]
        task_indexers.extend([
            (question_id, attribute)
            for attribute in ["question", "solution", "answer", "response", "justification"]
        ])
        task_inputs.extend([
            (question, ), (solution, ), (answer, ), 
            (response, ), (justification, ), 
        ])
    
    _render_equation = partial(
        render_equation_async,
        begin_of_equation = lark_bot.begin_of_equation,
        end_of_equation = lark_bot.end_of_equation,
        model = "Qwen-Max-for-HET-AGI",
        temperature = 0.0,
        timeout = 300,
        trial_num = 20,
        trial_interval = 5,
    )
    render_results = await run_tasks_concurrently_async(
        task = _render_equation,
        task_indexers = task_indexers,
        task_inputs = task_inputs,
        progress_bar_description = "文档组件渲染中...",
        local_storage_path = f"WorkingTable{seperator}local_storage{seperator}render_results{seperator}{model}.pickle",
        checkpoint_threshold = 1,
    )
    
    document_title = f"HET-bench Answer Sheet of {model}"
    document_id = await lark_bot.create_document_async(
        title = document_title,
        folder_token = lark_bot._config["WorkingTable_folder_token"],
    )
    document_url = get_lark_document_url(
        tenant = lark_bot._config["association_tenant"],
        document_id = document_id,
    )
    print(f"飞书云文档 {document_title} 已创建：{document_url}")
    
    batch_size = 3
    scores = [
        eval_results[model][problem["question_id"]]["score"]
        for problem in HET_bench_problems
    ]
    average_score = sum(scores) / len(scores)
    heading_content = ""
    heading_content += lark_bot.begin_of_first_heading
    heading_content += "整体情况"
    heading_content += lark_bot.end_of_first_heading
    heading_content += f"{lark_bot.begin_of_bold}题目总数{lark_bot.end_of_bold}：{len(HET_bench_problems)}"
    heading_content += f"{lark_bot.begin_of_bold}{model} 均分{lark_bot.end_of_bold}：{average_score:.1f}"
    heading_content += lark_bot.begin_of_first_heading
    heading_content += "答卷细则"
    heading_content += lark_bot.end_of_first_heading
    heading_blocks = lark_bot.build_document_blocks(
        content = heading_content,
    )
    await lark_bot.append_document_blocks_async(
        document_id = document_id,
        blocks = heading_blocks,
        images = [],
    )
    for index in tqdm(
        range(0, len(HET_bench_problems), batch_size),
        desc = f"{model} 作答的题目分批上传中...",
    ):
        batch_content = ""
        problems = HET_bench_problems[index : index + batch_size]
        batch_images = []
        for batch_index, problem in enumerate(problems):
            
            question_id = problem["question_id"]
            rendered_question = render_results[(question_id, "question")]
            rendered_solution = render_results[(question_id, "solution")]
            rendered_answer = render_results[(question_id, "answer")]
            rendered_response = render_results[(question_id, "response")]
            eval_result = eval_results[model][question_id]
            score = eval_result["score"]
            rendered_justification = render_results[(question_id, "justification")]
            
            original_image_placeholder = problem["image_placeholder"]
            problem_images = problem["images"]
            if rendered_question.count(original_image_placeholder) == len(problem_images):
                rendered_question = rendered_question.replace(original_image_placeholder, lark_bot.image_placeholder)
            else:
                rendered_question = rendered_question.replace(original_image_placeholder, "") \
                            + len(problem_images) * lark_bot.image_placeholder
                            
            batch_images.extend(problem_images)
            if batch_index or index:
                batch_content += lark_bot.divider_placeholder
            batch_content += lark_bot.begin_of_second_heading
            batch_content += f"题目 {index + batch_index + 1}"
            batch_content += lark_bot.end_of_second_heading
            batch_content += lark_bot.begin_of_third_heading
            batch_content += "题目"
            batch_content += lark_bot.end_of_third_heading
            batch_content += rendered_question
            batch_content += lark_bot.begin_of_third_heading
            batch_content += "参考解答"
            batch_content += lark_bot.end_of_third_heading
            batch_content += rendered_solution
            batch_content += lark_bot.begin_of_third_heading
            batch_content += "参考答案"
            batch_content += lark_bot.end_of_third_heading
            batch_content += rendered_answer
            batch_content += lark_bot.begin_of_third_heading
            batch_content += "AI 解答"
            batch_content += lark_bot.end_of_third_heading
            batch_content += rendered_response
            batch_content += lark_bot.begin_of_third_heading
            batch_content += "AI 裁判员打分"
            batch_content += lark_bot.end_of_third_heading
            batch_content += lark_bot.begin_of_forth_heading
            batch_content += "分数"
            batch_content += lark_bot.end_of_forth_heading
            batch_content += f"{score:.1f}"
            batch_content += lark_bot.begin_of_forth_heading
            batch_content += "评分依据"
            batch_content += lark_bot.end_of_forth_heading
            batch_content += rendered_justification
            
        batch_blocks = lark_bot.build_document_blocks(
            content = batch_content,
        )
        await lark_bot.append_document_blocks_async(
            document_id = document_id,
            blocks = batch_blocks,
            images = batch_images,
        )
        await asyncio.sleep(random.uniform(0.4, 0.6))
    
    print(f"{model} 的 Answer sheet 已上传完毕！")


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
    
    PKU_PHY_fermion_for_testing = PkuPhyFermionBot(
        config_path = f"configs/pku_phy_fermion_config_for_testing.yaml",
    )
    PKU_PHY_fermion_for_testing.start()
    
    for model in model_to_api_setting_name:
        await upload_model_answer_sheet(
            model = model,
            lark_bot = PKU_PHY_fermion_for_testing,
        )


if __name__ == "__main__":
    
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass
    
    asyncio.run(main())