"""Pump driver — fake implementation for testing."""

from __future__ import annotations

import logging

from evo_hl.pump.base import Pump

log = logging.getLogger(__name__)


class PumpFake(Pump):
    """In-memory pump for tests and simulation."""

    def __init__(self):
        self.pump_on = False
        self.ev_open = False

    def grab(self) -> None:
        self.pump_on = True
        self.ev_open = False

    def release(self) -> None:
        self.pump_on = False
        self.ev_open = True

    def stop_ev(self) -> None:
        self.ev_open = False
