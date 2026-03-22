"""SICK TIM driver, fake implementation for testing."""

from __future__ import annotations

import logging
import time
from typing import Generator

from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class SickTIMFake(Lidar2D):
    """In-memory TIM for tests and simulation.

    Inject scan data via inject_scan(), then consume it through
    the standard Lidar2D interface.
    """

    def __init__(self, name: str, host: str = "127.0.0.1", port: int = 2112):
        super().__init__(name)
        self._host = host
        self._port = port
        self.scanning = False
        self._scans: list[list[Lidar2DMeasure]] = []
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()

    # -- Component lifecycle --

    def init(self) -> None:
        log.info("TIM fake initialized (%s:%d)", self._host, self._port)

    def close(self) -> None:
        self.scanning = False
        self._scans.clear()
        log.info("TIM fake closed")

    # -- Lidar2D interface --

    def start(self) -> Task[None]:
        self.scanning = True
        return ImmediateResultTask(None)

    def stop(self) -> Task[None]:
        self.scanning = False
        return ImmediateResultTask(None)

    def iter(self, duration: float | None = None) -> Generator[Lidar2DMeasure, None, None]:
        """Yield measures from injected scans.

        If duration is given, stops after that many seconds.
        """
        deadline = None if duration is None else time.monotonic() + duration
        for scan in self._scans:
            if deadline is not None and time.monotonic() >= deadline:
                return
            yield from scan

    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        return self._scan_event

    # -- Test helpers --

    def inject_scan(self, measures: list[Lidar2DMeasure]) -> None:
        """Add a scan to the internal buffer and trigger the event."""
        self._scans.append(measures)
        self._scan_event.trigger(measures)
