"""Abstract interface for 2D scanning lidars."""

from abc import abstractmethod
from typing import TYPE_CHECKING, Generator

from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    from evo_lib.event import Event
    from evo_lib.task import Task


class Lidar2DMeasure:
    __slots__ = ("angle", "distance", "timestamp", "quality")

    def __init__(self, angle: float, distance: float, timestamp: float, quality: float):
        self.distance = distance # Shall be given in mm
        self.angle = angle # Shall be given in rads
        self.timestamp = timestamp
        self.quality = quality # Shall be between 0 and 255


class Lidar2D(Placable):
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
