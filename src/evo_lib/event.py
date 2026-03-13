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
        start_timestamp = time.time()

        with self._condition:
            gen = self._generation

            while self._generation == gen:
                ellapsed_time = time.time() - start_timestamp
                remaning_time = timeout - ellapsed_time
                if remaning_time <= 0:
                    return False # Timeout

                if not self._condition.wait(remaning_time):
                    return False # Timeout

            return True # Event triggered

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
