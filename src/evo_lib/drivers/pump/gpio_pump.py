"""Pump driver, implementation via GPIO pins."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from evo_lib.interfaces.pump import Pump
from evo_lib.task import ImmediateResultTask

if TYPE_CHECKING:
    from evo_lib.interfaces.gpio import GPIO
    from evo_lib.task import Task

log = logging.getLogger(__name__)


class PumpGPIO(Pump):
    """Pump controlled via two GPIO component instances (pump + electrovalve)."""

    def __init__(
        self, name: str, pin_pump: "GPIO", pin_ev: "GPIO | None" = None
    ):
        super().__init__(name)
        self._pin_pump = pin_pump
        self._pin_ev = pin_ev

    def init(self) -> None:
        log.info("PumpGPIO '%s' initialized", self.name)

    def close(self) -> None:
        # Ensure pump is off on close
        self._pin_pump.write(False).wait()
        if self._pin_ev is not None:
            self._pin_ev.write(False).wait()
        log.info("PumpGPIO '%s' closed", self.name)

    def grab(self) -> "Task[None]":
        self._pin_pump.write(True).wait()
        if self._pin_ev is not None:
            self._pin_ev.write(False).wait()
        log.debug("PumpGPIO '%s' grab: pump ON", self.name)
        return ImmediateResultTask(None)

    def release(self) -> "Task[None]":
        self._pin_pump.write(False).wait()
        if self._pin_ev is not None:
            self._pin_ev.write(True).wait()
        log.debug("PumpGPIO '%s' release: pump OFF, EV open", self.name)
        return ImmediateResultTask(None)

    def stop_ev(self) -> "Task[None]":
        if self._pin_ev is not None:
            self._pin_ev.write(False).wait()
        log.debug("PumpGPIO '%s' stop_ev", self.name)
        return ImmediateResultTask(None)
