"""Abstract interface for smart servos with position feedback (e.g. Dynamixel AX-12)."""

from abc import abstractmethod
from enum import IntEnum
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.interfaces.servo import Servo, ServoAngleUnit

if TYPE_CHECKING:
    from evo_lib.task import Task


class ServoSpeedUnit(IntEnum):
    NATIVE = 0
    RPM = 1
    DEGREES_PER_SECOND = 2
    RADIANS_PER_SECOND = 3


class SmartServo(Servo):
    """A servo with position feedback, speed control, and torque management.

    Unlike a basic Servo (fire-and-forget PWM), a SmartServo reports
    its actual position and can be queried at any time.
    """

    commands = DriverCommands(parents=[Servo.commands])

    @abstractmethod
    @commands.register(
        args=[
            ("unit", ArgTypes.Enum(ServoAngleUnit, help="Unit of the position value")),
        ],
        result=[("position", ArgTypes.U16(help="Current position in native units"))],
    )
    def get_position(self, unit: ServoAngleUnit) -> Task[float]:
        """Read current position."""

    @abstractmethod
    @commands.register(
        args=[
            ("speed", ArgTypes.F32(help="Movement speed as 'units' per second")),
            ("unit", ArgTypes.Enum(ServoSpeedUnit, help="Unit of the speed value")),
        ],
        result=[],
    )
    def set_speed(self, speed: float, unit: ServoSpeedUnit) -> Task[()]:
        """Set movement speed (in 'units' per second)."""

    @abstractmethod
    @commands.register(
        args=[
            ("unit", ArgTypes.Enum(ServoSpeedUnit, help="Unit of the speed value")),
        ],
        result=[("speed", ArgTypes.F32(help="Current speed in position units per second"))],
    )
    def get_speed(self, unit: ServoSpeedUnit) -> Task[float]:
        """Read present speed."""
        pass

    @abstractmethod
    @commands.register(
        args=[],
        result=[("load", ArgTypes.F32(help="Current load in 'units'"))],
    )
    def get_load(self) -> Task[float]:
        """Read present load in servo own units."""
        pass
