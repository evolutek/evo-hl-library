from queue import Queue
from threading import Event, Lock, Thread
from typing import Callable

from evo_lib.executor import Executor
from evo_lib.logger import Logger
from evo_lib.task import DelayedTask, Task


class WorkerThread:
    """Represent a thread in a thread pool.
    Should not be used directly, use ``ThreadPoolExecutor`` instead.
    """

    def __init__(self, pool: ThreadPoolExecutor):
        self.pool = pool
        self.thread: Thread = None
        self.busy = Event()

    def start(self) -> None:
        if self.thread is not None:
            return
        self.busy.clear()
        self.thread = Thread(target=self._loop)
        self.thread.start()

    def wait_stopped(self) -> None:
        self.thread.join()
        self.thread = None

    def _loop(self) -> None:
        while True:
            task = self.pool.queue.get()
            if task is None:
                break

            self.busy.set()
            result, func, args, kwargs = task
            try:
                result.complete(func(*args, **kwargs))
            except Exception as e:
                result.error(e)
            finally:
                self.busy.clear()


class ThreadPoolExecutor(Executor):
    """A thread pool (used to run callbacks in workers threads).

    All workers share a single queue. Tasks are dispatched to whichever
    worker picks them up first, avoiding per-worker queues and
    work-stealing complexity.
    """

    def __init__(self, logger: Logger, max_workers: int = 0):
        self.workers: list[WorkerThread] = []
        self.queue: Queue[None | tuple[DelayedTask, Callable, list, dict]] = Queue()
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

    def exec[T](self, callback: Callable[..., T], *args, **kwargs) -> Task[T]:
        result = DelayedTask()
        self.queue.put((result, callback, args, kwargs))

        with self.lock:
            # If any worker is idle, it will pick up the task from the queue
            for worker in self.workers:
                if not worker.busy.is_set():
                    return result

            # All workers are busy, create a new one if allowed
            if self.max_workers == 0 or len(self.workers) < self.max_workers:
                self._create_worker()
            else:
                self.logger.warning("Maximum number of workers reached, the task will be queued")

        return result

    def stop(self) -> None:
        # Send one sentinel per worker so each one exits its loop
        for _ in self.workers:
            self.queue.put(None)

        for worker in self.workers:
            worker.wait_stopped()

        self.workers.clear()
