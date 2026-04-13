"""Abstract interface for 2D scanning lidars."""

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterator

from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    from evo_lib.event import Event
    from evo_lib.task import Task


@dataclass(slots=True)
class Lidar2DMeasure:
    distance: float # Shall be given in mm
    angle: float # Shall be given in radians
    timestamp: float # In seconds
    quality: float # Between 0 and 1


class Lidar2D(Placable):
    """A 2D rotating lidar (e.g. RPLidar A2, SICK TIM).

    Produces periodic scan data as a list of (angle_deg, distance_mm) points.
    """

    commands = DriverCommands()

    @abstractmethod
    @commands.register(args = [], result = [])
    def start(self) -> Task[()]:
        """Start continuous scanning."""

    @abstractmethod
    @commands.register(args = [], result = [])
    def stop(self) -> Task[()]:
        """Stop scanning."""

    @abstractmethod
    def iter(self, duration: float | None = None) -> Iterator[Lidar2DMeasure]:
        """Return a Python generator to iterate efficiently on lidar measurement."""

    @abstractmethod
    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        """Register a callback to invoked on each complete scan batch.

        The callback receives a list of ``Lidar2DMeasure``.
        """
