"""RPLidar driver: 2D scanning lidar via rplidar-roboticia library.

The RPLidar A2 is a rotating 2D lidar connected via USB serial.
Uses the rplidar-roboticia library (already in rpi extras).
"""

import logging
import math
import os
import threading
import time
from collections import deque
from typing import Generator

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task

# Lazy-loaded
_rplidar = None


class RPLidarDriver(Lidar2D):
    """RPLidar A2 driver via rplidar-roboticia library."""

    def __init__(
        self,
        name: str,
        port: str,
        baudrate: int = 115200,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._port = port
        self._baudrate = baudrate
        self._log = logger or logging.getLogger(__name__)
        self._lidar = None
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()
        self._scan_thread: threading.Thread | None = None
        self._running = False
        self._stop_r, self._stop_w = os.pipe()
        self._measures: deque[Lidar2DMeasure] = deque(maxlen=10000)
        self._data_ready = threading.Event()

    def init(self) -> None:
        global _rplidar
        if _rplidar is None:
            import rplidar

            _rplidar = rplidar

        self._lidar = _rplidar.RPLidar(self._port, baudrate=self._baudrate)
        self._log.info("RPLidar '%s' initialized on %s", self.name, self._port)

    def close(self) -> None:
        self.stop().wait()
        if self._stop_w >= 0:
            os.close(self._stop_r)
            os.close(self._stop_w)
            self._stop_r, self._stop_w = -1, -1
        if self._lidar is not None:
            self._lidar.stop()
            self._lidar.disconnect()
            self._lidar = None
        self._log.info("RPLidar '%s' closed", self.name)

    def start(self) -> Task[None]:
        if self._running:
            return ImmediateResultTask(None)
        self._running = True
        self._scan_thread = threading.Thread(
            target=self._scan_loop, daemon=True, name=f"rplidar-{self.name}"
        )
        self._scan_thread.start()
        return ImmediateResultTask(None)

    def stop(self) -> Task[None]:
        if not self._running:
            return ImmediateResultTask(None)
        self._running = False
        if self._stop_w >= 0:
            os.write(self._stop_w, b"\x00")
        if self._scan_thread is not None:
            self._scan_thread.join(timeout=3.0)
            self._scan_thread = None
        return ImmediateResultTask(None)

    def iter(self, duration: float | None = None) -> Generator[Lidar2DMeasure, None, None]:
        start = time.monotonic()
        while True:
            if duration is not None and time.monotonic() - start >= duration:
                return
            if self._measures:
                yield self._measures.popleft()
            else:
                self._data_ready.clear()
                self._data_ready.wait(timeout=0.1)

    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        return self._scan_event

    def _scan_loop(self) -> None:
        """Background thread: read scans and fire events."""
        try:
            for scan in self._lidar.iter_scans():
                if not self._running:
                    break
                batch = []
                ts = time.monotonic()
                for quality, angle_deg, distance_mm in scan:
                    measure = Lidar2DMeasure(
                        angle=math.radians(angle_deg),
                        distance=distance_mm,
                        timestamp=ts,
                        quality=quality,
                    )
                    batch.append(measure)
                    self._measures.append(measure)
                self._data_ready.set()
                self._scan_event.trigger(batch)
        except Exception as e:
            if self._running:
                self._log.error("RPLidar scan error: %s", e)
        finally:
            self._running = False


class RPLidarDefinition(DriverDefinition):
    """Factory for RPLidarDriver from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_required("port", ArgTypes.String())
        defn.add_optional("baudrate", ArgTypes.U32(), 115200)
        return defn

    def create(self, args: DriverInitArgs) -> RPLidarDriver:
        name = args.get("name")
        return RPLidarDriver(
            name=name,
            port=args.get("port"),
            baudrate=args.get("baudrate"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
