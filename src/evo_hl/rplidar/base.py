"""Abstract base class for RPLidar 2D laser scanner."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

class RPLidar(ABC):
    """Continuous 2D laser scanning with shape detection.

    Scans run in a background thread. Each scan produces a point cloud,
    which is split into shapes (clusters of nearby points). A callback
    is invoked with the detected shapes after each scan.
    """

    def __init__(
        self,
        device: str = "/dev/ttyUSB0",
        max_distance: float = 1500.0,
        min_shape_size: int = 3,
        shape_split_distance: float = 50.0,
    ):
        self.device = device
        self.max_distance = max_distance
        self.min_shape_size = min_shape_size
        self.shape_split_distance = shape_split_distance

    @abstractmethod
    def init(self) -> None:
        """Initialize the lidar hardware."""

    @abstractmethod
    def start_scanning(self, callback: Callable | None = None) -> None:
        """Start background scanning thread.

        callback(cloud, shapes) is called after each scan with:
        - cloud: list of (x, y) tuples — all valid points
        - shapes: list of list of (x, y) — clustered point groups
        """

    @abstractmethod
    def stop_scanning(self) -> None:
        """Stop the scanning thread."""

    @abstractmethod
    def get_cloud(self) -> list[tuple[float, float]]:
        """Get the latest point cloud."""

    @abstractmethod
    def get_shapes(self) -> list[list[tuple[float, float]]]:
        """Get the latest detected shapes."""

    @abstractmethod
    def close(self) -> None:
        """Stop scanning and release hardware."""
