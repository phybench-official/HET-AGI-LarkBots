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
            20,                                   # trial_num
            5,                                    # trial_interval
            None,                                 # check_and_accept, no need
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
    
    # Demo and Stats Logic
    pass


if __name__ == "__main__":
    
    asyncio.run(main())