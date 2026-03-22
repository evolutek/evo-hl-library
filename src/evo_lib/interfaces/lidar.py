"""Abstract interface for 2D scanning lidars."""

from abc import abstractmethod

from evo_lib.component import Component

from typing import TYPE_CHECKING, Generator
if TYPE_CHECKING:
    from evo_lib.task import Task
    from evo_lib.event import Event


class Lidar2DMeasure:
    __slots__ = ("angle", "distance", "timestamp", "quality")

    angle: float
    """Angle in radians."""
    distance: float
    """Distance in mm."""
    timestamp: float
    """Monotonic timestamp (seconds)."""
    quality: float
    """Signal quality, 0-255."""

    def __init__(self, angle: float, distance: float, timestamp: float, quality: float):
        self.distance = distance
        self.angle = angle
        self.timestamp = timestamp
        self.quality = quality


class Lidar2D(Component):
    """A 2D rotating lidar (e.g. RPLidar A2, SICK TIM).

    Produces periodic scan data as a list of (angle_deg, distance_mm) points.
    """

    @abstractmethod
    def start(self) -> Task[None]:
        """Start continuous scanning."""

    @abstractmethod
    def stop(self) -> Task[None]:
        """Stop scanning."""

    @abstractmethod
    def iter(self, duration: float | None = None) -> Generator[Lidar2DMeasure, None, None]:
        """Return a Python generator to iterate efficiently on lidar measurement."""

    @abstractmethod
    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        """Register a callback to invoked on each complete scan batch.

        The callback receives a list of ``Lidar2DMeasure``.
        """
