"""Abstract interface for robot movement (differential and holonomic pilots)."""

from abc import abstractmethod
from enum import Enum

from evo_lib.component import Component

from dataclasses import dataclass

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from evo_lib.task import Task


class PilotMoveStatus(Enum):
    ERROR = 0
    MOVING = 1
    REACHED = 2
    BLOCKED = 3
    CANCELLED = 4


@dataclass(slots=True)
class DifferentialPilotWaypoint:
    """
    Represent a waypoint on a path for a differential robot.

    Attributes:
        x           X coordinate of this waypoint.
        y           Y coordinate of this waypoint.
        heading     Orientation in radians the robot must have when it
                    reached/leave this waypoint.
        velocity    Velocity of the robot at this waypoint (positive).
    """
    x: float
    y: float
    heading: float
    velocity: float


@dataclass(slots=True)
class HolonomicPilotWaypoint(DifferentialPilotWaypoint):
    """
    Represent a waypoint on a path for a holonomic robot.

    Attributes:
        tangent     Angle in radians of the tangent of this waypoint (ie. the
                    direction of the velocity vector when the robot reache this
                    waypoint)
    """
    tangent: float


class Pilot(Component):
    @abstractmethod
    def stop(self) -> Task[None]:
        """Immediately stop the current movement."""
        pass

    @abstractmethod
    def free(self) -> Task[None]:
        """Immediately stop motor and go into freewheel."""
        pass


class DifferentialPilot(Pilot):
    """
    Interface to control the movement of a differential robot.
    """

    @abstractmethod
    def go_to(self, x: float, y: float) -> Task[PilotMoveStatus]:
        """Move to the given position. The returned Task can be cancelled."""

    @abstractmethod
    def go_to_then_head_to(self, x: float, y: float, heading: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def go_to_then_rotate(self, x: float, y: float, angle: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def go_to_then_look_at(self, x: float, y: float, look_x: float, look_y: float) -> Task[PilotMoveStatus]:
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
    def follow_path(self, waypoints: list[DifferentialPilotWaypoint]) -> Task[PilotMoveStatus]:
        pass


class HolonomicPilot(DifferentialPilot):
    """
    Interface to control the movement of a holonomic robot.
    It's extends the DifferentialPilot interface, so it has all the features of
    a differential robot plus some more.
    """

    @abstractmethod
    def go_to_while_head_to(self, x: float, y: float, heading: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def go_to_while_rotate(self, x: float, y: float, angle: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def go_to_while_look_at(self, x: float, y: float, look_x: float, look_y: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def follow_holonomic_path(self, waypoints: list[HolonomicPilotWaypoint]) -> Task[PilotMoveStatus]:
        pass
