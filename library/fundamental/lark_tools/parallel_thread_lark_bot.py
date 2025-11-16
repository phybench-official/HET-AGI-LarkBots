from .lark_bot import *
from ._lark_sdk import *
from ..typing import *
from ..externals import *


__all__ = [
    "ParallelThreadLarkBot",
]


class ParallelThreadLarkBot(LarkBot):
    
    def __init__(
        self,
        lark_bot_name: str,
        worker_timeout: float,
        context_cache_size: int,
        max_workers: Optional[int],
    )-> None:

        super().__init__(lark_bot_name)
        
        self._init_arguments: Dict[str, Any] = {
            "lark_bot_name": lark_bot_name,
            "worker_timeout": worker_timeout,
            "context_cache_size": context_cache_size,
            "max_workers": max_workers,
        }
        
        self._async_loop: Optional[asyncio.AbstractEventLoop] = None
        self._async_thread: Optional[threading.Thread] = None
        self._manager_lock: Optional[asyncio.Lock] = None
        
        self.thread_queues: Dict[str, asyncio.Queue] = {}
        self.active_workers: Dict[str, asyncio.Task] = {}
        
        self._worker_timeout: float = worker_timeout
        
        self._context_cache_size: int = context_cache_size
        self._context_cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._cache_lock: Optional[asyncio.Lock] = None
        
        self._max_workers: Optional[int] = max_workers
        
        self._event_handler_builder.register_p2_im_message_receive_v1(
            self._sync_bridge_callback,
        )
    

    def _start_internal_logic(self)-> None:
        """
        [实例方法] 真正的机器人启动逻辑，运行在子进程中。
        它启动异步循环和阻塞的 Websocket 客户端。
        """
        
        self._async_loop = asyncio.new_event_loop()
        ready_event = threading.Event()
        self._async_thread = threading.Thread(
            target = self._start_async_loop,
            args = (self._async_loop, ready_event),
            daemon = True,
        )
        print(f"[ParallelThreadLarkBot] Starting synchronous Lark WS client (blocking)...")
        
        self._async_thread.start()
        ready_event.wait()
        print(f"[ParallelThreadLarkBot] Async worker thread started.")
        
        super()._start_internal_logic()
        print(f"[ParallelThreadLarkBot] {self._name} WS client shut down.")
    
    
    def _sync_bridge_callback(
        self,
        message: P2ImMessageReceiveV1,
    )-> None:

        assert self._async_loop is not None, "Bot not started. Call .start()"

        parsed_event: Dict[str, Any] = self.parse_message(message)
        if not parsed_event.get("success"):
            print(f"[ParallelThreadLarkBot] Failed to parse message: {parsed_event.get('error')}")
            return
        
        coro = self._async_distributor(parsed_event)
        asyncio.run_coroutine_threadsafe(coro, self._async_loop)


    async def _async_distributor(
        self,
        parsed_event: Dict[str, Any],
    )-> None:

        try:
            if not self.should_process(parsed_event):
                return
        except Exception as e:
            print(f"[ParallelThreadLarkBot] Error in should_process: {e}")
            return
            
        thread_root_id: str = parsed_event["thread_root_id"]
        
        assert self._manager_lock is not None
        assert self._async_loop is not None
        
        queue = self.thread_queues.get(thread_root_id)

        if queue is None:
            async with self._manager_lock:
                queue = self.thread_queues.get(thread_root_id)
                if queue is None:
                    queue = asyncio.Queue()
                    self.thread_queues[thread_root_id] = queue
                    task: asyncio.Task = self._async_loop.create_task(
                        self._thread_worker(thread_root_id, queue)
                    )
                    self.active_workers[thread_root_id] = task

        await queue.put(parsed_event)


    async def _thread_worker(
        self,
        thread_root_id: str,
        queue: asyncio.Queue,
    )-> None:
        
        current_state: Optional[Dict[str, Any]] = None
        assert self._cache_lock is not None

        async with self._cache_lock:
            current_state = self._context_cache.get(thread_root_id)
            if current_state is not None:
                self._context_cache.move_to_end(thread_root_id)
        
        try:
            while True:
                try:
                    parsed_message: Dict[str, Any] = await asyncio.wait_for(
                        queue.get(), 
                        timeout = self._worker_timeout,
                    )
                    
                    if current_state is None:
                        current_state = await self.get_initial_context(thread_root_id)
                    new_state = await self.process_message_in_context(parsed_message, current_state)
                    
                    current_state = new_state
                    queue.task_done()
                
                except asyncio.TimeoutError:
                    break
        
        except Exception as e:
            print(f"[ParallelThreadLarkBot] Worker {thread_root_id} crashed: {e}")
            
        finally:
            if current_state is not None:
                try:
                    await self.on_thread_timeout(thread_root_id, current_state)
                except Exception as e:
                    print(f"[ParallelThreadLarkBot] Error in on_thread_timeout for {thread_root_id}: {e}")
                
                async with self._cache_lock:
                    self._context_cache[thread_root_id] = current_state
                    self._context_cache.move_to_end(thread_root_id)
                    if len(self._context_cache) > self._context_cache_size:
                        evicted_key, _ = self._context_cache.popitem(last=False)
                        print(f"[ParallelThreadLarkBot] Evicted context for {evicted_key} from LRU cache.")

            
            assert self._manager_lock is not None
            async with self._manager_lock:
                self.thread_queues.pop(thread_root_id, None)
                self.active_workers.pop(thread_root_id, None)
                print(f"[ParallelThreadLarkBot] Worker for thread {thread_root_id} terminated.")


    def _start_async_loop(
        self,
        loop: asyncio.AbstractEventLoop,
        ready_event: threading.Event,
    )-> None:
        
        asyncio.set_event_loop(loop)
        if self._max_workers is not None:
            custom_executor = ThreadPoolExecutor(max_workers=self._max_workers)
            loop.set_default_executor(custom_executor)
            print(f"[ParallelThreadLarkBot] Custom thread pool size set to {self._max_workers}")
        
        self._manager_lock = asyncio.Lock()
        self._cache_lock = asyncio.Lock()
        
        ready_event.set()
        loop.run_forever()

    
    # ------------------ 业务逻辑钩子 ------------------
    
    def should_process(
        self,
        parsed_message: Dict[str, Any],
    )-> bool:
        """
        [同步] 快速过滤器。
        
        :param parsed_message: LarkBot.parse_message() 的输出字典。
        :return: True 表示处理，False 表示丢弃。
        """
        raise NotImplementedError("Subclass must implement should_process")


    async def get_initial_context(
        self,
        thread_root_id: str,
    )-> Dict[str, Any]:
        """
        [异步] 当 LRU 缓存 (L1) 未命中时调用。
        用于创建新上下文，或从持久化存储 (L2, 如 DB) 加载。
        
        :param thread_root_id: 当前话题的 ID，用于 L2 查找。
        :return: 状态字典 (例如: {"history": []})。
        """
        raise NotImplementedError("Subclass must implement get_initial_context")
    
    
    async def process_message_in_context(
        self,
        parsed_message: Dict[str, Any],
        context: Dict[str, Any],
    )-> Dict[str, Any]:
        """
        [异步] 核心业务逻辑，串行处理话题中的每个事件。
        
        :param parsed_message: 当前事件的 parsed_message 字典。
        :param context: 上一个事件处理后返回的状态。
        :return: 处理完毕后需要保存的新状态。
        """
        raise NotImplementedError("Subclass must implement process_message_in_context")
    

    async def on_thread_timeout(
        self,
        thread_root_id: str,
        context: Dict[str, Any],
    )-> None:
        """
        [异步] (可选) Worker 因超时而终止前调用。
        在状态被存入 LRU 缓存 (L1) 前执行，可用于额外持久化到 L2 (DB)。
        
        :param thread_root_id: 当前话题的 ID。
        :param context: 此话题最后一次的状态字典。
        """
        pass