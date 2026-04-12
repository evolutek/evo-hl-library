"""Multi-shot event primitive for driver notifications.

An Event can fire multiple times (unlike Result which is one-shot).
Typical use: GPIO interrupts, sensor triggers, periodic updates.

    event = gpio.interrupt(GPIOEdge.RISING)
    event.register(lambda v: print("Triggered!"))
    event.wait() # Blocks until next trigger
"""

import threading
import time
from typing import Callable

from .listeners import Listener, Listeners


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

    def register(self, callback: Callable[[*T], None], onetime: bool = False) -> Listener[*T]:
        """Add a callback invoked on every future trigger."""
        with self._condition:
            return super().register(callback, onetime)

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

    def transform[*U](self, callback: Callable[[*T], tuple[*U]]) -> Event[*U]:
        """Transform the event value before triggering."""
        event = Event[*U]()
        self.register(lambda *args: event.trigger(*callback(*args)))
        return event

    def debounce(self, delay_s: float) -> Event[*T]:
        """Return a debounced event: only the last value stable for ``delay_s`` fires.

        Each incoming trigger cancels any pending emission and schedules a new
        one. The downstream event only fires once the upstream has been quiet
        for ``delay_s``. Useful to filter mechanical bouncing on switches.
        """
        debounced = Event[*T]()
        lock = threading.Lock()
        timer: threading.Timer | None = None
        last_args: tuple | None = None
        # Bumped on every upstream trigger. A pending fire commits only if its
        # captured generation still matches at fire time; otherwise a newer
        # event has arrived and will schedule its own fire.
        generation = 0

        def handler(*args):
            nonlocal timer, last_args, generation
            with lock:
                last_args = args
                generation += 1
                my_gen = generation
                if timer is not None:
                    timer.cancel()

                def fire():
                    nonlocal timer
                    with lock:
                        if generation != my_gen:
                            return
                        args_to_fire = last_args
                        timer = None
                    debounced.trigger(*args_to_fire)

                timer = threading.Timer(delay_s, fire)
                timer.daemon = True
                timer.start()

        self.register(handler)
        return debounced
