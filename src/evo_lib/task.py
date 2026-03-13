"""
Long-running task with progress tracking and cancellation.

A Task is a Result that hasn't completed yet. The producer calls
``complete()`` or ``abort()``, the consumer calls ``wait()`` or
registers callbacks. Supports progress tracking and cancellation.

    task = Task(on_cancel=motor.stop)
    task.complete(result)     # mark done, wake waiters
    # or
    task.cancel()             # calls on_cancel, then aborts
"""

from abc import ABC, abstractmethod
from typing import Callable
import threading


class TaskCancelledError(Exception):
    """Raised when waiting on a cancelled task."""


class TaskTimeoutError(Exception):
    """Raised when ``wait`` method is called with a timeout and the timeout time
    has ellapsed."""


class Task[T](ABC):
    """
    An asynchronous operation with cancellation.
    Can have multiple implementation like:
    - ImmediateResultTask & ImmediateErrorTask : No syncronisation mecanisms
      because the result or error is already known when constructor is called
      (used for fast operation that do not block the code).
    - DelayedTask : Has inter-thread syncronisation mecanisms in order to be
      used to long running operations.
    """

    # Consumer API

    @abstractmethod
    def wait(self, timeout: float | None = None) -> T:
        """Block until the result is available.
        Returns the value on success, raises on error.
        """

    @abstractmethod
    def is_done(self) -> bool:
        """True if the result (or error) is available."""

    @abstractmethod
    def on_complete(self, callback: Callable[[T], None]) -> Task[T]:
        """Register a callback invoked with the value on success."""

    @abstractmethod
    def on_error(self, callback: Callable[[Exception], None]) -> Task[T]:
        """Register a callback invoked with the exception on failure."""

    @abstractmethod
    def cancel(self) -> Task[T]:
        """Cancel the task. Calls on_cancel handler, then dispatch cancel
        exception."""


class ImmediateResultTask[T](Task[T]):
    def __init__(self, result: T):
        super().__init__()
        self._result = result
        self._canceled: bool = False

    # Consumer API (implement abstract method of parent class)

    def wait(self, timeout: float | None = None) -> T:
        """Immediatly return the result value."""
        if self._canceled:
            raise TaskCancelledError()
        # No need to wait, result is already known
        return self._result

    def is_done(self) -> bool:
        """True if the result (or error) is available."""
        return True

    def on_complete(self, callback: Callable[[T], None]) -> ImmediateResultTask[T]:
        """As the result is already known, immediatly invoke the callback with
        the result value."""
        if not self._canceled:
            callback(self._result)
        return self

    def on_error(self, callback: Callable[[Exception], None]) -> ImmediateResultTask[T]:
        """Do nothing since there is no error."""
        return self

    def cancel(self) -> ImmediateResultTask[T]:
        """Cause all subsequent calls to on_complete to do nothing and calls to
        wait raise a canceled exception."""
        self._canceled = True
        return self


class ImmediateErrorTask[T](Task[T]):
    """
    An implementation of Task that has inter-thread syncronisation mecanisms
    in order to be used to long running operations and from multiple different
    threads.
    """
    def __init__(self, error: T):
        super().__init__()
        self._error = error
        self._canceled: bool = False

    # Consumer API (implement abstract method of parent class)

    def wait(self, timeout: float | None = None) -> T:
        """Immediatly return raise the error."""
        if self._canceled:
            raise TaskCancelledError()
        # No need to wait, error is already known
        raise self._error

    def is_done(self) -> bool:
        """True if the result (or error) is available."""
        return True

    def on_complete(self, callback: Callable[[T], None]) -> ImmediateErrorTask[T]:
        """Do nothing since there is no result value."""
        return self

    def on_error(self, callback: Callable[[Exception], None]) -> ImmediateErrorTask[T]:
        """As the error is already known, immediatly invoke the callback with the error."""
        if not self._canceled:
            callback(self._error)
        return self

    def cancel(self) -> ImmediateErrorTask[T]:
        """Cause all subsequent calls to on_complete to do nothing and calls to wait raise a canceled exception."""
        self._canceled = True
        return self


class DelayedTask[T](Task[T]):
    def __init__(self, on_cancel: Callable[[], None] = None):
        self._on_cancel = on_cancel
        self._progress = 0.0
        self._value: T | None = None
        self._error: Exception | None = None
        self._done = threading.Event()
        self._complete_callbacks: list[Callable[[T], None]] = []
        self._error_callbacks: list[Callable[[Exception], None]] = []
        self._lock = threading.Lock()

    # Consumer API (implement abstract method of parent class)

    def wait(self, timeout: float | None = None) -> T:
        """Block until the task completes. Returns value or raises error."""
        if not self._done.wait(timeout):
            raise TaskTimeoutError()
        if self._error is not None:
            raise self._error
        return self._value

    def is_done(self) -> bool:
        return self._done.is_set()

    def on_complete(self, callback: Callable[[T], None]) -> DelayedTask[T]:
        with self._lock:
            if self._done.is_set() and self._error is None:
                callback(self._value)
            else:
                self._complete_callbacks.append(callback)
        return self

    def on_error(self, callback: Callable[[Exception], None]) -> DelayedTask[T]:
        with self._lock:
            if self._done.is_set() and self._error is not None:
                callback(self._error)
            else:
                self._error_callbacks.append(callback)
        return self

    def cancel(self) -> DelayedTask[T]:
        """Cancel the task. Calls on_cancel handler, then aborts."""
        if self._on_cancel is not None:
            self._on_cancel()
        self.abort(TaskCancelledError("Task cancelled"))

    # Producer API

    def complete(self, value: T = None) -> None:
        """Mark the task as successfully completed."""
        with self._lock:
            self._value = value
            self._progress = 1.0
            self._done.set()
            callbacks = list(self._complete_callbacks)
        for cb in callbacks:
            cb(value)

    def error(self, error: Exception) -> None:
        """Mark the task as failed."""
        with self._lock:
            self._error = error
            self._done.set()
            callbacks = list(self._error_callbacks)
        for cb in callbacks:
            cb(error)
