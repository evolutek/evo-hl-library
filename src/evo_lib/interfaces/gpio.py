"""Abstract interface for digital GPIO pins."""

from __future__ import annotations

from abc import abstractmethod
from enum import Enum
from typing import TYPE_CHECKING

from evo_lib.component import Component

if TYPE_CHECKING:
    from evo_lib.event import Event


class Edge(Enum):
    """Edge type for interrupt triggers."""

    RISING = "rising"
    FALLING = "falling"
    BOTH = "both"


class GPIO(Component):
    """A single digital I/O pin (RPi GPIO, MCP23017 pin, etc.)."""

    @abstractmethod
    def read(self) -> bool:
        """Read current pin state (True = high, False = low)."""

    @abstractmethod
    def write(self, state: bool) -> None:
        """Set the output state (True = high, False = low)."""

    @abstractmethod
    def interrupt(self, edge: Edge = Edge.BOTH) -> Event[bool]:
        """Return an Event that triggers on the given edge.

        The event value is the new pin state.
        """
