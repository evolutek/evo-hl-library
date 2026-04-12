"""Abstract interface for angle-controlled servos."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    from evo_lib.task import Task


class Servo(Placable):
    """A servo that can move to an angle or be set as a fraction of its range.

    Abstracts away the underlying hardware (PCA9685 channel, direct PWM, etc.).
    """

    commands = DriverCommands()

    @abstractmethod
    @commands.register(
        args=[("angle", ArgTypes.F32(help="Target angle in degrees"))],
        result=[],
    )
    def move_to_angle(self, angle: float) -> Task[()]:
        """Move to the given angle (in degrees)."""

    @abstractmethod
    @commands.register(
        args=[("fraction", ArgTypes.F32(help="Target position as fraction of full range (0.0 to 1.0)"))],
        result=[],
    )
    def move_to_fraction(self, fraction: float) -> Task[()]:
        """Set position as a fraction of the full range (0.0 to 1.0)."""

    @abstractmethod
    @commands.register(args=[], result=[])
    def free(self) -> Task[()]:
        """Disable PWM output (servo goes limp)."""
