import re
import xml.etree.ElementTree as ET
import traceback
from typing import Any, Dict, List, Optional

# 假设这些函数存在于 ..fundamental 中
from ..fundamental import get_answer_async

__all__ = [
    "HET_model_verify",
]


async def HET_model_verify(
    problem: str,
    answer: str,
    response: str,
)-> Dict[str, Any]:
    
    # 局部参数定义 (已遵循你提供的最新值)
    model: str = "GPT-5-for-HET-AGI"
    temperature: float = 0.0
    timeout: int = 300
    trial_num: int = 20
    trial_interval: int = 5
    
    # 评估数据块
    eval_message = f"""
<Problem>
{problem}
</Problem>

<Ground_Truth_Answer>
{answer}
</Ground_Truth_Answer>

<Model_Response_to_Verify>
{response}
</Model_Response_to_Verify>
"""

    prompt = f"""
<system_role>
You are an extremely strict Equivalence Validator. Your ONLY task is to compare the final result contained in <Model_Response_to_Verify> against the <Ground_Truth_Answer>.
</system_role>

<instruction>
**HIGHEST PRIORITY RULE (OVERRIDE ALL DOWNSTREAM SCORING):**
**IGNORE THE SOLUTION PROCESS/METHODOLOGY. ONLY JUDGE THE FINAL ANSWER.**

Analyze the final result provided in <Model_Response_to_Verify> and compare it against the <Ground_Truth_Answer>. The <Problem> provides necessary context for precision tolerance (e.g., significant figures).

**EQUIVALENCE JUDGMENT PRINCIPLES:**
1. **Numerical Equivalence:** Judge numerical results based on the precision required by the <Problem>. If context allows, treat slight numerical differences (e.g., 1.5 vs 1.49) as equivalent.
2. **Semantic Equivalence:** Treat syntactically different but semantically equivalent answers as a match (e.g., "B" vs "B. 1+\\sqrt{2}"). Normalize common math expressions (e.g., pi, sqrt) before comparison.
3. **Partial Credit:** If the problem has sub-questions, grant partial credit for each correct sub-answer, maintaining the total score out of 100.

**OUTPUT FIELDS (Total Score out of 100):**
1. **score** (Float): The final score (0.0 to 100.0, rounded to one decimal place). 100.0 for full equivalence, 0.0 for no equivalence/major error.
2. **justification** (String): A concise explanation stating why the final answer IS or IS NOT equivalent, mentioning the assumed precision or format normalization used.
    
**OUTPUT PROTOCOL:**
You MUST return a single XML object wrapped in **<evaluation>...</evaluation>** tags. `score` should be a floatable string and justification should be a string.
</instruction>

<required_schema>
<evaluation>
    <score>...</score>
    <justification>...</justification>
</evaluation>
</required_schema>

{eval_message}

Please generate the final XML evaluation now.
"""
    
    final_result: Dict[str, Any] = {}

    def check_and_accept(
        response_text: str,
    ) -> bool:
        nonlocal final_result
        
        try:
            # 1. 提取 XML 块
            xml_pattern = r'<evaluation>(.*?)</evaluation>'
            matches = re.findall(xml_pattern, response_text, re.DOTALL)
            
            if not matches:
                root = ET.fromstring(response_text.strip())
            else:
                xml_string = f"<evaluation>{matches[0].strip()}</evaluation>"
                root = ET.fromstring(xml_string)

            # 2. 查找关键元素
            score_element = root.find('score')
            justification_element = root.find('justification')

            if score_element is None or justification_element is None:
                return False

            # 3. 校验类型和范围
            # 使用 assert 满足 Pylance 静态检查
            assert score_element.text is not None
            assert justification_element.text is not None
            
            score_value = float(score_element.text.strip())
            justification_value = justification_element.text.strip()
            
            if not (0.0 <= score_value <= 100.0):
                return False
                
            final_result = {
                "score": round(score_value, 1),
                "justification": justification_value,
            }
            return True

        except Exception:
            # 捕获并打印调用栈信息，遵循用户调试需求
            # 必须在模块顶部导入 traceback
            print(f"{model} model verifier 重试啦！调用栈：\n{traceback.format_exc()}")
            return False

    image_placeholder = "<image_placeholder>"
    prompt = prompt.replace(image_placeholder, "")
    
    # 执行请求
    await get_answer_async(
        prompt = prompt,
        model = model,
        images = [],
        image_placeholder = image_placeholder,
        temperature = temperature,
        timeout = timeout,
        trial_num = trial_num,
        trial_interval = trial_interval,
        check_and_accept = check_and_accept,
    )

    return final_result