"""RPLidar driver: 2D scanning lidar via rplidar-roboticia library.

The RPLidar A2 is a rotating 2D lidar connected via USB serial.
Uses the rplidar-roboticia library (already in rpi extras).
"""

import os
import time
import math
from queue import Empty, Full, Queue
from threading import Thread
from typing import TYPE_CHECKING, Iterator

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.drivers.lidar.virtual import Lidar2DVirtual
from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task

_MEASURES_QUEUE_LENGTH = 10000

# Lazy-loaded
_rplidar = None

if TYPE_CHECKING:
    import adafruit_rplidar as rplidar_type
    _rplidar = rplidar_type


class RPLidarDriver(Lidar2D):
    """RPLidar A2 driver via rplidar-roboticia library."""

    def __init__(
        self,
        name: str,
        logger: Logger,
        port: str,
        baudrate: int = 115200,
    ):
        super().__init__(name)
        self._port = port
        self._baudrate = baudrate
        self._log = logger
        self._lidar: rplidar_type.RPLidar | None = None
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()
        self._scan_thread: Thread | None = None
        self._running: bool = False
        self._stop_r, self._stop_w = os.pipe()
        self._measures: Queue[Lidar2DMeasure] = Queue(maxsize = _MEASURES_QUEUE_LENGTH)

    def init(self) -> Task[()]:
        global _rplidar
        if _rplidar is None:
            import adafruit_rplidar
            _rplidar = adafruit_rplidar

        self._lidar = _rplidar.RPLidar(motor_pin = None, port = self._port, baudrate = self._baudrate)
        self._log.info(f"RPLidar '{self.name}' initialized on {self._port}")

        return ImmediateResultTask()

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
        self._log.info(f"RPLidar '{self.name}' closed")

    def start(self) -> Task[()]:
        if self._running:
            return ImmediateResultTask()
        self._running = True
        self._scan_thread = Thread(target=self._scan_loop)
        self._scan_thread.start()
        return ImmediateResultTask()

    def stop(self) -> Task[None]:
        if not self._running:
            return ImmediateResultTask()
        self._running = False
        if self._stop_w >= 0:
            os.write(self._stop_w, b"\x00")
        if self._scan_thread is not None:
            self._scan_thread.join(timeout=1.0)
            if self._scan_thread.is_alive():
                self._log.error(f"Failed to stop RPLidar '{self.name}' thread")
            self._scan_thread = None
        return ImmediateResultTask()

    def iter(self, duration: float | None = None) -> Iterator[Lidar2DMeasure]:
        start = time.monotonic()
        while True:
            if duration is not None and time.monotonic() - start >= duration:
                return
            try:
                yield self._measures.get(block = True, timeout = 0.1) # TODO: Do not use a timeout
            except Empty:
                pass

    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        return self._scan_event

    def _scan_loop(self) -> None:
        """Background thread: read scans and fire events."""

        # Old RPLidar implementation
        """
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
                self._log.error(f"RPLidar scan error: {e}")
        finally:
            self._running = False
        """

        # New adafruit RPLidar implementation
        batch = []
        while self._running:
            try:
                for new_scan, quality, angle, distance in self._lidar.iter_measurements(
                    scan_type = _rplidar.SCAN_TYPE_NORMAL,
                    max_buf_meas = 2048
                ):
                    if not self._running:
                        break

                    if new_scan and len(batch) > 0:
                        self._scan_event.trigger(batch)
                        batch = []

                    angle = -angle # Lidar rotate in non trigonometric order
                    measure = Lidar2DMeasure(distance, math.radians(angle), time.monotonic(), quality / 255.0)
                    try:
                        self._measures.put(measure, block = False)
                    except Full:
                        pass
                    batch.append(measure)

            except _rplidar.RPLidarException as e:
                if self._running:
                    # self._log.error(f"RPLidar scan error: {e}")
                    self._log.error("RPLidar scan error")
                    while True:
                        try:
                            self._lidar.stop()
                            time.sleep(0.1)
                            self._lidar.start()
                            break
                        except _rplidar.RPLidarException:
                            time.sleep(0.2)
                    time.sleep(0.2)
                    self._log.error("RPLidar error recovered")


class RPLidarDefinition(DriverDefinition):
    """Factory for RPLidarDriver from config args."""

    def __init__(self, logger: Logger):
        super().__init__(Lidar2D.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("port", ArgTypes.String())
        defn.add_optional("baudrate", ArgTypes.U32(), 115200)
        return defn

    def create(self, args: DriverInitArgs) -> RPLidarDriver:
        return RPLidarDriver(
            name=args.get_name(),
            logger=self._logger,
            port=args.get("port"),
            baudrate=args.get("baudrate"),
        )


class RPLidarVirtual(Lidar2DVirtual):
    """Drop-in virtual twin for RPLidarDriver.

    Constructor mirrors RPLidarDriver exactly so a config swap is a one-line
    change. ``port`` and ``baudrate`` are kept for signature parity and are
    orthogonal to the simulation.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        port: str,
        baudrate: int = 115200,
    ):
        super().__init__(name, logger)
        self._port = port
        self._baudrate = baudrate


class RPLidarVirtualDefinition(DriverDefinition):
    """Factory for RPLidarVirtual — args mirror RPLidarDefinition."""

    def __init__(self, logger: Logger):
        super().__init__(Lidar2D.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("port", ArgTypes.String())
        defn.add_optional("baudrate", ArgTypes.U32(), 115200)
        return defn

    def create(self, args: DriverInitArgs) -> RPLidarVirtual:
        return RPLidarVirtual(
            name=args.get_name(),
            logger=self._logger,
            port=args.get("port"),
            baudrate=args.get("baudrate"),
        )
