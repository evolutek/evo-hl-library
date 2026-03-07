"""Pump driver — implementation via GPIO pins."""

from __future__ import annotations

import logging

from evo_hl.gpio.base import GPIO
from evo_hl.pump.base import Pump

log = logging.getLogger(__name__)


class PumpGPIO(Pump):
    """Pump controlled via two GPIO pins (pump + electrovalve)."""

    def __init__(self, gpio: GPIO, pump_pin: int, ev_pin: int | None = None):
        self._gpio = gpio
        self._pump_pin = pump_pin
        self._ev_pin = ev_pin

    def grab(self) -> None:
        self._gpio.write(self._pump_pin, True)
        if self._ev_pin is not None:
            self._gpio.write(self._ev_pin, False)
        log.debug("Pump pin%d ON", self._pump_pin)

    def release(self) -> None:
        self._gpio.write(self._pump_pin, False)
        if self._ev_pin is not None:
            self._gpio.write(self._ev_pin, True)
        log.debug("Pump pin%d OFF, EV open", self._pump_pin)

    def stop_ev(self) -> None:
        if self._ev_pin is not None:
            self._gpio.write(self._ev_pin, False)
