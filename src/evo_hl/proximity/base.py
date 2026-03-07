"""Abstract base class for proximity sensors (digital detection)."""

from __future__ import annotations

from abc import ABC, abstractmethod
class Proximity(ABC):
    """Reads a binary proximity detection from a digital input."""

    @abstractmethod
    def read(self, sensor_id: int) -> bool:
        """Returns True if an object is detected."""
