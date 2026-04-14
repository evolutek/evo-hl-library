"""Standalone generic virtual lidar for tests and simulation.

``Lidar2DVirtual`` is not a drop-in twin of any specific driver: its
constructor only takes ``(name, logger)`` and it exposes ``inject_scan``
for unit tests that do not care which hardware model is being simulated.

Per-driver drop-in virtuals (matching each real driver's constructor and
DriverDefinition surface exactly) live alongside their real counterparts:
``RPLidarVirtual`` in ``rplidar.py``, ``SickTIMVirtual`` in ``sick_tim.py``,
``LD06LidarVirtual`` in ``ld06.py``.
"""

import time
from collections import deque
from typing import Generator

from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class Lidar2DVirtual(Lidar2D):
    """Standalone in-memory lidar for tests and simulation.

    Not a drop-in twin of RPLidar / SickTIM / LD06 — those live alongside
    their real counterparts. Use this when the specific hardware model
    does not matter.
    """

    def __init__(self, name: str, logger: Logger):
        super().__init__(name)
        self._log = logger
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()
        self._measures: deque[Lidar2DMeasure] = deque(maxlen=10000)
        self._running = False

    def init(self) -> Task[()]:
        self._log.info(f"Lidar2DVirtual '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        self._running = False

    def start(self) -> Task[()]:
        self._running = True
        return ImmediateResultTask()

    def stop(self) -> Task[()]:
        self._running = False
        return ImmediateResultTask()

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
        super().__init__(Lidar2D.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        return DriverInitArgsDefinition()

    def create(self, args: DriverInitArgs) -> Lidar2DVirtual:
        return Lidar2DVirtual(
            name=args.get_name(),
            logger=self._logger,
        )
