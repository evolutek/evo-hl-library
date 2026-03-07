"""Abstract interface for proximity sensors (read-only detection)."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.component import Component
from evo_lib.interfaces.gpio import GPIOEdge

if TYPE_CHECKING:
    from evo_lib.event import Event
    from evo_lib.task import Task


class ProximitySensor(Component):
    """Read-only proximity detection sensor.

    Unlike GPIO, this interface has no write() method.
    Implementations wrap a GPIO pin but only expose read and interrupt.
    """

    @abstractmethod
    def read(self) -> Task[bool]:
        """Read sensor state. True = object detected."""

    @abstractmethod
    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        """Return event triggered on detection state change."""
