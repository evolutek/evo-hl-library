"""Tests for WS2812B LED strip drivers."""

from evo_lib.drivers.led_strip.virtual import LedStripVirtual
from evo_lib.types.color import Color


class TestLedStripVirtual:
    def test_default_pixels_are_black(self):
        strip = LedStripVirtual("leds", num_pixels=8)
        strip.init()
        for p in strip.pixels:
            assert p.r == 0.0 and p.g == 0.0 and p.b == 0.0

    def test_set_and_get_pixel(self):
        strip = LedStripVirtual("leds", num_pixels=4)
        strip.init()
        red = Color(1.0, 0.0, 0.0)
        strip.set_pixel(1, red)
        assert strip.get_pixel(1).r == 1.0
        assert strip.get_pixel(0).r == 0.0

    def test_fill(self):
        strip = LedStripVirtual("leds", num_pixels=3)
        strip.init()
        blue = Color(0.0, 0.0, 1.0)
        strip.fill(blue)
        for p in strip.pixels:
            assert p.b == 1.0

    def test_clear(self):
        strip = LedStripVirtual("leds", num_pixels=3)
        strip.init()
        strip.fill(Color(1.0, 1.0, 1.0))
        strip.clear().wait()
        for p in strip.pixels:
            assert p.r == 0.0

    def test_brightness(self):
        strip = LedStripVirtual("leds", num_pixels=1, brightness=0.8)
        assert strip.get_brightness() == 0.8
        strip.set_brightness(0.3)
        assert abs(strip.get_brightness() - 0.3) < 0.001

    def test_num_pixels(self):
        strip = LedStripVirtual("leds", num_pixels=10)
        assert strip.num_pixels == 10

    def test_show_returns_task(self):
        strip = LedStripVirtual("leds", num_pixels=1)
        strip.init()
        task = strip.show()
        assert task.wait() is None
