"""Recalibration sensor: fake implementation for testing."""

from __future__ import annotations

import logging

from evo_lib.interfaces.recal import RecalSensor
from evo_lib.event import Event
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class RecalFake(RecalSensor):
    """In-memory recal sensor for tests and simulation."""

    def __init__(self, name: str):
        super().__init__(name)
        self._triggered: bool = False
        self._event: Event[bool] = Event()

    def init(self) -> None:
        self._triggered = False
        log.info("RecalFake '%s' initialized", self._name)

    def close(self) -> None:
        self._triggered = False
        log.info("RecalFake '%s' closed", self._name)

    def is_triggered(self) -> Task[bool]:
        return ImmediateResultTask(self._triggered)

    def on_trigger(self) -> Event[bool]:
        return self._event

    def inject(self, triggered: bool) -> None:
        """Inject a trigger state for testing. Fires the event on change."""
        old = self._triggered
        self._triggered = triggered
        if triggered != old:
            self._event.trigger(triggered)
