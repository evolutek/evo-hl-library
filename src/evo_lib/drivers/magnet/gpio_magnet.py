"""Magnet driver: GPIO implementation."""

from __future__ import annotations

import logging

from evo_lib.interfaces.magnet import Magnet
from evo_lib.interfaces.gpio import GPIO
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class MagnetGPIO(Magnet):
    """Electromagnet controlled via a GPIO pin."""

    def __init__(self, name: str, gpio: GPIO):
        super().__init__(name)
        self._gpio = gpio
        self._active: bool = False

    def init(self) -> None:
        self._active = False
        log.info("MagnetGPIO '%s' initialized", self._name)

    def close(self) -> None:
        self._gpio.write(False).wait()
        self._active = False
        log.info("MagnetGPIO '%s' closed", self._name)

    def activate(self) -> Task[None]:
        self._gpio.write(True).wait()
        self._active = True
        log.debug("MagnetGPIO '%s' ON", self._name)
        return ImmediateResultTask(None)

    def deactivate(self) -> Task[None]:
        self._gpio.write(False).wait()
        self._active = False
        log.debug("MagnetGPIO '%s' OFF", self._name)
        return ImmediateResultTask(None)

    def is_active(self) -> Task[bool]:
        return ImmediateResultTask(self._active)
