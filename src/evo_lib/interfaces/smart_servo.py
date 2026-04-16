"""Abstract interface for smart servos with position feedback (e.g. Dynamixel AX-12)."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.interfaces.servo import Servo

if TYPE_CHECKING:
    from evo_lib.task import Task


class SmartServo(Servo):
    """A servo with position feedback, speed control, and torque management.

    Unlike a basic Servo (fire-and-forget PWM), a SmartServo reports
    its actual position and can be queried at any time.
    """

    commands = DriverCommands(parents=[Servo.commands])

    @abstractmethod
    @commands.register(
        args=[("position", ArgTypes.U16(help="Target position in native units"))],
        result=[],
    )
    def move_to_position(self, position: int) -> Task[()]:
        """Move to the given position (native units)."""

    @abstractmethod
    @commands.register(
        args=[],
        result=[("position", ArgTypes.U16(help="Current position in native units"))],
    )
    def get_position(self) -> Task[int]:
        """Read current position (in native units)."""

    @abstractmethod
    @commands.register(
        args=[],
        result=[("angle", ArgTypes.F32(help="Current angle in degrees"))],
    )
    def get_angle(self) -> Task[float]:
        """Read current position (in degrees)."""

    @abstractmethod
    @commands.register(
        args=[],
        result=[("fraction", ArgTypes.F32(help="Current position as fraction of full range"))],
    )
    def get_fraction(self) -> Task[float]:
        """Read current position (as a fraction between 0 and 1)."""

    @abstractmethod
    @commands.register(
        args=[("speed", ArgTypes.F32(help="Movement speed as a fraction (0.0 to 1.0)"))],
        result=[],
    )
    def set_speed(self, speed: float) -> Task[()]:
        """Set movement speed (as a fraction between 0 and 1)."""
