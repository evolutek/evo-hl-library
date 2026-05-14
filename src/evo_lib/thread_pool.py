from queue import Queue
from threading import Lock, Thread
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

    def start(self) -> None:
        if self.thread is not None:
            return
        self.thread = Thread(target=self._loop)
        self.thread.start()

    def wait_stopped(self) -> None:
        self.thread.join()
        self.thread = None

    def _loop(self) -> None:
        # First iteration claims the task that triggered this worker's spawn.
        first = True
        while True:
            if not first:
                with self.pool.lock:
                    self.pool._available_slots += 1
            first = False
            task = self.pool.queue.get()
            if task is None:
                break
            result, func, args, kwargs = task
            try:
                result.complete(func(*args, **kwargs))
            except Exception as e:
                result.error(e)


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
        self._stopping = False
        # Workers about to enter queue.get() with no claim yet.
        self._available_slots = 0

    def set_max_workers(self, max_workers: int) -> None:
        self.max_workers = max_workers

    def _create_worker(self) -> WorkerThread:
        worker = WorkerThread(self)
        self.workers.append(worker)
        worker.start()
        return worker

    def exec[T](self, callback: Callable[..., T], *args, **kwargs) -> Task[T]:
        if self._stopping:
            raise RuntimeError("ThreadPoolExecutor is stopping, cannot submit new tasks")

        result = DelayedTask()
        with self.lock:
            if self._available_slots > 0:
                self._available_slots -= 1
            elif self.max_workers == 0 or len(self.workers) < self.max_workers:
                self._create_worker()
            else:
                self.logger.warning("Maximum number of workers reached, the task will be queued")
            self.queue.put((result, callback, args, kwargs))
        return result

    def stop(self) -> None:
        self._stopping = True
        # Send one sentinel per worker so each one exits its loop
        for _ in self.workers:
            self.queue.put(None)

        for worker in self.workers:
            worker.wait_stopped()

        self.workers.clear()
