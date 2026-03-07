"""Recalibration sensor: wraps a GPIO pin with active-low logic."""

from __future__ import annotations

import logging

from evo_lib.interfaces.recal import RecalSensor
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class RecalGPIO(RecalSensor):
    """Recalibration sensor on a GPIO pin (active-low: triggered when pin is low)."""

    def __init__(self, name: str, gpio: GPIO):
        super().__init__(name)
        self._gpio = gpio
        self._event: Event[bool] = Event()

    def init(self) -> None:
        # Subscribe to GPIO interrupts and translate to recal events
        gpio_event = self._gpio.interrupt(GPIOEdge.BOTH)
        gpio_event.register(lambda state: self._event.trigger(not state))
        log.info("RecalGPIO '%s' initialized", self._name)

    def close(self) -> None:
        pass  # underlying GPIO closed externally

    def is_triggered(self) -> Task[bool]:
        # Active-low: triggered when GPIO reads False
        value = self._gpio.read().wait()
        return ImmediateResultTask(not value)

    def on_trigger(self) -> Event[bool]:
        return self._event
