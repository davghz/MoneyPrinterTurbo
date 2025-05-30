import threading
from typing import Any, Callable, Dict


from loguru import logger # Add logger import

class TaskManager:
    def __init__(self, max_concurrent_tasks: int):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.current_tasks = 0
        self.lock = threading.Lock()
        self.queue = self.create_queue()
        self.logger = logger.bind(name=self.__class__.__name__) # Initialize logger

    def create_queue(self):
        raise NotImplementedError()

    def add_task(self, func: Callable, *args: Any, **kwargs: Any):
        with self.lock:
            if self.current_tasks < self.max_concurrent_tasks:
                self.logger.info(f"Executing task directly: {func.__name__}, current tasks: {self.current_tasks}/{self.max_concurrent_tasks}")
                self.execute_task(func, *args, **kwargs)
            else:
                self.logger.info(
                    f"Queueing task: {func.__name__}, current tasks: {self.current_tasks}/{self.max_concurrent_tasks}. Queue size: {len(self.queue) if hasattr(self.queue, '__len__') else 'N/A'}"
                )
                self.enqueue({"func": func, "args": args, "kwargs": kwargs})

    def execute_task(self, func: Callable, *args: Any, **kwargs: Any):
        thread = threading.Thread(
            target=self.run_task, args=(func, *args), kwargs=kwargs
        )
        thread.start()

    def run_task(self, func: Callable, *args: Any, **kwargs: Any):
        try:
            with self.lock:
                self.current_tasks += 1
            func(*args, **kwargs)  # call the function here, passing *args and **kwargs.
        finally:
            self.task_done()

    def check_queue(self):
        with self.lock:
            if (
                self.current_tasks < self.max_concurrent_tasks
                and not self.is_queue_empty()
            ):
                task_info = self.dequeue()
                func = task_info["func"]
                args = task_info.get("args", ())
                kwargs = task_info.get("kwargs", {})
                self.execute_task(func, *args, **kwargs)

    def task_done(self):
        with self.lock:
            self.current_tasks -= 1
        self.check_queue()

    def enqueue(self, task: Dict):
        raise NotImplementedError()

    def dequeue(self):
        raise NotImplementedError()

    def is_queue_empty(self):
        raise NotImplementedError()
