from library import *


print = partial(print, flush=True)


input_base_path = "documents/problems/raw_files"
output_base_path = "documents/problems/parsed_attributes"
image_placeholder = "<image>"


async def parse_pdf_to_problems(
    pdf_images: List[bytes],
    contributor: str,
) -> List[Dict[str, Any]]:
    
    model = "Gemini-2.5-Pro-for-HET-AGI"
    temperature = 0.0
    timeout = 600
    trial_num = 20
    trial_interval = 5
    
    # 对 yunwu 温柔一点
    await asyncio.sleep(random.uniform(5, 10))

    vlm_input_placeholder = "<image_page_input>" 
    output_image_token = "<image>"

    prompt = f"""
<system_role>
You are a strict Physics Data Digitizer. 
Your task is to extract physics problems from PDF page images into a structured JSON List.
</system_role>

<instruction>
Analyze the provided images. Identify ALL independent physics problems.

**1. GROUPING LOGIC:**
- **One Dict = One Independent Problem.**
- **Sub-questions:** If a problem has multiple parts (e.g., (1), (2)), KEEP THEM TOGETHER in a single dictionary.

**2. CRITICAL RULES: IMAGES vs. FORMULAS:**
- **FORMULAS -> OCR (LaTeX):** Do **NOT** use image placeholders for mathematical formulas, equations, or expressions, even if they appear as block elements. You **MUST** transcribe them into LaTeX (e.g., `$$E = mc^2$$`).
- **DIAGRAMS/TABLES -> Placeholder:** Only use the token "{output_image_token}" for:
    1. **Geometric Diagrams / Illustrations** (e.g., circuits, free-body diagrams).
    2. **Data Plots / Graphs** (e.g., v-t graph).
    3. **Tables** (grids of data).
- **NO OCR inside Diagrams:** Do not describe the visual content of a diagram (e.g., do not write "A circle with radius R"). Just put "{output_image_token}".

**3. FIELD EXTRACTION RULES:**

* **question** (String): 
    - The full text of the problem stem.
    - **Prefix Cleaning:** **REMOVE** meta-labels at the start, such as "Problem 1:", "Q1.", "1.", "【题目】", or "Example:". Start directly with the meaningful content.
    - **Allows Images:** Insert "{output_image_token}" for diagrams/tables.
    - **Language:** STRICTLY maintain the original language. NO TRANSLATION.

* **solution** (String):
    - The detailed derivation/explanation.
    - **Constraint:** **PURE TEXT ONLY.** ABSOLUTELY NO image tokens.
    - **Missing Solution:** If not provided, set `solution` = `answer`. Do NOT hallucinate steps.

* **answer** (String):
    - The final result.
    - **Constraint:** **PURE TEXT ONLY.** ABSOLUTELY NO image tokens.
    - **Format:** For sub-questions, use: `(1) result1 (2) result2 ...`.
    - **Extraction:** If not explicitly labeled, extract from the end of the solution.
    - **Missing:** If absolutely no answer found, set to "暂无".

**4. GENERAL FORMATTING:**
- Output MUST be a valid JSON List of Objects.
- Wrap JSON in ```json ... ``` blocks EXPLICITLY.
- **LaTeX:** Use single `$` for inline math. Escape backslashes (e.g., `\\alpha` -> `\\\\alpha` in JSON string), **ensure successful parsing using `json.loads`**.
</instruction>

<examples>
    <example_1>
        <input>
        [Text: "Problem 1: Calculate the flux."]
        [Image: A solenoid diagram]
        [Text: "Given $\\Phi = B \\cdot A$."]
        </input>
        <output>
        ```json
        [
            {{
                "question": "Calculate the flux. Refer to the solenoid {output_image_token}.",
                "solution": "We know that $\\Phi = B \\cdot A$. Integrating over the surface...",
                "answer": "42 Wb"
            }}
        ]
        ```
        <note>Prefix "Problem 1:" removed. Formula "Phi = B A" is OCR'd as LaTeX. Diagram is replaced by token.</note>
    </example_1>
</examples>

<input_raw_PDF_pages>
{vlm_input_placeholder * len(pdf_images)}
</input_raw_PDF_pages>

Please generate the JSON List now.
"""

    final_result: List[Dict[str, Any]] = []

    def check_and_accept(
        response: str,
    ) -> bool:
        nonlocal final_result
        
        try:
            json_pattern = r'```json\s*(.*?)\s*```'
            matches = re.findall(json_pattern, response, re.DOTALL)
            
            if matches:
                json_string = matches[0].strip()
            else:
                json_string = response.strip()

            parsed_obj = deserialize_json(json_string)

            if not isinstance(parsed_obj, list):
                return False
            
            validated_list = []
            required_keys = ["question", "solution", "answer"]

            for item in parsed_obj:
                if not all(k in item for k in required_keys): return False
                if not all(isinstance(item[k], str) for k in required_keys): return False
                # Solution 和 Answer 必须是纯文本
                if output_image_token in item["solution"]: return False
                if output_image_token in item["answer"]: return False
                item["contributor"] = contributor
                item["image_placeholder"] = image_placeholder
                item["reviewed"] = False
                validated_list.append(item)

            final_result = validated_list
            return True

        except Exception:
            print(f"Oh no，{model} 重试啦！调用栈：\n{traceback.format_exc()}")
            return False

    _ = await get_answer_async(
        prompt = prompt,
        model = model,
        images = pdf_images,
        image_placeholder = vlm_input_placeholder,
        temperature = temperature,
        timeout = timeout,
        trial_num = trial_num,
        trial_interval = trial_interval,
        check_and_accept = check_and_accept,
    )

    return final_result


