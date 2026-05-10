from abc import abstractmethod
from dataclasses import dataclass

from evo_lib.event import Event
from evo_lib.peripheral import Peripheral
from evo_lib.types.vect import Vect2D


@dataclass(slots=True)
class Obstacle:
    position: Vect2D


class ObstaclesProvider(Peripheral):
    @abstractmethod
    def on_obstacles(self) -> Event[list[Obstacle]]:
        """Returns an event that is triggered when the obstacles list change."""
