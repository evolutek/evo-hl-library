"""Pump driver, fake implementation for testing."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from evo_lib.interfaces.pump import Pump
from evo_lib.task import ImmediateResultTask

if TYPE_CHECKING:
    from evo_lib.task import Task

log = logging.getLogger(__name__)


class PumpFake(Pump):
    """In-memory pump for tests and simulation."""

    def __init__(self, name: str = "fake-pump"):
        super().__init__(name)
        self.pump_on: bool = False
        self.ev_open: bool = False

    def init(self) -> None:
        self.pump_on = False
        self.ev_open = False

    def close(self) -> None:
        self.pump_on = False
        self.ev_open = False

    def grab(self) -> "Task[None]":
        self.pump_on = True
        self.ev_open = False
        return ImmediateResultTask(None)

    def release(self) -> "Task[None]":
        self.pump_on = False
        self.ev_open = True
        return ImmediateResultTask(None)

    def stop_ev(self) -> "Task[None]":
        self.ev_open = False
        return ImmediateResultTask(None)
