"""Tests for WS2812B LED strip driver using fake implementation."""

import pytest

from evo_lib.drivers.ws2812b.fake import WS2812BFake
from evo_lib.types.color import Color


@pytest.fixture
def strip():
    drv = WS2812BFake(name="test-strip", num_pixels=30, brightness=0.5)
    drv.init()
    yield drv
    drv.close()


def _color_eq(a: Color, b: Color) -> bool:
    """Compare two colors with tolerance for float rounding."""
    return (
        abs(a.r - b.r) < 1e-9
        and abs(a.g - b.g) < 1e-9
        and abs(a.b - b.b) < 1e-9
    )


class TestWS2812BFake:
    def test_init_pixels(self, strip):
        assert len(strip.pixels) == 30
        assert all(_color_eq(p, Color(0.0, 0.0, 0.0)) for p in strip.pixels)

    def test_set_pixel(self, strip):
        red = Color(1.0, 0.0, 0.0)
        strip.set_pixel(0, red)
        assert _color_eq(strip.pixels[0], red)
        assert _color_eq(strip.pixels[1], Color(0.0, 0.0, 0.0))

    def test_set_pixel_out_of_bounds(self, strip):
        red = Color(1.0, 0.0, 0.0)
        with pytest.raises(IndexError):
            strip.set_pixel(-1, red)
        with pytest.raises(IndexError):
            strip.set_pixel(30, red)

    def test_get_pixel_out_of_bounds(self, strip):
        with pytest.raises(IndexError):
            strip.get_pixel(-1)
        with pytest.raises(IndexError):
            strip.get_pixel(30)

    def test_get_pixel(self, strip):
        blue = Color(0.0, 0.0, 1.0)
        strip.set_pixel(5, blue)
        assert _color_eq(strip.get_pixel(5), blue)

    def test_fill(self, strip):
        green = Color(0.0, 1.0, 0.0)
        strip.fill(green)
        assert all(_color_eq(p, green) for p in strip.pixels)

    def test_show_returns_task(self, strip):
        task = strip.show()
        assert task.wait() is None

    def test_clear(self, strip):
        strip.fill(Color(1.0, 1.0, 1.0))
        task = strip.clear()
        assert task.wait() is None
        assert all(_color_eq(p, Color(0.0, 0.0, 0.0)) for p in strip.pixels)

    def test_brightness(self, strip):
        assert strip.get_brightness() == 0.5
        strip.set_brightness(0.8)
        assert strip.get_brightness() == 0.8

    def test_num_pixels(self, strip):
        assert strip.num_pixels == 30

    def test_close_resets(self, strip):
        strip.fill(Color(1.0, 1.0, 1.0))
        strip.close()
        assert all(_color_eq(p, Color(0.0, 0.0, 0.0)) for p in strip.pixels)

    def test_name(self, strip):
        assert strip.name == "test-strip"

    def test_methods_before_init_raise(self):
        drv = WS2812BFake(name="uninit", num_pixels=10)
        red = Color(1.0, 0.0, 0.0)
        with pytest.raises(RuntimeError, match="not initialized"):
            drv.set_pixel(0, red)
        with pytest.raises(RuntimeError, match="not initialized"):
            drv.get_pixel(0)
        with pytest.raises(RuntimeError, match="not initialized"):
            drv.fill(red)
        with pytest.raises(RuntimeError, match="not initialized"):
            drv.show()
        with pytest.raises(RuntimeError, match="not initialized"):
            drv.clear()
