from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any

# Global thread pool for background tasks
_executor = ThreadPoolExecutor(max_workers=4)

def run_in_background(func: Callable, *args, **kwargs) -> Future:
    """
    Run func(*args, **kwargs) in a background thread.
    Returns a concurrent.futures.Future object.
    """
    return _executor.submit(func, *args, **kwargs) 