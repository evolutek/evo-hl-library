import queue
from typing import Callable
from abc import ABC, abstractmethod

from evo_lib.task import Task, DelayedTask


class Executor(ABC):
    """An interface that represent something that can run functions."""
    @abstractmethod
    def exec[T](self, callback: Callable[...,T], *args, **kwargs) -> Task[T]:
        pass


class SimpleExecutor(Executor):
    """A very basic implementation of ``Executor`` that queue callback to
    run and has a method ``handle`` that call all queued callbacks.

    This class is threads-safe.
    """

    def __init__(self):
        self._pending_callbacks: queue.Queue[
            tuple[DelayedTask, Callable, tuple, dict[str, object]] | None
        ] = queue.Queue()

    def handle(self) -> None:
        """Execute all queued callback sequentially (return after all callbacks
        has been run).
        """
        try:
            while True:
                item = self._pending_callbacks.get(block = False)
                if item is None:
                    break
                task, callback, args, kwargs = item
                try:
                    task.complete(callback(*args, **kwargs))
                except Exception as e:
                    task.error(e)

        except queue.Empty:
            pass

    def run(self) -> None:
        """Like running ``handle`` in a loop but is blocking until there is a
        new queued callback so it's not cpu intensive."""
        while True:
            item = self._pending_callbacks.get(block = True)
            if item is None:
                break
            task, callback, args, kwargs = item
            try:
                task.complete(callback(*args, **kwargs))
            except Exception as e:
                task.error(e)

    def stop(self) -> None:
        """Stop the run loop."""
        self._pending_callbacks.put(None)

    def exec[T](self, callback: Callable[...,T], *args, **kwargs) -> Task[T]:
        """Add a calback to the queue. The callback will be called the next time
        ``handle`` is called or will be called asap if ``run`` has been called
        on another thread."""
        task = DelayedTask()
        self._pending_callbacks.put((task, callback, args, kwargs), block = False)
        return task
