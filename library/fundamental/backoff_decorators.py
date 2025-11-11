from .typing import *
from .externals import *


__all__ = [
    "backoff",
    "backoff_async",
]


_RawFunctionType = TypeVar("_RawFunctionType", bound=Callable[..., Any])
_RawFunctionAsyncType = TypeVar("_RawFunctionAsyncType", bound=Callable[..., Awaitable[Any]])


def backoff(
    backoff_seconds: List[float],
    trigger_exceptions: Tuple[Type[Exception], ...] = (Exception,),
)-> Callable[[_RawFunctionType], _RawFunctionType]:

    def decorator(func: _RawFunctionType)-> _RawFunctionType:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any)-> Any:
            max_attempts = len(backoff_seconds) + 1
            attempts = 0
            while attempts < max_attempts:
                try:
                    attempts += 1
                    return func(*args, **kwargs)
                except trigger_exceptions:
                    if attempts >= max_attempts: raise
                    wait_time = backoff_seconds[attempts - 1]
                    sleep(normalvariate(wait_time, wait_time / 3))
        return cast(_RawFunctionType, wrapper)
    return decorator


def backoff_async(
    backoff_seconds: List[float],
    trigger_exceptions: Tuple[Type[Exception], ...] = (Exception,),
)-> Callable[[_RawFunctionAsyncType], _RawFunctionAsyncType]:

    def decorator(func: _RawFunctionAsyncType)-> _RawFunctionAsyncType:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any)-> Any:
            max_attempts = len(backoff_seconds) + 1
            attempts = 0
            while attempts < max_attempts:
                try:
                    attempts += 1
                    return await func(*args, **kwargs)
                except trigger_exceptions:
                    if attempts >= max_attempts: raise
                    wait_time = backoff_seconds[attempts - 1]
                    await asyncio.sleep(normalvariate(wait_time, wait_time / 3))
        return cast(_RawFunctionAsyncType, wrapper)
    return decorator