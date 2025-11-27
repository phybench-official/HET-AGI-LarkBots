from library import *


input_base_path = "documents/problems/parsed_attributes"
output_base_path = "documents/problems/final_QAs"


def get_question_id(
    question: str,
    image_bytes_list: List[bytes],
) -> str:
    
    hasher = hashlib.md5()
    hasher.update(question.encode("UTF-8"))

    for image_bytes in image_bytes_list:
        hasher.update(image_bytes)
    
    return hasher.hexdigest()


def main():
    
    problems = []
    for path in get_file_paths(
        input_base_path,
        file_type = "dirs_only",
        return_format = "full_path",
    ):
        problem_attributes = load_from_json(
            file_path = f"{path}{seperator}result.json",
        )
        image_count = problem_attributes["question"]\
                        .count(problem_attributes["image_placeholder"])
        image_bytes_list = []
        image_path = ""
        try:
            for index in range(image_count):
                image_path = f"{path}{seperator}{index}.png"
                image_bytes_list.append(
                    align_image_to_bytes(image_path)
                )
        except FileNotFoundError:
            print(f"{path} 这道题目的图片 {image_path} 缺失！")
            continue
        problems.append({
            "question_id": get_question_id(problem_attributes["question"], image_bytes_list),
            "system_prompt": None,
            "question": problem_attributes["question"],
            "images": image_bytes_list,
            "solution": problem_attributes["solution"],
            "answer": problem_attributes["answer"],
            "contributor": problem_attributes["contributor"],
            "image_placeholder": problem_attributes["image_placeholder"],
            "reviewed": problem_attributes["reviewed"],
        })
    
    parquet_path = f"{output_base_path}{seperator}HET_bench.parquet"
    save_to_parquet(
        problems,
        parquet_path = parquet_path,
    )
    print(f"Saved {len(problems)} problems to {parquet_path}")
    
    print("Program OK.")


if __name__ == "__main__":
    
    main()