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

**2. CRITICAL RULES FOR IMAGES (NO OCR):**
- **Strict Placeholder Usage:** When you encounter ANY diagram, figure, or graph, you MUST insert the token "{output_image_token}" exactly at that position.
- **NO OCR / NO TRANSCRIPTION:** Do NOT try to read, transcribe, or describe text/numbers inside the image. 
    - BAD: "As shown in the figure (where F=10N)..."
    - GOOD: "As shown in the figure {output_image_token}..."
- **Text Only vs Mixed:** Only the `question` field can contain image tokens. The `solution` and `answer` fields MUST BE PURE TEXT.

**3. FIELD EXTRACTION RULES:**

* **question** (String): 
    - The full text of the problem stem.
    - **Allows Images:** Insert "{output_image_token}" for diagrams.
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
- **LaTeX:** Use single `$` for inline math. Escape backslashes (e.g., `\\alpha`), **ensure successful parsing using `json.loads`**.
</instruction>

<examples>
    <example_1>
        <input>
        [Question 1 with a circuit diagram. Answer is 5A.]
        </input>
        <output>
        ```json
        [
            {{
                "question": "Refer to the circuit diagram {output_image_token}. Calculate current.",
                "solution": "Using Ohm's law, I = V/R...",
                "answer": "5 A"
            }}
        ]
        ```
        <note>Question has token. Answer is pure text.</note>
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
                # 键校验
                if not all(k in item for k in required_keys):
                    return False
                
                # 类型校验
                if not all(isinstance(item[k], str) for k in required_keys):
                    return False

                # 逻辑校验：Solution 和 Answer 必须是纯文本
                if output_image_token in item["solution"]:
                    # print("  [Reject] Solution contains image token.")
                    return False
                
                if output_image_token in item["answer"]:
                    # print("  [Reject] Answer contains image token.")
                    return False

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
                render_pdf_to_image_bytes(pdf_path, dpi=300.0),
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


if __name__ == "__main__":

    asyncio.run(main())