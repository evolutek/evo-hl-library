"""Abstract interface for robot movement (differential and holonomic pilots)."""

from abc import abstractmethod
from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.event import Event
from evo_lib.peripheral import Placable
from evo_lib.types.pose import Pose2D
from evo_lib.types.vect import Vect2D

if TYPE_CHECKING:
    from evo_lib.task import Task


class PilotMoveStatus(StrEnum):
    ERROR = "error"
    MOVING = "moving"
    REACHED = "reached"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


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


class Pilot(Placable):
    commands = DriverCommands()

    @abstractmethod
    @commands.register(args = [], result = [])
    def stop(self) -> Task[()]:
        """Immediately stop the current movement."""
        pass

    @abstractmethod
    @commands.register(args = [], result = [])
    def free(self) -> Task[()]:
        """Immediately stop motor and go into freewheel."""
        pass

    @abstractmethod
    @commands.register(args = [], result = [])
    def unfree(self) -> Task[()]:
        """Enable asservissement and keep robot in current position."""
        pass

    @abstractmethod
    def on_pose_or_velocity_update(self) -> Event[Pose2D, Vect2D]:
        pass

    @abstractmethod
    @commands.register(args = [], result = Vect2D.ArgType())
    def get_velocity(self) -> Task[Vect2D]:
        pass

    @abstractmethod
    @commands.register(args = [], result = Pose2D.ArgType())
    def get_pose(self) -> Task[Pose2D]:
        pass

    @abstractmethod
    @commands.register(args = [], result = [
        ("pose", Pose2D.ArgType()),
        ("velocity", Vect2D.ArgType())
    ])
    def get_pose_and_velocity(self) -> Task[Pose2D, Vect2D]:
        pass

    @abstractmethod
    @commands.register(args = [("pose", Pose2D.ArgType())], result = [])
    def set_pose(self, pose: Pose2D) -> Task[()]:
        pass

    @abstractmethod
    @commands.register(args = [
        ("x", ArgTypes.F32()),
        ("y", ArgTypes.F32()),
    ], result = [])
    def go_to(self, x: float, y: float) -> Task[PilotMoveStatus]:
        """Move to the given position. The returned Task can be cancelled."""
        pass

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
    @commands.register(args = [
        ("heading", ArgTypes.F32()),
    ], result = [])
    def head_to(self, heading: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    @commands.register(args = [
        ("x", ArgTypes.F32()),
        ("y", ArgTypes.F32()),
    ], result = [])
    def look_at(self, x: float, y: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    @commands.register(args = [
        ("angle", ArgTypes.F32()),
    ], result = [])
    def rotate(self, angle: float) -> Task[PilotMoveStatus]:
        pass


class DifferentialPilot(Pilot):
    """
    Interface to control the movement of a differential robot.
    """

    commands = DriverCommands([Pilot.commands])

    @abstractmethod
    @commands.register(args = [
        ("forward", ArgTypes.F32()),
    ], result = [])
    def forward(self, distance: float) -> Task[PilotMoveStatus]:
        pass

    @abstractmethod
    def follow_path(self, waypoints: list[DifferentialPilotWaypoint]) -> Task[PilotMoveStatus]:
        pass


class HolonomicPilot(Pilot):
    """
    Interface to control the movement of a holonomic robot.
    It's extends the DifferentialPilot interface, so it has all the features of
    a differential robot plus some more.
    """

    commands = DriverCommands([Pilot.commands])

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
