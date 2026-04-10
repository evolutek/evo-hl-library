"""Abstract interface for digital GPIO pins."""

from abc import abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Interface

if TYPE_CHECKING:
    from evo_lib.event import Event
    from evo_lib.task import Task


class GPIODirection(Enum):
    """Pin direction."""

    INPUT = "input"
    OUTPUT = "output"


class GPIOEdge(Enum):
    """Edge type for interrupt triggers."""

    RISING = "rising"
    FALLING = "falling"
    BOTH = "both"


class GPIO(Interface):
    """A single digital I/O pin (RPi GPIO, MCP23017 pin, etc.)."""

    commands = DriverCommands()

    @abstractmethod
    @commands.register(args = [], result = [
        ("state", ArgTypes.Bool(help = "The current state"))
    ])
    def read(self) -> Task[bool]:
        """Read current pin state (True = high, False = low)."""

    @abstractmethod
    @commands.register(args = [
        ("state", ArgTypes.Bool(help = "The state to set"))
    ], result = [])
    def write(self, state: bool) -> Task[None]:
        """Set the output state (True = high, False = low)."""

    @abstractmethod
    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        """Return an Event that triggers on the given edge.

        The event value is the new pin state.
        """
