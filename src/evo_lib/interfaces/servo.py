"""Abstract interface for angle-controlled servos."""

from abc import abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    from evo_lib.task import Task


class ServoAngleUnit(IntEnum):
    NATIVE = 0
    DEGREES = 1
    FRACTION = 2
    RADIANS = 3


class Servo(Placable):
    """A servo that can move to an angle or be set as a fraction of its range.

    Abstracts away the underlying hardware (PCA9685 channel, direct PWM, etc.).
    """

    commands = DriverCommands()

    @abstractmethod
    @commands.register(
        args=[
            ("position", ArgTypes.U16(help="Target position in native units")),
            ("unit", ArgTypes.Enum(ServoAngleUnit, help="Unit of the position value")),
            ("wait_multiplier", ArgTypes.F32(help="Wait multiplier for move completion")),
        ],
        result=[],
    )
    def move_to(
        self,
        position: float,
        unit: ServoAngleUnit,
        wait_multiplier: float = 1.0,
        timeout: float | None = None,
    ) -> Task[()]:
        """Move to the given position."""

    @abstractmethod
    @commands.register(args=[], result=[])
    def free(self) -> Task[()]:
        """Disable PWM output (servo goes limp)."""
