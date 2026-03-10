"""Abstract interface for RGB color sensors."""

from __future__ import annotations

from abc import abstractmethod

from evo_hl.component import Component


class ColorSensor(Component):
    """An RGB color sensor (e.g. TCS34725 behind a TCA9548A mux)."""

    @abstractmethod
    def read_rgb(self) -> tuple[int, int, int]:
        """Read raw RGB values."""

    @abstractmethod
    def read_color(self) -> str:
        """Read and classify the detected color (e.g. "red", "blue", "unknown")."""
