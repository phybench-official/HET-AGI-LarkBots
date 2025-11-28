import asyncio
from pywheels import get_answer_async


async def test_model(
    model: str,
)-> None:
    
    response = await get_answer_async(
        prompt = "你是谁？是哪个组织制造的什么模型？何时被推出？知识截止至何时？",
        model = model,
    )
    print(f"[{model}]\n{response}\n\n")
    
    return None


async def main():
    
    models_to_test = [
        "GPT-5-for-HET-AGI",
        "GPT-4o-for-HET-AGI",
        "O3-for-HET-AGI",
        "O4-mini-for-HET-AGI",
        "Gemini-2.5-Pro-for-HET-AGI",
        "Gemini-2.5-Flash-for-HET-AGI",
        "Grok-4.1-thinking-for-HET-AGI",
        "Grok-3-for-HET-AGI",
        "Qwen-Max-for-HET-AGI",
        "Qwen-Plus-for-HET-AGI",
        "Doubao-Seed-1.6-thinking-for-HET-AGI",
        "Deepseek-R1-for-HET-AGI",
        "Deepseek-V3-for-HET-AGI",
        "GLM-4.5-for-HET-AGI",
        "Claude-Sonnet-4.5-thinking-for-HET-AGI",
    ]
    
    await asyncio.gather(
        *[test_model(model) for model in models_to_test],
    )
        
    print("Program OK.")


if __name__ == "__main__":
    
    asyncio.run(main())