import io
import traceback
import contextlib
import functools
from typing import Any, Dict, Callable
import multiprocessing as mp
from multiprocessing import Queue


__all__ = [
    "python_tool",
]


def _execute_in_sandbox(
    code: str,
    result_queue: "Queue[str]",
)-> None:
    
    exec_scope: Dict[str, Any] = {}
    stdout_capture = io.StringIO()
    output: str = ""
    
    try:
        with contextlib.redirect_stdout(stdout_capture):
            exec(code, exec_scope, exec_scope) 
        
        output = stdout_capture.getvalue()
        
        if not output:
            output = "代码已成功执行，但没有产生 stdout 输出。必须使用 print() 语句才能返回计算结果。"
            
    except Exception as error:
        output = f"代码执行失败: {error}\n调用栈：\n{traceback.format_exc()}"
    
    result_queue.put(output)


def _execute_python(
    code: str,
    timeout: int,
    verbose: bool,
)-> str:
    
    result_queue: "Queue[str]" = mp.Queue()
    
    process = mp.Process(
        target=_execute_in_sandbox,
        args=(code, result_queue)
    )
    
    output: str = ""
    
    try:
        process.start()
        process.join(timeout=timeout)
        
        if process.is_alive():
            process.terminate()
            process.join()
            output = f"代码执行失败：已超过 {timeout} 秒超时限制。代码可能包含死循环或被 'input()' 挂起。"
        
        elif process.exitcode == 0:
            try:
                output = result_queue.get(timeout=1)
            except Exception:
                output = "代码执行失败：子进程已退出，但未能从结果队列中获取输出。"
        
        else:
            output = f"代码执行失败：子进程异常终止，退出代码: {process.exitcode}。可能是由段错误或内存溢出引起。"
            try:
                output += f"\n捕获到的输出：\n{result_queue.get_nowait()}"
            except Exception:
                pass
    
    except Exception as error:
        output = f"尝试执行 Python 代码时出错: {error}"
    finally:
        if process.is_alive():
            process.terminate()
        process.close()
    
    if verbose: 
        print(f"--- [Python Tool Executed] ---")
        print(f"Code:\n{code}")
        print(f"Result:\n{output}")
        print(f"------------------------------")
        
    return output


def python_tool(
    timeout: int = 30,
    verbose: bool = False,
)-> Dict[str, Any]:

    bound_implementation: Callable[..., str] = functools.partial(
        _execute_python,
        timeout = timeout,
        verbose = verbose,
    )
    
    tool_definition: Dict[str, Any] = {
        "name": "execute_python",
        "description": (
            "执行 Python 代码块并返回其 `stdout` 输出。\n"
            "适用于需要精确计算、符号求解或使用 `scipy`, `numpy`, `sympy` 等库的复杂数学问题。\n"
            "重要约束 (Important Notes):\n"
            f"1. **超时**: 代码执行有 {timeout} 秒的严格超时限制。\n"
            "2. **无状态**: 每次执行都是独立的。变量、函数或导入不会在多次调用间保留。\n"
            "3. **输出**: 必须使用 `print()` 语句来输出最终结果。仅写入表达式（如在 Notebook 中）不会产生输出。\n"
            "4. **导入**: 必须 `import` 所有需要的库（例如 `import numpy as np`）。\n"
            "5. **无交互**: 不允许使用 `input()` 或任何其他形式的交互式输入，否则将导致超时。"
        ),
        "parameters": {
            "code": {
                "type": "string",
                "description": (
                    "要执行的 Python 代码字符串。必须是自包含的（包含所有 imports）。"
                    "例如: 'import numpy as np; print(np.log(2 * np.pi))'"
                ),
                "required": True,
            },
        },
        "implementation": bound_implementation,
    }
    
    return tool_definition