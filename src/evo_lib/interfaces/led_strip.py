"""Abstract interface for addressable LED strips."""

from __future__ import annotations

from abc import abstractmethod

from evo_lib.component import Component


class LedStrip(Component):
    """An addressable RGB LED strip (e.g. WS2812B / NeoPixel)."""

    @abstractmethod
    def set_pixel(self, index: int, r: int, g: int, b: int) -> None:
        """Set a single pixel color (buffered, call show() to apply)."""

    @abstractmethod
    def fill(self, r: int, g: int, b: int) -> None:
        """Set all pixels to the same color (buffered, call show() to apply)."""

    @abstractmethod
    def show(self) -> None:
        """Push the pixel buffer to the hardware."""

    @abstractmethod
    def clear(self) -> None:
        """Turn off all pixels and show immediately."""

    @property
    @abstractmethod
    def num_pixels(self) -> int:
        """Number of pixels in the strip."""
