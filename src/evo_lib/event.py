"""Multi-shot event primitive for driver notifications.

An Event can fire multiple times (unlike Result which is one-shot).
Typical use: GPIO interrupts, sensor triggers, periodic updates.

    event = gpio.interrupt(GPIOEdge.RISING)
    event.register(lambda v: print("triggered!"))
    event.wait()  # blocks until next trigger
"""

from __future__ import annotations

import threading
from typing import Callable, Generic, TypeVar

T = TypeVar("T")


class Event(Generic[T]):
    """Multi-shot event with callbacks and blocking wait.

    Thread-safe. Multiple threads can wait or register callbacks
    concurrently. Each ``trigger()`` wakes all waiters and invokes
    all registered callbacks.
    """

    def __init__(self):
        self._callbacks: list[Callable[[T], None]] = []
        self._condition = threading.Condition()
        self._last_value: T | None = None
        self._generation = 0

    def register(self, callback: Callable[[T], None]) -> None:
        """Add a callback invoked on every future trigger."""
        with self._condition:
            self._callbacks.append(callback)

    def unregister(self, callback: Callable[[T], None]) -> None:
        """Remove a previously registered callback."""
        with self._condition:
            self._callbacks.remove(callback)

    def wait(self) -> T:
        """Block until the next trigger and return its value.

        If the event was already triggered in the past, this still
        waits for the *next* trigger (not a past one).
        """
        with self._condition:
            gen = self._generation
            while self._generation == gen:
                self._condition.wait()
            return self._last_value

    def trigger(self, value: T = None) -> None:
        """Fire the event: wake all waiters and invoke all callbacks."""
        with self._condition:
            self._last_value = value
            self._generation += 1
            self._condition.notify_all()
            callbacks = list(self._callbacks)
        for cb in callbacks:
            cb(value)
