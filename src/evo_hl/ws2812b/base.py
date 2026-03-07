"""Abstract base class for WS2812B addressable LED strip."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum

class LedMode(Enum):
    """LED strip display mode."""
    Disabled = "disabled"
    Error = "error"
    Loading = "loading"
    Running = "running"
# Refresh interval per mode (seconds)
MODE_REFRESH: dict[LedMode, float] = {
    LedMode.Disabled: 0.25,
    LedMode.Error: 0.5,
    LedMode.Loading: 0.05,
    LedMode.Running: 1.0,
}

# Number of lit LEDs in loading animation
LOADING_LED_COUNT = 10
class LedStrip(ABC):
    """Controls a WS2812B addressable LED strip.

    Supports multiple display modes (loading, running, error, disabled)
    with a background animation thread.
    """

    def __init__(self, nb_leds: int, brightness: float = 0.5):
        self.nb_leds = nb_leds
        self.brightness = brightness
        self.mode = LedMode.Loading

    @abstractmethod
    def init(self) -> None:
        """Initialize the LED strip hardware."""

    @abstractmethod
    def set_mode(self, mode: LedMode) -> None:
        """Switch display mode."""

    @abstractmethod
    def set_pixel(self, index: int, r: int, g: int, b: int) -> None:
        """Set a single pixel color."""

    @abstractmethod
    def fill(self, r: int, g: int, b: int) -> None:
        """Fill all pixels with a color."""

    @abstractmethod
    def show(self) -> None:
        """Push pixel buffer to the strip."""

    @abstractmethod
    def start(self) -> None:
        """Start the background animation thread."""

    @abstractmethod
    def stop(self) -> None:
        """Stop animation and turn off LEDs."""

    @abstractmethod
    def close(self) -> None:
        """Release hardware resources."""
