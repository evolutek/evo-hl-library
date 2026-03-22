"""RPLidar driver, fake implementation for testing without hardware."""

from __future__ import annotations

import logging
import time
from typing import Generator

from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.event import Event

log = logging.getLogger(__name__)


class RPLidarFake(Lidar2D):
    """In-memory RPLidar for tests and simulation."""

    def __init__(self, name: str):
        super().__init__(name)
        self._scanning = False
        self._measures: list[Lidar2DMeasure] = []
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()

    @property
    def scanning(self) -> bool:
        return self._scanning

    def init(self) -> None:
        log.info("RPLidar fake '%s' initialized", self.name)

    def close(self) -> None:
        self._scanning = False
        self._measures.clear()
        log.info("RPLidar fake '%s' closed", self.name)

    def start(self) -> Task[None]:
        self._scanning = True
        log.info("RPLidar fake '%s' scanning started", self.name)
        return ImmediateResultTask(None)

    def stop(self) -> Task[None]:
        self._scanning = False
        log.info("RPLidar fake '%s' scanning stopped", self.name)
        return ImmediateResultTask(None)

    def iter(self, duration: float | None = None) -> Generator[Lidar2DMeasure, None, None]:
        start_time = time.monotonic()
        for measure in self._measures:
            if duration is not None and (time.monotonic() - start_time) >= duration:
                break
            yield measure

    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        return self._scan_event

    def inject_measures(self, measures: list[Lidar2DMeasure]) -> None:
        """Inject measures for testing."""
        self._measures = list(measures)

    def inject_scan(self, scan: list[Lidar2DMeasure]) -> None:
        """Inject a complete scan and trigger the scan event."""
        self._scan_event.trigger(scan)
