"""RPLidar driver — real implementation via rplidar-roboticia."""

from __future__ import annotations

import logging
from math import cos, pi, radians, sin
from threading import Event, Lock, Thread
from typing import Callable

from evo_hl.rplidar.base import RPLidar

log = logging.getLogger(__name__)


class RPLidarSerial(RPLidar):
    """RPLidar A2 scanner via USB UART (rplidar-roboticia)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._lidar = None
        self._lock = Lock()
        self._stop_event = Event()
        self._cloud: list[tuple[float, float]] = []
        self._shapes: list[list[tuple[float, float]]] = []

    def init(self) -> None:
        from rplidar import RPLidar as _HwRPLidar

        self._lidar = _HwRPLidar(self.device)
        info = self._lidar.get_info()
        log.info("RPLidar initialized: %s", info)

    def _convert_scan(self, scan) -> list[tuple[float, float]]:
        """Convert polar scan data to cartesian (x, y) points."""
        cloud = []
        for _quality, angle, distance in scan:
            if distance > self.max_distance or distance == 0:
                continue
            angle_rad = radians(angle) + pi / 2
            x = distance * sin(angle_rad)
            y = distance * cos(angle_rad)
            cloud.append((x, y))
        return cloud

    def _split_shapes(self, cloud: list[tuple[float, float]]) -> list[list[tuple[float, float]]]:
        """Split point cloud into clusters based on inter-point distance."""
        shapes = []
        shape: list[tuple[float, float]] = []
        for point in cloud:
            if not shape:
                shape.append(point)
                continue
            dx = point[0] - shape[-1][0]
            dy = point[1] - shape[-1][1]
            dist = (dx * dx + dy * dy) ** 0.5
            if dist < self.shape_split_distance:
                shape.append(point)
            else:
                if len(shape) >= self.min_shape_size:
                    shapes.append(shape)
                shape = [point]
        if len(shape) >= self.min_shape_size:
            shapes.append(shape)
        return shapes

    def _scan_loop(self, callback: Callable | None) -> None:
        """Background scanning loop."""
        log.info("RPLidar scanning started")
        try:
            for scan in self._lidar.iter_scans():
                if self._stop_event.is_set():
                    break
                cloud = self._convert_scan(scan)
                shapes = self._split_shapes(cloud)
                with self._lock:
                    self._cloud = cloud
                    self._shapes = shapes
                if callback is not None:
                    callback(cloud, shapes)
        except Exception as e:
            log.error("RPLidar scan error: %s", e)
        finally:
            log.info("RPLidar scanning stopped")

    def start_scanning(self, callback: Callable | None = None) -> None:
        self._stop_event.clear()
        Thread(target=self._scan_loop, args=(callback,), daemon=True).start()

    def stop_scanning(self) -> None:
        self._stop_event.set()

    def get_cloud(self) -> list[tuple[float, float]]:
        with self._lock:
            return list(self._cloud)

    def get_shapes(self) -> list[list[tuple[float, float]]]:
        with self._lock:
            return [list(s) for s in self._shapes]

    def close(self) -> None:
        self.stop_scanning()
        if self._lidar is not None:
            self._lidar.stop()
            self._lidar.stop_motor()
            self._lidar.disconnect()
            self._lidar = None
            log.info("RPLidar closed")
