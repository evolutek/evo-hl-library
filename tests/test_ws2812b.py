"""Tests for WS2812B LED strip driver using fake implementation."""

import pytest

from evo_hl.ws2812b.base import LedMode, LOADING_LED_COUNT, MODE_REFRESH
from evo_hl.ws2812b.fake import LedStripFake


@pytest.fixture
def strip():
    drv = LedStripFake(nb_leds=30, brightness=0.5)
    drv.init()
    yield drv
    drv.close()


class TestLedStripFake:
    def test_init_pixels(self, strip):
        assert len(strip.pixels) == 30
        assert all(p == (0, 0, 0) for p in strip.pixels)

    def test_set_pixel(self, strip):
        strip.set_pixel(0, 255, 0, 0)
        assert strip.pixels[0] == (255, 0, 0)
        assert strip.pixels[1] == (0, 0, 0)

    def test_set_pixel_bounds(self, strip):
        strip.set_pixel(-1, 255, 0, 0)  # out of bounds, no-op
        strip.set_pixel(30, 0, 255, 0)  # out of bounds, no-op
        assert all(p == (0, 0, 0) for p in strip.pixels)

    def test_fill(self, strip):
        strip.fill(0, 255, 0)
        assert all(p == (0, 255, 0) for p in strip.pixels)

    def test_set_mode(self, strip):
        strip.set_mode(LedMode.Running)
        assert strip.mode == LedMode.Running

    def test_set_mode_clears(self, strip):
        strip.fill(255, 0, 0)
        strip.set_mode(LedMode.Error)
        assert all(p == (0, 0, 0) for p in strip.pixels)

    def test_start_stop(self, strip):
        strip.start()
        assert strip.running is True
        strip.stop()
        assert strip.running is False

    def test_close_resets(self, strip):
        strip.fill(255, 255, 255)
        strip.start()
        strip.close()
        assert strip.running is False
        assert all(p == (0, 0, 0) for p in strip.pixels)

    def test_default_mode_loading(self, strip):
        assert strip.mode == LedMode.Loading

    def test_brightness_stored(self, strip):
        assert strip.brightness == 0.5


class TestLedMode:
    def test_all_modes_have_refresh(self):
        for mode in LedMode:
            assert mode in MODE_REFRESH

    def test_loading_led_count(self):
        assert LOADING_LED_COUNT > 0

    def test_mode_values(self):
        assert LedMode.Loading.value == "loading"
        assert LedMode.Running.value == "running"
        assert LedMode.Error.value == "error"
        assert LedMode.Disabled.value == "disabled"
