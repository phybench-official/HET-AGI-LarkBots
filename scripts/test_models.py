import asyncio
from pywheels import get_answer_async


async def main():
    
    models_to_test = [
        "Gemini-2.5-Pro-for-HET-AGI",
        "GPT-5-for-HET-AGI",
        "GPT-5-Nano-for-HET-AGI",
    ]
    
    coroutines = []
    for model in models_to_test:
        coroutines.append(get_answer_async(
            prompt = "你是谁？是哪个组织制造的什么模型？何时被推出？知识截止至何时？",
            model = model,
        ))
        
    for model, coroutine in zip(models_to_test, coroutines):
        response = await coroutine
        print(f"[{model}]\n{response}")


if __name__ == "__main__":
    
    asyncio.run(main())