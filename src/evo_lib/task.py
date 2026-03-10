"""Long-running task with progress tracking and cancellation.

A Task is a Result that hasn't completed yet. The producer calls
``complete()`` or ``abort()``, the consumer calls ``wait()`` or
registers callbacks. Supports progress tracking and cancellation.

    task = Task(on_cancel=motor.stop)
    task.progress = 0.5       # 50% done
    task.complete(result)     # mark done, wake waiters
    # or
    task.cancel()             # calls on_cancel, then aborts
"""

from __future__ import annotations

import threading
from typing import Callable, Generic, TypeVar

from evo_hl.result import Result

T = TypeVar("T")


class CancelledError(Exception):
    """Raised when waiting on a cancelled task."""


class Task(Result[T], Generic[T]):
    """Long-running operation with progress and cancellation.

    Created by the producer (driver), consumed by the caller.
    Thread-safe: producer and consumer can be on different threads.
    """

    def __init__(self, on_cancel: Callable[[], None] | None = None):
        self._on_cancel = on_cancel
        self._progress = 0.0
        self._value: T | None = None
        self._error: Exception | None = None
        self._done = threading.Event()
        self._complete_callbacks: list[Callable[[T], None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._lock = threading.Lock()

    # -- Consumer API --

    def wait(self) -> T:
        """Block until the task completes. Returns value or raises error."""
        self._done.wait()
        if self._error is not None:
            raise self._error
        return self._value

    def is_done(self) -> bool:
        return self._done.is_set()

    def on_complete(self, callback: Callable[[T], None]) -> Result[T]:
        with self._lock:
            if self._done.is_set() and self._error is None:
                callback(self._value)
            else:
                self._complete_callbacks.append(callback)
        return self

    def on_error(self, callback: Callable[[Exception], None]) -> Result[T]:
        with self._lock:
            if self._done.is_set() and self._error is not None:
                callback(self._error)
            else:
                self._error_callbacks.append(callback)
        return self

    @property
    def progress(self) -> float:
        return self._progress

    @progress.setter
    def progress(self, value: float) -> None:
        self._progress = value

    def cancel(self) -> None:
        """Cancel the task. Calls on_cancel handler, then aborts."""
        if self._on_cancel is not None:
            self._on_cancel()
        self.abort(CancelledError("Task cancelled"))

    # -- Producer API --

    def complete(self, value: T = None) -> None:
        """Mark the task as successfully completed."""
        with self._lock:
            self._value = value
            self._progress = 1.0
            self._done.set()
            callbacks = list(self._complete_callbacks)
        for cb in callbacks:
            cb(value)

    def abort(self, error: Exception) -> None:
        """Mark the task as failed."""
        with self._lock:
            self._error = error
            self._done.set()
            callbacks = list(self._error_callbacks)
        for cb in callbacks:
            cb(error)
