from abc import abstractmethod
from dataclasses import dataclass

from evo_lib.event import Event
from evo_lib.peripheral import Peripheral
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.vect import Vect2D


@dataclass(slots=True)
class Obstacle:
    position: Vect2D


class ObstacleProvider(Peripheral):
    @abstractmethod
    def on_obstacles(self) -> Event[list[Obstacle]]:
        """Returns an event that is triggered when the obstacles list change."""


class ObstacleProviderMerger(ObstacleProvider):
    """
    Merges multiple obstacles providers into a single provider.
    """

    def __init__(self, providers: list[ObstacleProvider]):
        self._providers = providers
        self._obstacles: dict[ObstacleProvider, list[Obstacle]] = {}
        self._event = Event[list[Obstacle]]()

    def init(self) -> Task[()]:
        for provider in self._providers:
            provider.on_obstacles().register(
                lambda obstacles: self._on_obstacles(provider, obstacles)
            )
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    def _on_obstacles(self, provider: ObstacleProvider, obstacles: list[Obstacle]) -> None:
        self._obstacles[provider] = obstacles
        # Merge all obstacles into a single list and trigger the event
        all_obstacles = [
            obstacle for obstacles_list in self._obstacles.values() for obstacle in obstacles_list
        ]
        self._event.trigger(all_obstacles)

    def on_obstacles(self) -> Event[list[Obstacle]]:
        return self._event
