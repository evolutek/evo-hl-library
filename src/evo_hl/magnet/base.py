"""Abstract base class for electromagnet."""

from __future__ import annotations

from abc import ABC, abstractmethod
class Magnet(ABC):
    """Controls an electromagnet via a single digital output."""

    @abstractmethod
    def on(self) -> None:
        """Activate the electromagnet."""

    @abstractmethod
    def off(self) -> None:
        """Deactivate the electromagnet."""
