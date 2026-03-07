"""WS2812B LED strip driver — fake implementation for testing."""

from __future__ import annotations

import logging

from evo_hl.ws2812b.base import LedMode, LedStrip

log = logging.getLogger(__name__)


class LedStripFake(LedStrip):
    """In-memory LED strip for tests and simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.pixels: list[tuple[int, int, int]] = []
        self.running = False

    def init(self) -> None:
        self.pixels = [(0, 0, 0)] * self.nb_leds
        log.info("WS2812B fake initialized: %d LEDs", self.nb_leds)

    def set_pixel(self, index: int, r: int, g: int, b: int) -> None:
        if 0 <= index < self.nb_leds:
            self.pixels[index] = (r, g, b)

    def fill(self, r: int, g: int, b: int) -> None:
        self.pixels = [(r, g, b)] * self.nb_leds

    def show(self) -> None:
        pass  # no-op in fake

    def set_mode(self, mode: LedMode) -> None:
        self.mode = mode
        self.fill(0, 0, 0)

    def start(self) -> None:
        self.running = True

    def stop(self) -> None:
        self.running = False

    def close(self) -> None:
        self.running = False
        self.pixels = [(0, 0, 0)] * self.nb_leds
        log.info("WS2812B fake closed")
