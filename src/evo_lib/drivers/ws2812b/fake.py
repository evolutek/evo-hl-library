"""WS2812B LED strip driver, in-memory fake for testing."""

from __future__ import annotations

import logging

from evo_lib.interfaces.led_strip import LedStrip
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.color import Color

log = logging.getLogger(__name__)

_BLACK = Color(0.0, 0.0, 0.0)


class WS2812BFake(LedStrip):
    """In-memory LED strip for tests and simulation."""

    def __init__(self, name: str, num_pixels: int, brightness: float = 1.0):
        super().__init__(name)
        self._num_pixels = num_pixels
        self._brightness = brightness
        self._pixels: list[Color] = []

    def init(self) -> None:
        self._pixels = [Color(0.0, 0.0, 0.0) for _ in range(self._num_pixels)]
        log.info("WS2812B fake initialized: %d LEDs", self._num_pixels)

    def close(self) -> None:
        self._pixels = [Color(0.0, 0.0, 0.0) for _ in range(self._num_pixels)]
        log.info("WS2812B fake closed")

    def _require_init(self) -> None:
        """Raise if the strip has not been initialized."""
        if not self._pixels:
            raise RuntimeError("WS2812B not initialized")

    def set_pixel(self, index: int, color: Color) -> None:
        self._require_init()
        if not 0 <= index < self._num_pixels:
            raise IndexError(f"Pixel index {index} out of range [0, {self._num_pixels})")
        self._pixels[index] = color

    def get_pixel(self, index: int) -> Color:
        self._require_init()
        if not 0 <= index < self._num_pixels:
            raise IndexError(f"Pixel index {index} out of range [0, {self._num_pixels})")
        return self._pixels[index]

    def fill(self, color: Color) -> None:
        self._require_init()
        self._pixels = [Color(color.r, color.g, color.b, color.a) for _ in range(self._num_pixels)]

    def set_brightness(self, brightness: float) -> None:
        self._brightness = brightness

    def get_brightness(self) -> float:
        return self._brightness

    def show(self) -> Task[None]:
        self._require_init()
        return ImmediateResultTask(None)

    def clear(self) -> Task[None]:
        self._require_init()
        self._pixels = [Color(0.0, 0.0, 0.0) for _ in range(self._num_pixels)]
        return ImmediateResultTask(None)

    @property
    def num_pixels(self) -> int:
        return self._num_pixels

    @property
    def pixels(self) -> list[Color]:
        """Access the pixel buffer (for test assertions)."""
        return self._pixels
