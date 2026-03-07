"""RPLidar driver — fake implementation for testing without hardware."""

from __future__ import annotations

import logging
from typing import Callable

from evo_hl.rplidar.base import RPLidar

log = logging.getLogger(__name__)


class RPLidarFake(RPLidar):
    """In-memory RPLidar for tests and simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.cloud: list[tuple[float, float]] = []
        self.shapes: list[list[tuple[float, float]]] = []
        self.scanning = False

    def init(self) -> None:
        log.info("RPLidar fake initialized on %s", self.device)

    def inject_cloud(self, cloud: list[tuple[float, float]]) -> None:
        """Inject a point cloud for testing."""
        self.cloud = cloud

    def inject_shapes(self, shapes: list[list[tuple[float, float]]]) -> None:
        """Inject detected shapes for testing."""
        self.shapes = shapes

    def start_scanning(self, callback: Callable | None = None) -> None:
        self.scanning = True
        log.info("RPLidar fake scanning started")

    def stop_scanning(self) -> None:
        self.scanning = False

    def get_cloud(self) -> list[tuple[float, float]]:
        return list(self.cloud)

    def get_shapes(self) -> list[list[tuple[float, float]]]:
        return [list(s) for s in self.shapes]

    def close(self) -> None:
        self.scanning = False
        self.cloud.clear()
        self.shapes.clear()
        log.info("RPLidar fake closed")
