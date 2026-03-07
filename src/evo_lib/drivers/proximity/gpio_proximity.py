"""Proximity sensor driver: wraps a GPIO pin as read-only."""

from __future__ import annotations

from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.interfaces.proximity import ProximitySensor
from evo_lib.task import Task


class ProximityGPIO(ProximitySensor):
    """Read-only proximity sensor wrapping an existing GPIO pin.

    Delegates read() and interrupt() to the underlying GPIO.
    Does not expose write() since sensors are input-only.
    """

    def __init__(self, name: str, gpio: GPIO):
        super().__init__(name)
        self._gpio = gpio

    def init(self) -> None:
        pass  # underlying GPIO is initialized externally

    def close(self) -> None:
        pass  # underlying GPIO is closed externally

    def read(self) -> Task[bool]:
        return self._gpio.read()

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        return self._gpio.interrupt(edge)
