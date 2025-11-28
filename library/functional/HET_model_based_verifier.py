import xml.etree.ElementTree as ET
from ..fundamental import *


__all__ = [
    "HET_model_verify",
]


async def HET_model_verify(
    problem: str,
    answer: str,
    response: str,
)-> Dict[str, Any]:
    
    model: str = "GPT-5-for-HET-AGI"
    temperature: float = 0.0
    timeout: int = 300
    trial_num: int = 20
    trial_interval: int = 5
    
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

**EXECUTION STEPS:**
1. **Identify Sub-questions:** Determine if the <Problem> contains multiple independent sub-questions (e.g., (1), (2)). If not, treat it as a single question.
2. **Extract Model Answer:** Locate the final answer for each sub-question in <Model_Response_to_Verify>.
3. **Compare & Score:** Compare each extracted answer with the <Ground_Truth_Answer>.

**SCORING RULES (ALL-OR-NOTHING PER SUB-QUESTION):**
- **Strict Binary Scoring:** For EACH sub-question, the score is either **100% (Pass)** or **0% (Fail)**. NO partial credit for "correct steps" or "close attempts".
- **Total Score:** Calculate the average pass rate across all sub-questions. 
    - *Example:* If there are 3 sub-questions and the model gets 2 right: Score = (1 + 1 + 0) / 3 * 100 = 66.7.

**EQUIVALENCE JUDGMENT PRINCIPLES:**
1. **Numerical Equivalence (STRICT):** - Only accept numerical answers within a **strict tolerance of ±1%** unless the problem specifies otherwise.
    - Significant figures must be reasonable (e.g., 1.5 vs 1.499 is OK; 1.5 vs 1.6 is FAIL).
2. **Semantic Equivalence:** - Treat syntactically different but mathematically identical expressions as a match (e.g., "1/sqrt(2)" == "sqrt(2)/2").
    - Normalize common notations (e.g., "B" == "B. 1+\\sqrt{{2}}" in multiple choice).

**OUTPUT FIELDS:**
1. **score** (Float): The final score (0.0 to 100.0). Round to one decimal place.
2. **justification** (String): A concise explanation stating:
    - How many sub-questions were identified.
    - Which sub-questions passed/failed.
    - Why any failure occurred (e.g., "Sub-question (2) failed: Model result 15.0 outside tolerance of GT 12.0").
    
**OUTPUT PROTOCOL:**
You MUST return a single XML object wrapped in **<evaluation>...</evaluation>** tags.
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
            print(f"{model} model verifier 重试啦！调用栈：\n{traceback.format_exc()}")
            return False

    image_placeholder = "<image_placeholder_for_compatibility>"
    prompt = prompt.replace(image_placeholder, "")
    
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