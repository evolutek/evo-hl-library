"""SICK TIM driver — real implementation via TCP/IP socket."""

from __future__ import annotations

import logging
from math import cos, radians, sin, sqrt
from socket import AF_INET, SOCK_STREAM, socket
from threading import Lock, Thread
from time import sleep
from typing import Callable

from evo_hl.tim.base import Tim

log = logging.getLogger(__name__)


def _parse_num(s: str) -> int:
    """Parse a number — hex if no sign, decimal if signed."""
    if "+" in s or "-" in s:
        return int(s)
    return int(s, 16)


class TimSensor(Tim):
    """SICK TIM laser scanner connected via TCP/IP."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._socket: socket | None = None
        self._lock = Lock()
        self._scanning = False
        self._robots: list[tuple[float, float]] = []

    def init(self) -> None:
        self._socket = socket(AF_INET, SOCK_STREAM)
        self._connect()

    def _connect(self) -> None:
        while True:
            try:
                log.info("TIM connecting to %s:%d", self.ip, self.port)
                self._socket.connect((self.ip, self.port))
                log.info("TIM connected")
                return
            except Exception as e:
                log.warning("TIM connection failed: %s, retrying...", e)
                sleep(1)

    def _send_request(self) -> list[str] | None:
        """Send scan request and parse response."""
        try:
            self._socket.sendall(b"\x02sRN LMDscandata\x03\0")
        except Exception as e:
            log.error("TIM send failed: %s", e)
            return None

        data = ""
        while True:
            try:
                part = self._socket.recv(1024).decode()
            except Exception as e:
                log.error("TIM recv failed: %s", e)
                return None
            data += part
            if "\x03" in part:
                break

        if not data.startswith("\x02") or not data.endswith("\x03"):
            log.warning("TIM bad response frame")
            return None

        return data[1:-1].split(" ")

    def _convert_to_cartesian(self, distances: list[int], step_deg: float) -> list[tuple[float, float]]:
        """Convert polar scan to cartesian points in table coordinates."""
        points = []
        n = len(distances)
        for i, dist in enumerate(distances):
            angle = radians((n - i) * step_deg - self.angle)
            x = dist * sin(angle) + self.pos_x
            y = dist * cos(angle) + self.pos_y
            if 0 <= x <= 2000 and 0 <= y <= 3000:
                points.append((x, y))
        return points

    def _split_shapes(self, points: list[tuple[float, float]]) -> list[list[tuple[float, float]]]:
        """Cluster points into shapes."""
        shapes = []
        shape: list[tuple[float, float]] = []
        for p in points:
            if not shape:
                shape.append(p)
                continue
            dx = p[0] - shape[-1][0]
            dy = p[1] - shape[-1][1]
            if sqrt(dx * dx + dy * dy) < self.max_distance:
                shape.append(p)
            else:
                if len(shape) >= self.min_shape_size:
                    shapes.append(shape)
                shape = [p]
        if len(shape) >= self.min_shape_size:
            shapes.append(shape)
        return shapes

    def _compute_center(self, shape: list[tuple[float, float]]) -> tuple[float, float]:
        """Estimate robot center from shape points."""
        mx = sum(p[0] for p in shape) / len(shape)
        my = sum(p[1] for p in shape) / len(shape)
        dx = mx - self.pos_x
        dy = my - self.pos_y
        dist = sqrt(dx * dx + dy * dy)
        if dist == 0:
            return (mx, my)
        offset = self.beacon_radius / dist
        return (mx + dx * offset, my + dy * offset)

    def _scan_loop(self, callback: Callable | None) -> None:
        while self._scanning:
            sleep(0.1)
            data = self._send_request()
            if data is None:
                continue

            step = _parse_num(data[24]) / 10000.0
            length = _parse_num(data[25])
            if length == 0:
                continue

            distances = [_parse_num(d) for d in data[26 : 26 + length]]
            points = self._convert_to_cartesian(distances, step)
            shapes = self._split_shapes(points)
            robots = [self._compute_center(s) for s in shapes]

            with self._lock:
                self._robots = robots

            if callback is not None:
                callback(points, shapes, robots)

    def start_scanning(self, callback: Callable | None = None) -> None:
        self._scanning = True
        Thread(target=self._scan_loop, args=(callback,), daemon=True).start()

    def stop_scanning(self) -> None:
        self._scanning = False

    def get_robots(self) -> list[tuple[float, float]]:
        with self._lock:
            return list(self._robots)

    def close(self) -> None:
        self.stop_scanning()
        if self._socket is not None:
            self._socket.close()
            self._socket = None
            log.info("TIM closed")
