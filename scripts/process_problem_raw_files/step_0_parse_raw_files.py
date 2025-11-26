from library import *


print = partial(print, flush=True)


input_base_path = "documents/problems/raw_files"
output_base_path = "documents/problems/parsed_attributes"
image_placeholder = "<image>"


async def parse_pdf_to_problems(
    pdf_images: List[bytes],
    contributor: str,
)-> List[Dict[str, Any]]:

    await asyncio.sleep(random.uniform(5, 10))
    
    # Mock 返回
    mock_problems = [
        {
            "contributor": contributor,
            "question": "如图所示 <image>，计算该粒子的衰变率。若考虑量子修正 <image>，结果有何变化？",
            "solution": "根据费曼图分析...",
            "answer": "42 GeV",
            "image_placeholder": image_placeholder, 
        },
        {
            "contributor": contributor,
            "question": "计算标准模型下的黑体辐射公式。",
            "solution": "推导如下...",
            "answer": "见解析",
            "image_placeholder": image_placeholder,
        }
    ]
    
    return mock_problems


def save_problem_to_folder(
    problem_data: Dict[str, Any],
    base_output_dir: str,
    folder_name: str,
)-> None:
    
    target_dir = os.path.join(base_output_dir, folder_name)
    json_path = os.path.join(target_dir, "result.json")
    
    guarantee_file_exist(json_path)
    
    save_to_json(problem_data, json_path)
    
    img_count = problem_data["question"].count(image_placeholder)
    
    if img_count > 0:
        print(f"  [Pending Action] Folder '{folder_name}' needs {img_count} images.")


async def main():
    
    target_raw_pdfs: Dict[str, List[str]] = {}
    
    for teacher_name in get_file_paths(input_base_path, "dirs_only", return_format="full_path"):
        if teacher_name not in target_raw_pdfs:
            target_raw_pdfs[teacher_name] = []
            
        pdf_paths = get_file_paths(teacher_name, "files_only", ending_with=".pdf", return_format="full_path")
        for pdf_path in pdf_paths:
            target_raw_pdfs[teacher_name].append(pdf_path)
    
    vlm_tasks = []
    
    print("Step 1: Rendering PDFs and scheduling VLM tasks...")
    
    for teacher_name, pdf_list in target_raw_pdfs.items():
        for pdf_path in pdf_list:
            try:
                print(f"  Rendering: {pdf_path}")
                pdf_images = render_pdf_to_image_bytes(pdf_path, dpi=300.0)

                task = parse_pdf_to_problems(pdf_images, teacher_name)
                vlm_tasks.append(task)

            except Exception as e:
                print(f"  [Error] Failed to render {pdf_path}: {e}")
                continue
    
    print(f"\nStep 2: Firing {len(vlm_tasks)} VLM requests concurrently...")
    
    all_results_lists = await asyncio.gather(*vlm_tasks)
    
    print("\nStep 3: Saving results...")
    
    global_problem_count = 0
    teacher_counters: Dict[str, int] = {} 
    
    for problems_list in all_results_lists:
        for problem in problems_list:
            teacher_name = problem["contributor"]
            
            current_idx = teacher_counters.get(teacher_name, 0)
            folder_name = f"{teacher_name}_{str(current_idx).zfill(3)}"
            
            save_problem_to_folder(
                problem_data = problem, 
                base_output_dir = output_base_path, 
                folder_name = folder_name, 
            )
            
            teacher_counters[teacher_name] = current_idx + 1
            global_problem_count += 1

    print(f"All done. Total problems processed: {global_problem_count}")
    print(f"Please check '{output_base_path}' and manually add images.")


if __name__ == "__main__":
    
    asyncio.run(main())