"""Multi-shot event primitive for driver notifications.

An Event can fire multiple times (unlike Result which is one-shot).
Typical use: GPIO interrupts, sensor triggers, periodic updates.

    event = gpio.interrupt(GPIOEdge.RISING)
    event.register(lambda v: print("Triggered!"))
    event.wait() # Blocks until next trigger
"""

import threading
from typing import Callable
import time

from .listeners import Listeners, Listener


class Event[*T](Listeners[*T]):
    """
    Multi-shot event with callbacks and blocking wait.

    Thread-safe. Multiple threads can wait or register callbacks
    concurrently. Each ``trigger()`` wakes all waiters and invokes
    all registered callbacks.
    """

    def __init__(self):
        super().__init__()
        self._generation = 0
        self._condition = threading.Condition()

    def register(self, callback: Callable[[*T], None]) -> Listener:
        """Add a callback invoked on every future trigger."""
        with self._condition:
            return super().register(callback)

    def unregister(self, listener: Listener) -> None:
        """Remove a previously registered callback."""
        with self._condition:
            super().unregister(listener)

    def wait(self, timeout: float | None = None) -> bool:
        """Block until the next trigger and return its value.

        If the event was already triggered in the past, this still
        waits for the *next* trigger (not a past one).
        """
        with self._condition:
            gen = self._generation
            if timeout is None:
                while self._generation == gen:
                    self._condition.wait()
                return True
            else:
                start_timestamp = time.time()
                while self._generation == gen:
                    remaining = timeout - (time.time() - start_timestamp)
                    if remaining <= 0:
                        return False
                    if not self._condition.wait(remaining):
                        return False
                return True

    def trigger(self, *args: *T) -> None:
        """Fire the event: wake all waiters and invoke all callbacks."""
        with self._condition:
            self._generation += 1
            self._condition.notify_all()
            listeners = super()._trigger()

        # Call callbacks outside the lock to avoid blocking other thread that
        # try to used this event (calling all listeners can take some time)
        for listener in listeners:
            listener._callback(*args)
