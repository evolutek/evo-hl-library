"""Abstract interface for motor controllers (steppers, DC motors, etc.)."""

from abc import abstractmethod
from enum import Enum

from evo_lib.component import Component

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from evo_lib.task import Task


class PilotMoveStatus(Enum):
    ERROR = 0
    MOVING = 1
    REACHED = 2
    BLOCKED = 3
    CANCELLED = 4


class DifferentialPilot(Component):
    """Interface to control the movement of a differential robot.
    """

    @abstractmethod
    def go_to(self, x: float, y: float) -> Task[PilotMoveStatus]:
        """Move to the given position. The returned Task can be cancelled."""

    @abstractmethod
    def go_to_and_head_to(self, x: float, y: float, heading: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def go_to_and_rotate(self, x: float, y: float, angle: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def go_to_and_look_at(self, x: float, y: float, look_x: float, look_y: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def forward(self, distance: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def head_to(self, heading: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def look_at(self, x: float, y: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def rotate(self, angle: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def stop(self) -> Task[None]:
        """Immediately stop the movement."""
        pass

    @abstractmethod
    def free(self) -> Task[None]:
        """Immediately stop motor and go into freewheel."""
        pass
