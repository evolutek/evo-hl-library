"""Abstract base class for SICK TIM laser scanner."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

class Tim(ABC):
    """SICK TIM 2D laser scanner connected via TCP/IP.

    Continuously scans and detects robot-shaped obstacles.
    """

    def __init__(
        self,
        ip: str,
        port: int,
        pos_x: float,
        pos_y: float,
        angle: float,
        min_shape_size: int = 3,
        max_distance: float = 50.0,
        beacon_radius: float = 100.0,
    ):
        self.ip = ip
        self.port = port
        self.pos_x = pos_x
        self.pos_y = pos_y
        self.angle = angle
        self.min_shape_size = min_shape_size
        self.max_distance = max_distance
        self.beacon_radius = beacon_radius

    @abstractmethod
    def init(self) -> None:
        """Connect to the TIM sensor."""

    @abstractmethod
    def start_scanning(self, callback: Callable | None = None) -> None:
        """Start background scanning thread."""

    @abstractmethod
    def stop_scanning(self) -> None:
        """Stop the scanning thread."""

    @abstractmethod
    def get_robots(self) -> list[tuple[float, float]]:
        """Get estimated positions of detected robots."""

    @abstractmethod
    def close(self) -> None:
        """Disconnect and release resources."""
