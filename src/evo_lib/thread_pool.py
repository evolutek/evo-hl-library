from threading import Thread, Lock, Event
from queue import Queue
from typing import Callable

from evo_hl.task import Task, DelayedTask
from evo_hl.executor import Executor


class WorkerThread:
    """Represent a thread in a thread pool.
    Should not be used directly, use ``ThreadPool`` instead.
    """

    def __init__(self, pool: ThreadPoolExecutor):
        self.pool = pool
        self.thread: Thread = None
        self.busy = Event()
        self.queue: Queue[None | tuple[DelayedTask, Callable, list, dict]] = Queue()

    def start(self) -> None:
        if self.thread is not None:
            return
        self.busy.clear()
        self.thread = Thread(target = self._loop)
        self.thread.start()

    def stop(self) -> None:
        self.queue.put_nowait(None)

    def wait_stopped(self) -> None:
        self.thread.join()
        self.thread = None

    def _loop(self) -> None:
        while True:
            with self.pool.lock:
                if self.queue.empty() and len(self.pool.queue) > 0:
                    task = self.pool.queue.pop()
                else:
                    task = self.queue.get()
                    if task is None:
                        break
                self.busy.set()
            result, func, args, kwargs = task
            result.complete(func(*args, **kwargs))
            self.busy.clear()

    def run[T](self, func: Callable[...,T], *args, **kwargs) -> DelayedTask[T]:
        result = DelayedTask()
        self.queue.put_nowait((result, func, args, kwargs))
        return result


# This is basically a thread pool
class ThreadPoolExecutor(Executor):
    """A thread pool (used to run callbacks in workers threads)."""

    def __init__(self, logger: Logger, max_workers: int = 0):
        self.workers: list[WorkerThread] = []
        self.queue: list[None | tuple[DelayedTask, Callable, list, dict]] = []
        self.lock = Lock()
        self.logger = logger
        self.max_workers = max_workers

    def set_max_workers(self, max_workers: int) -> None:
        self.max_workers = max_workers

    def _create_worker(self) -> WorkerThread:
        worker = WorkerThread(self)
        worker.start()
        self.workers.append(worker)
        return worker

    def exec[T](self, callback: Callable[...,T], *args, **kwargs) -> Task[T]:
        self.lock.acquire()

        for worker in self.workers:
            if not worker.busy.is_set() and worker.queue.empty():
                return worker.run(callback, *args, **kwargs)

        if self.max_workers > 0 and len(self.workers) >= self.max_workers:
            self.logger.warning("Maximum number of workers reached, the task will be queued")
            result = DelayedTask()
            self.queue.append((result, callback, args, kwargs))
            self.lock.release()
            return result

        self.lock.release()

        # Create a new worker thread to run the task
        worker = self._create_worker()
        return worker.run(callback, *args, **kwargs)

    def stop(self) -> None:
        for worker in self.workers:
            worker.stop()

        for worker in self.workers:
            worker.wait_stopped()

        self.workers.clear()
