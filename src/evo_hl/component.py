"""Base class for all hardware components."""

from __future__ import annotations

from abc import ABC, abstractmethod


class Component(ABC):
    """Lifecycle contract shared by every hardware component.

    Every driver (real or fake) inherits from this and implements
    ``init`` (acquire resources) and ``close`` (release them).
    """

    @abstractmethod
    def init(self) -> None:
        """Acquire hardware resources."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""