def save_problem_to_folder(
    problem_data: Dict[str, Any],
    base_output_dir: str,
    folder_name: str,
)-> None:
    
    json_path = f"{base_output_dir}{seperator}{folder_name}{seperator}result.json"
    
    guarantee_file_exist(json_path)
    
    save_to_json(problem_data, json_path)
    
    img_count = problem_data["question"].count(image_placeholder)
    
    if img_count > 0:
        print(f"  [Pending Action] Folder '{folder_name}' needs {img_count} images.")


async def main():
    
    print("Step 1: Rendering PDFs and scheduling VLM tasks...")
    
    task_indexers = []
    task_inputs = []
    
    for teacher_name in get_file_paths(
        input_base_path,
        file_type = "dirs_only", 
        return_format = "name_only",
    ):
        pdf_paths = get_file_paths(
            f"{input_base_path}{seperator}{teacher_name}", 
            file_type = "files_only",
            ending_with = ".pdf",
            return_format = "full_path",
        )
        for pdf_path in pdf_paths:
            print(f"  Rendering: {pdf_path}")
            task_indexers.append(pdf_path)
            task_inputs.append((
                render_pdf_to_image_bytes(pdf_path, dpi=600.0),
                teacher_name,
            ))
    
    print(f"\nStep 2: Firing {len(task_indexers)} VLM requests concurrently...")
    
    OCR_results = await run_tasks_concurrently_async(
        task = parse_pdf_to_problems,
        task_indexers = task_indexers,
        task_inputs = task_inputs,
        local_storage_path = "WorkingTable/local_storage/process_problems_step_0.pickle",
        checkpoint_threshold = 1,
        # max_workers = 50,
        # lazy = False,
    )
    
    print("\nStep 3: Saving results...")
    
    global_problem_count = 0
    teacher_counters: Dict[str, int] = {}
    
    for pdf_path, (_, teacher_name) in zip(task_indexers, task_inputs):
        problems = OCR_results[pdf_path]
        for problem in problems:
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
    
    print("Program OK.")


if __name__ == "__main__":

    asyncio.run(main())