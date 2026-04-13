"""SICK TIM driver: 2D scanning lidar via TCP/COLA-B protocol.

The SICK TIM is a 2D lidar connected over Ethernet. Communication uses
the SOPAS (SICK Open Platform for Applications and Sensors) protocol
with COLA-B framing over TCP.
"""

import math
import socket
import time
from queue import Empty, Full, Queue
from threading import Thread
from typing import Iterator

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.thread_pool import ThreadPoolExecutor

# COLA-B framing
_STX = b"\x02"
_ETX = b"\x03"
_REQUEST = b"\x02sRN LMDscandata\x03"


class SickTIMDriver(Lidar2D):
    """SICK TIM lidar via TCP/COLA-B protocol."""

    def __init__(
        self,
        name: str,
        logger: Logger,
        threadpool: ThreadPoolExecutor,
        host: str,
        port: int = 2112,
    ):
        super().__init__(name)
        self._log = logger
        self._threadpool = threadpool
        self._host = host
        self._port = port
        self._socket: socket.socket | None = None
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()
        self._poll_thread: Thread | None = None
        self._running = False
        self._measures: Queue[Lidar2DMeasure] = Queue(maxsize=10000)

    def _init(self) -> None:
        # TODO: Do this init in a worker thread because socket connection can take some time
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(5.0)
        self._socket.connect((self._host, self._port))
        self._log.info(f"SICK TIM '{self.name}' connected to {self._host}:{self._port}")

    def init(self) -> Task[()]:
        return self._threadpool.exec(self._init)

    def close(self) -> None:
        self.stop().wait()
        if self._socket is not None:
            self._socket.close()
            self._socket = None
        self._log.info(f"SICK TIM '{self.name}' closed")

    def start(self) -> Task[()]:
        if self._running:
            return ImmediateResultTask()
        self._running = True
        self._poll_thread = Thread(target=self._poll_loop)
        self._poll_thread.start()
        return ImmediateResultTask()

    def stop(self) -> Task[()]:
        if not self._running:
            return ImmediateResultTask()
        self._running = False
        if self._poll_thread is not None:
            self._poll_thread.join(timeout=1.0)
            if self._poll_thread.is_alive():
                self._log.error(f"Failed to stop Sick TIM lidar '{self.name}' thread")
            self._poll_thread = None
        return ImmediateResultTask()

    def iter(self, duration: float | None = None) -> Iterator[Lidar2DMeasure]:
        start = time.monotonic()
        while True:
            if duration is not None and time.monotonic() - start >= duration:
                return
            if self._measures:
                try:
                    yield self._measures.get(block=True, timeout=0.1)
                except Empty:
                    pass

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
                    try:
                        for m in batch:
                            self._measures.put_nowait(m)
                    except Full:
                        pass
                    self._scan_event.trigger(batch)
        except Exception as e:
            if self._running:
                self._log.error(f"SICK TIM poll error: {e}")
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
                        quality=1.0,
                    )
                )
            return batch
        except ValueError, IndexError:
            return []


class SickTIMDefinition(DriverDefinition):
    """Factory for SickTIMDriver from config args."""

    def __init__(self, logger: Logger, threadpool: ThreadPoolExecutor):
        super().__init__(Lidar2D.commands)
        self._logger = logger
        self._threadpool = threadpool

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("host", ArgTypes.String())
        defn.add_optional("port", ArgTypes.U16(), 2112)
        return defn

    def create(self, args: DriverInitArgs) -> SickTIMDriver:
        return SickTIMDriver(
            name=args.get_name(),
            logger=self._logger,
            threadpool=self._threadpool,
            host=args.get("host"),
            port=args.get("port"),
        )
