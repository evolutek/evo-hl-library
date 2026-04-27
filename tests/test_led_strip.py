"""Tests for the WS2812BVirtual LedStrip driver.

The real WS2812B driver is not exercised here: it requires DMA hardware and
``rpi_ws281x``, which is only available on a Pi with the optional ``rpi``
extra. The virtual is a faithful in-memory twin and shares the wire format
(packed 0xRRGGBB ints), so it covers the contract end-to-end.
"""

import pytest

from evo_lib.drivers.led_strip.ws2812b import (
    WS2812BVirtual,
    _pack_rgb,
    _unpack_rgb,
)
from evo_lib.logger import Logger


@pytest.fixture
def logger():
    return Logger("test")


@pytest.fixture
def strip(logger):
    s = WS2812BVirtual(name="strip", logger=logger, num_pixels=8)
    s.init().wait()
    return s


# ── Packing helpers ──────────────────────────────────────────────────────

class TestPacking:
    def test_pack_rgb_clamps_above_one(self):
        assert _pack_rgb(2.0, -0.5, 0.5) == 0xFF0080

    def test_unpack_round_trip(self):
        # Asymmetric values (not just (1,1,1)) so a R/B-swap bug shows up.
        for r, g, b in [(0.0, 0.0, 0.0), (1.0, 0.5, 0.25), (0.1, 0.2, 0.3)]:
            ru, gu, bu = _unpack_rgb(_pack_rgb(r, g, b))
            # Quantization through 8-bit ints: tolerate ±1/255.
            assert abs(ru - r) < 1 / 255 + 1e-9
            assert abs(gu - g) < 1 / 255 + 1e-9
            assert abs(bu - b) < 1 / 255 + 1e-9


# ── WS2812BVirtual ───────────────────────────────────────────────────────

class TestWS2812BVirtual:
    def test_zero_pixels_is_rejected(self, logger):
        with pytest.raises(ValueError):
            WS2812BVirtual(name="bad", logger=logger, num_pixels=0)

    def test_set_pixel_then_get_pixel_round_trips(self, strip):
        strip.set_pixel(3, 1.0, 0.5, 0.0).wait()
        r, g, b = strip.get_pixel(3).wait()
        assert abs(r - 1.0) < 1 / 255 + 1e-9
        assert abs(g - 0.5) < 1 / 255 + 1e-9
        assert abs(b - 0.0) < 1 / 255 + 1e-9

    def test_get_pixel_out_of_range_raises(self, strip):
        with pytest.raises(IndexError):
            strip.get_pixel(99).wait()

    def test_set_pixel_out_of_range_raises(self, strip):
        with pytest.raises(IndexError):
            strip.set_pixel(99, 1.0, 0.0, 0.0).wait()

    def test_fill_writes_every_pixel(self, strip):
        strip.fill(0.2, 0.4, 0.8).wait()
        for i in range(strip.num_pixels):
            r, g, b = strip.get_pixel(i).wait()
            assert abs(r - 0.2) < 1 / 255 + 1e-9
            assert abs(g - 0.4) < 1 / 255 + 1e-9
            assert abs(b - 0.8) < 1 / 255 + 1e-9

    def test_show_required_to_publish_buffer(self, strip):
        # Buffer-only writes don't update the shown frame.
        strip.fill(1.0, 0.0, 0.0).wait()
        for px in strip.get_shown_frame():
            assert px == (0.0, 0.0, 0.0)

        strip.show().wait()
        for r, g, b in strip.get_shown_frame():
            assert abs(r - 1.0) < 1 / 255 + 1e-9
            assert g == 0.0 and b == 0.0

    def test_clear_blacks_out_and_shows(self, strip):
        strip.fill(1.0, 1.0, 1.0).wait()
        strip.show().wait()
        strip.clear().wait()
        for px in strip.get_shown_frame():
            assert px == (0.0, 0.0, 0.0)

    def test_brightness_clamps(self, strip):
        strip.set_brightness(2.0).wait()
        (b,) = strip.get_brightness().wait()
        assert b == 1.0
        strip.set_brightness(-0.5).wait()
        (b,) = strip.get_brightness().wait()
        assert b == 0.0

    def test_pixel_clamps(self, strip):
        # Out-of-range floats are clamped at the byte boundary, not raised.
        strip.set_pixel(0, 5.0, -1.0, 0.5).wait()
        r, g, b = strip.get_pixel(0).wait()
        assert r == 1.0
        assert g == 0.0
        assert abs(b - 0.5) < 1 / 255 + 1e-9

    def test_signature_parity_with_real_driver(self):
        """The virtual must accept exactly the same kwargs as the real driver,
        per the swap invariant in CLAUDE.local.md — otherwise a real↔virtual
        config swap would force edits to other lines."""
        import inspect

        from evo_lib.drivers.led_strip.ws2812b import WS2812B

        real_params = set(inspect.signature(WS2812B.__init__).parameters)
        virt_params = set(inspect.signature(WS2812BVirtual.__init__).parameters)
        assert real_params == virt_params, (
            f"WS2812B vs WS2812BVirtual ctor mismatch: "
            f"only-real={real_params - virt_params}, only-virt={virt_params - real_params}"
        )
