"""Magnet driver — implementation via GPIO pin."""

from __future__ import annotations

import logging

from evo_hl.gpio.base import GPIO
from evo_hl.magnet.base import Magnet

log = logging.getLogger(__name__)


class MagnetGPIO(Magnet):
    """Electromagnet controlled via a GPIO pin."""

    def __init__(self, gpio: GPIO, pin: int):
        self._gpio = gpio
        self._pin = pin

    def on(self) -> None:
        self._gpio.write(self._pin, True)
        log.debug("Magnet pin%d ON", self._pin)

    def off(self) -> None:
        self._gpio.write(self._pin, False)
        log.debug("Magnet pin%d OFF", self._pin)
