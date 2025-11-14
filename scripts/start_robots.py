from library import * # 确保这里能导入 ProblemSolverBot 和 LarkDocumentTestBot

# 必须定义一个顶层函数作为进程的入口点
def run_bot(
    bot_name: str, 
    bot_class: type,
)-> None:
    
    print(f"[Process-{os.getpid()}] Starting bot: {bot_name}")
    try:
        # 在新进程中实例化和启动 Bot
        bot_instance = bot_class(bot_name)
        
        # 使用 block=True 来阻塞这个 *子进程*
        # 这将使子进程保持活动状态，运行 Bot
        bot_instance.start(block=True) 
        
    except KeyboardInterrupt:
        # 子进程收到信号，正常退出
        print(f"[Process-{os.getpid()}] Shutdown signal for {bot_name}")
    except Exception as e:
        print(f"[Process-{os.getpid()}] Bot {bot_name} crashed: {e}")


def main():
    
    # 定义所有要运行的机器人
    bots_to_run: list[tuple[str, type]] = [
        ("ProblemSolver", ProblemSolverBot),
        ("PKU_PHY_fermion", LarkDocumentTestBot),
    ]

    processes: list[multiprocessing.Process] = []

    for name, bot_class in bots_to_run:
        # 创建进程
        proc = multiprocessing.Process(
            target=run_bot,
            args=(name, bot_class),
            daemon=True  # 设置为守护进程，以便主进程退出时它们也退出
        )
        proc.start()
        processes.append(proc)
        print(f"[Main] Started process {proc.pid} for {name}")

    # 保持主进程活动（等待 Ctrl+C）
    print("[Main] All bot processes started. MainThread is waiting (Press Ctrl+C to exit).")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[Main] Shutdown signal received. Terminating bot processes.")
        for proc in processes:
            if proc.is_alive():
                proc.terminate() # 发送 SIGTERM
        for proc in processes:
            proc.join() # 等待进程退出
        print("[Main] All processes terminated.")


if __name__ == "__main__":
    # 在 Windows 和 macOS 上，使用 "spawn" 启动方法是必要的
    try:
        multiprocessing.set_start_method("spawn")
    except RuntimeError:
        pass  # 可能是 "spawn" 已经被设置，或者在 Linux 上不需要
    
    main()