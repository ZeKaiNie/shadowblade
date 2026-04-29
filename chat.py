"""
简易聊天脚本 - 跟本地 Qwen3-4B 对话
用法: source .venv/bin/activate && python chat.py
输入 exit 或 quit 退出
"""
from vllm import LLM, SamplingParams

if __name__ == "__main__":
    print("正在加载模型，请等待约30秒...")
    llm = LLM(
        model="models/qwen3-4b-awq",
        quantization="awq",
        max_model_len=2048,
        enforce_eager=True,
        gpu_memory_utilization=0.80,
    )
    print("✅ 模型加载完成！输入问题开始聊天，输入 exit 退出\n")

    params = SamplingParams(temperature=0.7, max_tokens=500)

    while True:
        question = input("你: ").strip()
        if question.lower() in ("exit", "quit", "q"):
            print("再见！")
            break
        if not question:
            continue

        outputs = llm.generate([question], params)
        answer = outputs[0].outputs[0].text.strip()
        print(f"AI: {answer}\n")
