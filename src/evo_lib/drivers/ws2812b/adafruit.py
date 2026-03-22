"""WS2812B LED strip driver using Adafruit NeoPixel."""

from __future__ import annotations

import logging

from evo_lib.interfaces.led_strip import LedStrip
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.color import Color

log = logging.getLogger(__name__)


def _color_to_tuple(color: Color) -> tuple[int, int, int]:
    """Convert a Color (floats 0.0-1.0) to an RGB tuple (ints 0-255)."""
    return (
        round(color.r * 255),
        round(color.g * 255),
        round(color.b * 255),
    )


def _tuple_to_color(rgb: tuple[int, int, int]) -> Color:
    """Convert an RGB tuple (ints 0-255) to a Color (floats 0.0-1.0)."""
    return Color(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0)


class WS2812BAdafruit(LedStrip):
    """WS2812B NeoPixel strip using Adafruit CircuitPython (any blinka-supported SBC)."""

    def __init__(
        self,
        name: str,
        pin: int,
        num_pixels: int,
        brightness: float = 1.0,
        pixel_order: str = "GRB",
    ):
        super().__init__(name)
        self._pin = pin
        self._num_pixels = num_pixels
        self._brightness = brightness
        self._pixel_order = pixel_order
        self._strip = None

    def init(self) -> None:
        import board
        import neopixel

        board_pin = getattr(board, f"D{self._pin}")
        order = getattr(neopixel, self._pixel_order, neopixel.GRB)

        self._strip = neopixel.NeoPixel(
            board_pin,
            self._num_pixels,
            brightness=self._brightness,
            auto_write=False,
            pixel_order=order,
        )
        log.info("WS2812B initialized: %d LEDs on pin D%d", self._num_pixels, self._pin)

    def close(self) -> None:
        if self._strip is not None:
            self._strip.fill((0, 0, 0))
            self._strip.show()
            self._strip.deinit()
            self._strip = None
        log.info("WS2812B closed")

    def _require_init(self) -> None:
        """Raise if the strip has not been initialized."""
        if self._strip is None:
            raise RuntimeError("WS2812B not initialized")

    def set_pixel(self, index: int, color: Color) -> None:
        self._require_init()
        if not 0 <= index < self._num_pixels:
            raise IndexError(f"Pixel index {index} out of range [0, {self._num_pixels})")
        self._strip[index] = _color_to_tuple(color)

    def get_pixel(self, index: int) -> Color:
        self._require_init()
        if not 0 <= index < self._num_pixels:
            raise IndexError(f"Pixel index {index} out of range [0, {self._num_pixels})")
        rgb = self._strip[index]
        return _tuple_to_color(rgb)

    def fill(self, color: Color) -> None:
        self._require_init()
        self._strip.fill(_color_to_tuple(color))

    def set_brightness(self, brightness: float) -> None:
        self._brightness = brightness
        if self._strip is not None:
            self._strip.brightness = brightness

    def get_brightness(self) -> float:
        return self._brightness

    def show(self) -> Task[None]:
        self._require_init()
        self._strip.show()
        return ImmediateResultTask(None)

    def clear(self) -> Task[None]:
        self._require_init()
        self._strip.fill((0, 0, 0))
        self._strip.show()
        return ImmediateResultTask(None)

    @property
    def num_pixels(self) -> int:
        return self._num_pixels
