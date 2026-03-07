"""Abstract interface for recalibration distance sensors."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.component import Component

if TYPE_CHECKING:
    from evo_lib.event import Event
    from evo_lib.task import Task


class RecalSensor(Component):
    """Recalibration distance sensor for wall detection."""

    @abstractmethod
    def is_triggered(self) -> Task[bool]:
        """True if the sensor detects an obstacle within range."""

    @abstractmethod
    def on_trigger(self) -> Event[bool]:
        """Event fired when sensor state changes."""
