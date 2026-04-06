"""Lidar2D drivers: virtual implementations for testing and simulation."""

import logging
import time
from collections import deque
from typing import Generator

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class Lidar2DVirtual(Lidar2D):
    """In-memory lidar for tests and simulation."""

    def __init__(self, name: str, logger: logging.Logger | None = None):
        super().__init__(name)
        self._log = logger or logging.getLogger(__name__)
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()
        self._measures: deque[Lidar2DMeasure] = deque(maxlen=10000)
        self._running = False

    def init(self) -> None:
        self._log.info("Lidar2DVirtual '%s' initialized", self.name)

    def close(self) -> None:
        self._running = False

    def start(self) -> Task[None]:
        self._running = True
        return ImmediateResultTask(None)

    def stop(self) -> Task[None]:
        self._running = False
        return ImmediateResultTask(None)

    def iter(self, duration: float | None = None) -> Generator[Lidar2DMeasure, None, None]:
        start = time.monotonic()
        while self._measures:
            if duration is not None and time.monotonic() - start >= duration:
                return
            yield self._measures.popleft()

    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        return self._scan_event

    def inject_scan(self, measures: list[Lidar2DMeasure]) -> None:
        """Inject a scan for testing. Fires the on_scan event."""
        for m in measures:
            self._measures.append(m)
        self._scan_event.trigger(measures)


class Lidar2DVirtualDefinition(DriverDefinition):
    """Factory for Lidar2DVirtual from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        return defn

    def create(self, args: DriverInitArgs) -> Lidar2DVirtual:
        name = args.get("name")
        return Lidar2DVirtual(
            name=name,
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
