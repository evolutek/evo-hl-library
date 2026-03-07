"""Abstract base class for vacuum pump with optional electrovalve."""

from abc import abstractmethod
from typing import TYPE_CHECKING

from evo_lib.component import Component

if TYPE_CHECKING:
    from evo_lib.task import Task


class Pump(Component):
    """Controls a vacuum pump with an optional electrovalve (EV).

    - grab(): pump ON, EV closed -> suction
    - release(): pump OFF, EV open -> release
    - stop_ev(): EV closed (call after release delay)
    """

    @abstractmethod
    def grab(self) -> "Task[None]":
        """Activate pump (suction), close electrovalve."""

    @abstractmethod
    def release(self) -> "Task[None]":
        """Deactivate pump, open electrovalve to release."""

    @abstractmethod
    def stop_ev(self) -> "Task[None]":
        """Close electrovalve (call after release delay)."""
