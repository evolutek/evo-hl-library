"""Abstract interface for electromagnet (on/off)."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.component import Component

if TYPE_CHECKING:
    from evo_lib.task import Task


class Magnet(Component):
    """Electromagnet (on/off)."""

    @abstractmethod
    def activate(self) -> "Task[None]":
        """Energize the magnet."""

    @abstractmethod
    def deactivate(self) -> "Task[None]":
        """De-energize the magnet."""

    @abstractmethod
    def is_active(self) -> "Task[bool]":
        """Return current state."""
