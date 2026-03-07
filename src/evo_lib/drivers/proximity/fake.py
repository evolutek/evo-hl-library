"""Proximity sensor driver: fake implementation for testing."""

from __future__ import annotations

import logging

from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIOEdge
from evo_lib.interfaces.proximity import ProximitySensor
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class ProximityFake(ProximitySensor):
    """In-memory proximity sensor for tests and simulation.

    Use inject_input() to simulate detection state changes.
    """

    def __init__(self, name: str, pin: int):
        super().__init__(name)
        self._pin = pin
        self._state: bool = False
        self._event: Event[bool] | None = None
        self._edge: GPIOEdge = GPIOEdge.BOTH

    def init(self) -> None:
        self._state = False
        self._event = None
        log.info("ProximityFake '%s' initialized (pin %d)", self._name, self._pin)

    def close(self) -> None:
        self._state = False
        self._event = None
        log.info("ProximityFake '%s' closed (pin %d)", self._name, self._pin)

    def read(self) -> Task[bool]:
        """Read proximity state. True = object detected."""
        return ImmediateResultTask(self._state)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        self._edge = edge
        self._event = Event()
        return self._event

    def inject_input(self, value: bool) -> None:
        """Inject a detection state for testing. Triggers interrupt if active."""
        old = self._state
        self._state = value
        if self._event is not None and value != old:
            fire = (
                self._edge == GPIOEdge.BOTH
                or (self._edge == GPIOEdge.RISING and value)
                or (self._edge == GPIOEdge.FALLING and not value)
            )
            if fire:
                self._event.trigger(value)
