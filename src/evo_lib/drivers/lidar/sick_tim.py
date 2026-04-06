"""SICK TIM driver: 2D scanning lidar via TCP/COLA-B protocol.

The SICK TIM is a 2D lidar connected over Ethernet. Communication uses
the SOPAS (SICK Open Platform for Applications and Sensors) protocol
with COLA-B framing over TCP.
"""

import logging
import math
import socket
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

# COLA-B framing
_STX = b"\x02"
_ETX = b"\x03"
_REQUEST = b"\x02sRN LMDscandata\x03"


class SickTIMDriver(Lidar2D):
    """SICK TIM lidar via TCP/COLA-B protocol."""

    def __init__(
        self,
        name: str,
        host: str,
        port: int = 2112,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._host = host
        self._port = port
        self._log = logger or logging.getLogger(__name__)
        self._socket: socket.socket | None = None
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()
        self._poll_thread: threading.Thread | None = None
        self._running = False
        self._measures: deque[Lidar2DMeasure] = deque(maxlen=10000)
        self._data_ready = threading.Event()

    def init(self) -> None:
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5.0)
        self._socket.connect((self._host, self._port))
        self._log.info("SICK TIM '%s' connected to %s:%d", self.name, self._host, self._port)

    def close(self) -> None:
        self.stop().wait()
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._log.info("SICK TIM '%s' closed", self.name)

    def start(self) -> Task[None]:
        if self._running:
            return ImmediateResultTask(None)
        self._running = True
        self._poll_thread = threading.Thread(
            target=self._poll_loop, daemon=True, name=f"sicktim-{self.name}"
        )
        self._poll_thread.start()
        return ImmediateResultTask(None)

    def stop(self) -> Task[None]:
        if not self._running:
            return ImmediateResultTask(None)
        self._running = False
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=3.0)
            self._poll_thread = None
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

    def _poll_loop(self) -> None:
        """Background thread: request scans and parse responses."""
        try:
            while self._running:
                self._socket.sendall(_REQUEST)
                response = self._receive_response()
                if response is None:
                    continue
                batch = self._parse_response(response)
                if batch:
                    for m in batch:
                        self._measures.append(m)
                    self._data_ready.set()
                    self._scan_event.trigger(batch)
        except Exception as e:
            if self._running:
                self._log.error("SICK TIM poll error: %s", e)
        finally:
            self._running = False

    def _receive_response(self) -> str | None:
        """Read a COLA-B response (STX ... ETX) from the socket."""
        data = b""
        try:
            while _ETX not in data:
                chunk = self._socket.recv(4096)
                if not chunk:
                    return None
                data += chunk
        except socket.timeout:
            return None
        # Strip STX/ETX and decode
        start = data.find(_STX)
        end = data.find(_ETX, start)
        if start < 0 or end < 0:
            return None
        return data[start + 1 : end].decode("ascii", errors="replace")

    def _parse_response(self, response: str) -> list[Lidar2DMeasure]:
        """Parse a COLA-B scan response into measures."""
        parts = response.split()
        if len(parts) < 27:
            return []
        try:
            # Angular step in 1/10000 degrees
            angular_step = int(parts[24], 16) / 10000.0
            count = int(parts[25], 16)
            if len(parts) < 26 + count:
                return []
            # Starting angle in 1/10000 degrees
            start_angle = int(parts[23], 16) / 10000.0
            ts = time.monotonic()
            batch = []
            for i in range(count):
                distance_mm = int(parts[26 + i], 16)
                angle_deg = start_angle + i * angular_step
                batch.append(
                    Lidar2DMeasure(
                        angle=math.radians(angle_deg),
                        distance=float(distance_mm),
                        timestamp=ts,
                        quality=255.0,
                    )
                )
            return batch
        except ValueError, IndexError:
            return []


class SickTIMDefinition(DriverDefinition):
    """Factory for SickTIMDriver from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_required("host", ArgTypes.String())
        defn.add_optional("port", ArgTypes.U16(), 2112)
        return defn

    def create(self, args: DriverInitArgs) -> SickTIMDriver:
        name = args.get("name")
        return SickTIMDriver(
            name=name,
            host=args.get("host"),
            port=args.get("port"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
