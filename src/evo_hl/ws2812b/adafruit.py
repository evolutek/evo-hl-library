"""WS2812B LED strip driver — Adafruit NeoPixel implementation."""

from __future__ import annotations

import logging
from threading import Event, Lock, Thread
from time import sleep

from evo_hl.ws2812b.base import (
    LOADING_LED_COUNT,
    MODE_REFRESH,
    LedMode,
    LedStrip,
)

log = logging.getLogger(__name__)

# Common colors (R, G, B)
_BLACK = (0, 0, 0)
_GREEN = (0, 255, 0)
_RED = (255, 0, 0)
_ORANGE = (255, 50, 0)
_BLUE = (0, 0, 255)


class LedStripAdafruit(LedStrip):
    """WS2812B NeoPixel strip using Adafruit CircuitPython (any blinka-supported SBC)."""

    def __init__(self, pin, **kwargs):
        super().__init__(**kwargs)
        self._pin = pin
        self._strip = None
        self._lock = Lock()
        self._stop_event = Event()
        self._loading_color = _BLUE
        self._current_led = 0
        self._blink_state = False

    def init(self) -> None:
        import neopixel

        self._strip = neopixel.NeoPixel(
            self._pin, self.nb_leds, brightness=self.brightness, auto_write=False,
        )
        log.info("WS2812B initialized: %d LEDs", self.nb_leds)

    def set_pixel(self, index: int, r: int, g: int, b: int) -> None:
        self._strip[index] = (r, g, b)

    def fill(self, r: int, g: int, b: int) -> None:
        self._strip.fill((r, g, b))

    def show(self) -> None:
        self._strip.show()

    def set_mode(self, mode: LedMode) -> None:
        with self._lock:
            self.mode = mode
            self.fill(*_BLACK)
            if mode == LedMode.Loading:
                self._current_led = self.nb_leds - 1
                for i in range(min(LOADING_LED_COUNT, self.nb_leds)):
                    self.set_pixel(i, *self._loading_color)
            elif mode in (LedMode.Disabled, LedMode.Error):
                self._blink_state = False
            self.show()
        log.info("WS2812B mode: %s", mode.value)

    def start(self) -> None:
        self._stop_event.clear()
        Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self._stop_event.set()

    def _run(self) -> None:
        while not self._stop_event.is_set():
            with self._lock:
                if self.mode == LedMode.Disabled:
                    for i in range(self.nb_leds):
                        color = _ORANGE if (self._blink_state ^ (i % 2 == 0)) else _BLACK
                        self.set_pixel(i, *color)
                    self._blink_state = not self._blink_state

                elif self.mode == LedMode.Error:
                    color = _RED if self._blink_state else _BLACK
                    self.fill(*color)
                    self._blink_state = not self._blink_state

                elif self.mode == LedMode.Loading:
                    self.set_pixel(self._current_led, *_BLACK)
                    next_led = (self._current_led + LOADING_LED_COUNT) % self.nb_leds
                    self.set_pixel(next_led, *self._loading_color)
                    self._current_led = (self._current_led + 1) % self.nb_leds

                elif self.mode == LedMode.Running:
                    self.fill(*_GREEN)

                self.show()

            sleep(MODE_REFRESH[self.mode])

        with self._lock:
            self.fill(*_BLACK)
            self.show()
        log.info("WS2812B animation stopped")

    def close(self) -> None:
        self.stop()
        if self._strip is not None:
            self._strip.fill(_BLACK)
            self._strip.show()
            self._strip = None
        log.info("WS2812B closed")
