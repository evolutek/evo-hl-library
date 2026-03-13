"""Abstract interface for addressable LED strips."""

from abc import abstractmethod

from evo_lib.component import Component

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from evo_lib.task import Task
    from evo_lib.color import Color


class LedStrip(Component):
    """An addressable RGB LED strip (e.g. WS2812B / NeoPixel)."""

    @abstractmethod
    def set_pixel(self, index: int, color: Color) -> None:
        """Set a single pixel color (buffered, call show() to apply)."""

    @abstractmethod
    def get_pixel(self, index: int) -> Color:
        """Get the color of the current pixel (in the buffer)."""

    @abstractmethod
    def fill(self, color: Color) -> None:
        """Set all pixels to the same color (buffered, call show() to apply)."""

    @abstractmethod
    def set_brightness(self, brightness: float) -> None:
        pass

    @abstractmethod
    def get_brightness(self) -> float:
        pass

    @abstractmethod
    def show(self) -> Task[None]:
        """Push the pixel buffer to the hardware."""

    @abstractmethod
    def clear(self) -> Task[None]:
        """Turn off all pixels and show immediately."""

    @property
    @abstractmethod
    def num_pixels(self) -> int:
        """Number of pixels in the strip."""
