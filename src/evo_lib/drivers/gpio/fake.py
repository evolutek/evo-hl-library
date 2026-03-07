"""GPIO driver: fake implementation for testing without hardware."""

from __future__ import annotations

import logging
import threading

from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class GPIOFake(GPIO):
    """In-memory GPIO for tests and simulation, one pin per instance."""

    def __init__(self, name: str, pin: int):
        super().__init__(name)
        self._pin = pin
        self._lock = threading.Lock()
        self._state: bool = False
        self._event: Event[bool] | None = None
        self._edge: GPIOEdge = GPIOEdge.BOTH

    def init(self) -> None:
        self._state = False
        self._event = None
        log.info("GPIOFake '%s' initialized (pin %d)", self._name, self._pin)

    def close(self) -> None:
        self._state = False
        self._event = None
        log.info("GPIOFake '%s' closed (pin %d)", self._name, self._pin)

    def read(self) -> Task[bool]:
        return ImmediateResultTask(self._state)

    def write(self, state: bool) -> Task[None]:
        self._state = state
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        self._edge = edge
        self._event = Event()
        return self._event

    def inject_input(self, value: bool) -> None:
        """Inject a value for testing. Triggers the interrupt event if active."""
        with self._lock:
            old = self._state
            self._state = value
            event = self._event
            edge = self._edge
        if event is not None and value != old:
            fire = (
                edge == GPIOEdge.BOTH
                or (edge == GPIOEdge.RISING and value)
                or (edge == GPIOEdge.FALLING and not value)
            )
            if fire:
                event.trigger(value)
