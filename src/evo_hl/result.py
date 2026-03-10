"""Async result primitives for driver operations.

Provides one-shot result types for operations that may be immediate
or delayed. Based on concurrent.futures.Future for asyncio bridging.

    InstantResult — value already available, no thread.
    ErrorResult   — immediate error, no thread.
    DelayedResult — wraps a Future, resolved by a thread pool.
    TaskRunner    — thin wrapper around ThreadPoolExecutor.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Result(ABC, Generic[T]):
    """One-shot result of an operation that may be immediate or delayed."""

    @abstractmethod
    def wait(self) -> T:
        """Block until the result is available.

        Returns the value on success, raises on error.
        """

    @abstractmethod
    def is_done(self) -> bool:
        """True if the result (or error) is available."""

    @abstractmethod
    def on_complete(self, callback: Callable[[T], None]) -> Result[T]:
        """Register a callback invoked with the value on success."""

    @abstractmethod
    def on_error(self, callback: Callable[[Exception], None]) -> Result[T]:
        """Register a callback invoked with the exception on failure."""


class InstantResult(Result[T]):
    """Result that is immediately available (no thread)."""

    def __init__(self, value: T = None):
        self._value = value

    def wait(self) -> T:
        return self._value

    def is_done(self) -> bool:
        return True

    def on_complete(self, callback: Callable[[T], None]) -> Result[T]:
        callback(self._value)
        return self

    def on_error(self, callback: Callable[[Exception], None]) -> Result[T]:
        return self  # no error possible


class ErrorResult(Result[T]):
    """Immediate error result (no thread)."""

    def __init__(self, error: Exception):
        self._error = error

    def wait(self) -> T:
        raise self._error

    def is_done(self) -> bool:
        return True

    def on_complete(self, callback: Callable[[T], None]) -> Result[T]:
        return self  # no value

    def on_error(self, callback: Callable[[Exception], None]) -> Result[T]:
        callback(self._error)
        return self


class DelayedResult(Result[T]):
    """Result backed by a concurrent.futures.Future.

    Use ``result.future`` for asyncio bridging::

        await asyncio.wrap_future(result.future)
    """

    def __init__(self, future: Future[T]):
        self._future = future

    @property
    def future(self) -> Future[T]:
        """The underlying Future (for asyncio bridging)."""
        return self._future

    def wait(self) -> T:
        return self._future.result()

    def is_done(self) -> bool:
        return self._future.done()

    def on_complete(self, callback: Callable[[T], None]) -> Result[T]:
        def _on_done(f: Future[T]) -> None:
            if not f.cancelled() and f.exception() is None:
                callback(f.result())

        self._future.add_done_callback(_on_done)
        return self

    def on_error(self, callback: Callable[[Exception], None]) -> Result[T]:
        def _on_done(f: Future[T]) -> None:
            exc = f.exception()
            if exc is not None:
                callback(exc)

        self._future.add_done_callback(_on_done)
        return self


class TaskRunner:
    """Thread pool that returns DelayedResult instances.

    Thin wrapper around ThreadPoolExecutor. Replaces ~100 lines of
    custom thread pool code with a standard library call.
    """

    def __init__(self, max_workers: int = 4):
        self._executor = ThreadPoolExecutor(max_workers=max_workers)

    def run(self, fn: Callable[..., T], *args, **kwargs) -> DelayedResult[T]:
        """Submit a blocking function and return a DelayedResult."""
        future = self._executor.submit(fn, *args, **kwargs)
        return DelayedResult(future)

    def stop(self) -> None:
        """Shut down the thread pool, waiting for pending tasks."""
        self._executor.shutdown(wait=True)
