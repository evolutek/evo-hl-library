"""Abstract base class for vacuum pump with optional electrovalve."""

from __future__ import annotations

from abc import ABC, abstractmethod

class Pump(ABC):
    """Controls a vacuum pump with an optional electrovalve (EV).

    - grab(): pump ON, EV closed → suction
    - release(): pump OFF, EV open → release
    - stop_ev(): EV closed (after release delay)
    """

    @abstractmethod
    def grab(self) -> None:
        """Activate pump (suction), close electrovalve."""

    @abstractmethod
    def release(self) -> None:
        """Deactivate pump, open electrovalve to release."""

    @abstractmethod
    def stop_ev(self) -> None:
        """Close electrovalve (call after release delay)."""
