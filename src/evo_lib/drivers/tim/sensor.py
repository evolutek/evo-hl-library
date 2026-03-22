"""SICK TIM driver, real implementation via COLA-B over TCP."""

from __future__ import annotations

import logging
import socket
import time
from math import radians
from socket import AF_INET, SOCK_STREAM
from threading import Event as ThreadingEvent, Lock, Thread
from typing import Generator

from evo_lib.event import Event
from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.task import DelayedTask, ImmediateResultTask, Task

log = logging.getLogger(__name__)

# COLA-B framing bytes
_STX = b"\x02"
_ETX = b"\x03"

# Single scan request (COLA-A text command inside COLA-B frame)
_SCAN_REQUEST = _STX + b"sRN LMDscandata" + _ETX + b"\x00"


def _parse_num(s: str) -> int:
    """Parse a COLA response token: hex if no sign, decimal if signed."""
    if "+" in s or "-" in s:
        return int(s)
    return int(s, 16)


class SickTIM(Lidar2D):
    """SICK TIM 2D laser scanner connected via COLA-B over TCP.

    The sensor is polled in a background thread. Each complete scan
    triggers the on_scan event with a list of Lidar2DMeasure.
    """

    def __init__(self, name: str, host: str, port: int = 2112):
        super().__init__(name)
        self._host = host
        self._port = port
        self._socket: socket.socket | None = None
        self._scanning = False
        self._thread: Thread | None = None
        self._lock = Lock()
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()

    # -- Component lifecycle --

    def init(self) -> None:
        """Connect to the SICK TIM sensor via TCP."""
        self._socket = socket.socket(AF_INET, SOCK_STREAM)
        self._socket.settimeout(5.0)
        log.info("TIM connecting to %s:%d", self._host, self._port)
        self._socket.connect((self._host, self._port))
        log.info("TIM connected")

    def close(self) -> None:
        """Stop scanning and disconnect."""
        self._scanning = False
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None:
            thread.join(timeout=3.0)
        with self._lock:
            if self._socket is not None:
                self._socket.close()
                self._socket = None
                log.info("TIM closed")

    # -- Lidar2D interface --

    def start(self) -> Task[None]:
        """Start continuous scanning in a background thread."""
        with self._lock:
            if self._scanning:
                return ImmediateResultTask(None)
            self._scanning = True
            ready = ThreadingEvent()
            self._thread = Thread(
                target=self._scan_loop, args=(ready,), daemon=True,
            )
            self._thread.start()
        task: DelayedTask[None] = DelayedTask()
        if ready.wait(timeout=5.0):
            task.complete(None)
        else:
            task.error(TimeoutError("TIM scan thread did not become ready within 5s"))
        return task

    def stop(self) -> Task[None]:
        """Stop the background scanning thread."""
        self._scanning = False
        with self._lock:
            thread = self._thread
            self._thread = None
        if thread is not None:
            thread.join(timeout=3.0)
        return ImmediateResultTask(None)

    def iter(self, duration: float | None = None) -> Generator[Lidar2DMeasure, None, None]:
        """Yield individual measures by polling the sensor.

        If duration is None, yields forever (until close or StopIteration).
        """
        deadline = None if duration is None else time.monotonic() + duration
        while True:
            if deadline is not None and time.monotonic() >= deadline:
                return
            measures = self._poll_one_scan()
            if measures is None:
                continue
            yield from measures

    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        """Return the event fired on each complete scan."""
        return self._scan_event

    # -- Internal --

    def _recv_response(self) -> list[str] | None:
        """Read one COLA-B response frame from the socket."""
        data = b""
        while True:
            try:
                with self._lock:
                    sock = self._socket
                if sock is None:
                    log.warning("TIM socket closed during recv")
                    return None
                chunk = sock.recv(4096)
            except (socket.timeout, socket.error, OSError) as e:
                log.error("TIM recv failed: %s", e)
                return None
            if not chunk:
                log.warning("TIM socket closed by remote")
                return None
            data += chunk
            # Check accumulated buffer for ETX, not just the current chunk
            if _ETX[0:1] in data:
                break

        # Strip STX/ETX framing
        text = data.decode("ascii", errors="replace")
        stx = text.find("\x02")
        etx = text.find("\x03")
        if stx < 0 or etx < 0 or etx <= stx:
            log.warning("TIM bad response frame")
            return None

        return text[stx + 1 : etx].split(" ")

    def _poll_one_scan(self) -> list[Lidar2DMeasure] | None:
        """Send a single scan request and parse the response."""
        try:
            with self._lock:
                sock = self._socket
            if sock is None:
                return None
            sock.sendall(_SCAN_REQUEST)
        except (socket.timeout, socket.error, OSError) as e:
            log.error("TIM send failed: %s", e)
            return None

        tokens = self._recv_response()
        if tokens is None:
            return None

        return self._parse_scan(tokens)

    @staticmethod
    def _parse_scan(tokens: list[str]) -> list[Lidar2DMeasure] | None:
        """Parse COLA-B scan data tokens into a list of measures.

        Token layout (SICK TIM sRN LMDscandata):
          [24] = angular step in 1/10000 deg
          [25] = number of distance samples
          [26..26+N-1] = distance values (hex, in mm)
        """
        # Bounds check: need at least tokens[0..25] for header
        if len(tokens) < 26:
            log.warning("TIM scan too short: %d tokens", len(tokens))
            return None

        try:
            step_raw = _parse_num(tokens[24])  # 1/10000 deg
            count = _parse_num(tokens[25])
        except (IndexError, ValueError) as e:
            log.warning("TIM parse error: %s", e)
            return None

        if count == 0:
            return None

        # Verify enough tokens for all distance samples
        if len(tokens) < 26 + count:
            log.warning(
                "TIM scan truncated: expected %d samples, got %d tokens",
                count,
                len(tokens) - 26,
            )
            return None

        step_rad = radians(step_raw / 10000.0)
        now = time.monotonic()
        measures: list[Lidar2DMeasure] = []

        for i in range(count):
            try:
                dist_mm = _parse_num(tokens[26 + i])
            except (IndexError, ValueError):
                break
            angle_rad = i * step_rad
            # Quality not provided by SICK TIM protocol, default to max
            measures.append(
                Lidar2DMeasure(
                    angle=angle_rad,
                    distance=float(dist_mm),
                    timestamp=now,
                    quality=255.0,
                )
            )

        return measures

    def _scan_loop(self, ready: ThreadingEvent) -> None:
        """Background thread: poll scans and trigger the event."""
        ready.set()
        try:
            while self._scanning:
                measures = self._poll_one_scan()
                if measures is not None:
                    self._scan_event.trigger(measures)
                else:
                    time.sleep(0.05)
        except (socket.timeout, socket.error, OSError) as exc:
            log.error("TIM scan loop crashed: %s", exc)
        finally:
            self._scanning = False
