"""Abstract interface for a single PWM output channel."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Interface

if TYPE_CHECKING:
    from evo_lib.task import Task


class PWM(Interface):
    """A single PWM output (e.g. one channel on a PCA9685).

    Abstracts away the underlying hardware so consumers (servos, LEDs, ESCs)
    don't need to know which chip generates the signal.
    """

    commands = DriverCommands()

    @abstractmethod
    @commands.register(
        args=[("duty", ArgTypes.F32(help="Duty cycle as a fraction (0.0 to 1.0)"))],
        result=[],
    )
    def set_duty_cycle(self, duty: float) -> Task[()]:
        """Set duty cycle as a fraction (0.0 to 1.0)."""

    @abstractmethod
    @commands.register(
        args=[("width_us", ArgTypes.F32(help="Pulse width in microseconds"))],
        result=[],
    )
    def set_pulse_width_us(self, width_us: float) -> Task[()]:
        """Set pulse width in microseconds.

        Requires a known frequency on the underlying hardware.
        Typical servo range: 500-2500 us at 50 Hz.
        """

    @abstractmethod
    @commands.register(args=[], result=[])
    def free(self) -> Task[()]:
        """Disable PWM output (full off)."""
