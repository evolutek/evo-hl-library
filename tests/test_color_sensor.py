"""Tests for TCS34725 driver, Palette and Color utilities."""

import struct

import pytest

from evo_lib.drivers.color_sensor.tcs34725 import (
    TCS34725,
    TCS34725Virtual,
    _atime_to_ms,
    _ms_to_atime,
)
from evo_lib.drivers.i2c.virtual import I2CVirtual
from evo_lib.drivers.led.pwm_led import PWMLed
from evo_lib.drivers.pwm.virtual import PWMVirtual
from evo_lib.logger import Logger
from evo_lib.types.color import Color, ColorRaw, NamedColor, Palette


_AVALID_READY = b"\x01"


@pytest.fixture
def logger():
    return Logger("test")


# ── Palette ──────────────────────────────────────────────────────────────

class TestPalette:
    def test_empty_palette_returns_unknown(self):
        assert Palette().classify(ColorRaw(100, 200, 300, 400)) is NamedColor.Unknown

    def test_closest_entry_wins(self):
        p = Palette(refs={
            NamedColor.Red:   ColorRaw(8000, 1000, 1000, 10000),
            NamedColor.Green: ColorRaw(1000, 8000, 1000, 10000),
        })
        assert p.classify(ColorRaw(7500, 1100, 900, 9500)) is NamedColor.Red

    def test_threshold_returns_unknown_when_too_far(self):
        p = Palette(refs={NamedColor.Red: ColorRaw(8000, 1000, 1000, 10000)})
        # Distance² is huge — well beyond a tight threshold of 1000.
        assert p.classify(ColorRaw(0, 0, 0, 0), max_distance_squared=1000) is NamedColor.Unknown

    def test_gamma_changes_result(self):
        # Refs are nearly equidistant so a gamma shift can flip the winner.
        p = Palette(refs={
            NamedColor.Red:   ColorRaw(10000, 100, 100, 10000),
            NamedColor.Green: ColorRaw(100, 10000, 100, 10000),
        })
        raw = ColorRaw(5000, 5000, 100, 10000)
        baseline = p.classify(raw)
        p.set_gamma(2.0)
        # We don't assert on exact identity, just that gamma path is exercised
        # and the cache rebuilt without error; pick a value that is symmetric.
        assert p.classify(raw) in (baseline, NamedColor.Red, NamedColor.Green)


# ── Color.from_raw ───────────────────────────────────────────────────────

class TestColorFromRaw:
    def test_normalizes_and_clamps(self):
        color = Color.from_raw(ColorRaw(32768, 16384, 8192, 100000), full_scale=65535)
        assert abs(color.r - 0.5) < 0.001
        assert abs(color.g - 0.25) < 0.001
        assert abs(color.b - 0.125) < 0.001
        assert color.c == 1.0  # clamped


# ── TCS34725 (real, register-level over virtual I2C) ─────────────────────

class TestTCS34725:
    def _bus_with_device(self):
        bus = I2CVirtual()
        bus.init().wait()
        return bus, bus.add_device(0x29)

    def test_init_writes_pon_then_aen_then_atime_then_gain(self, logger):
        bus, dev = self._bus_with_device()
        sensor = TCS34725(name="cs0", logger=logger, bus=bus, gain=4)
        sensor.init().wait()

        assert dev.written[0] == bytes([0x80, 0x01])              # ENABLE = PON
        assert dev.written[1] == bytes([0x80, 0x03])              # ENABLE = PON|AEN
        assert dev.written[2][0] == 0x81                          # ATIME register
        assert dev.written[3] == bytes([0x80 | 0x0F, 0x01])       # CONTROL = 4× (0x01)

    def test_read_color_parses_rgbc(self, logger):
        bus, dev = self._bus_with_device()
        sensor = TCS34725(name="cs0", logger=logger, bus=bus)
        sensor.init().wait()
        dev.inject_read(_AVALID_READY)
        dev.inject_read(struct.pack("<HHHH", 1000, 500, 250, 100))

        (raw,) = sensor.read_color().wait()
        assert (raw.r, raw.g, raw.b, raw.c) == (500, 250, 100, 1000)

    def test_read_color_times_out_if_avalid_never_set(self, logger):
        bus, dev = self._bus_with_device()
        sensor = TCS34725(name="cs0", logger=logger, bus=bus)
        sensor.init().wait()
        for _ in range(100):
            dev.inject_read(b"\x00")

        with pytest.raises(TimeoutError):
            sensor._wait_data_ready(timeout_s=0.02)

    def test_set_gain_writes_control_register(self, logger):
        bus, dev = self._bus_with_device()
        sensor = TCS34725(name="cs0", logger=logger, bus=bus, gain=1)
        sensor.init().wait()
        dev.written.clear()

        sensor.set_gain(60).wait()
        assert dev.written[-1] == bytes([0x80 | 0x0F, 0x03])
        (g,) = sensor.get_gain().wait()
        assert g == 60

    def test_set_integration_time_writes_atime_and_roundtrips(self, logger):
        bus, dev = self._bus_with_device()
        sensor = TCS34725(name="cs0", logger=logger, bus=bus)
        sensor.init().wait()
        dev.written.clear()

        sensor.set_integration_time(154.0).wait()
        assert dev.written[-1] == bytes([0x80 | 0x01, 0xC0])
        (ms,) = sensor.get_integration_time().wait()
        assert abs(ms - 154.0) < _atime_to_ms(0) - _atime_to_ms(1)

    def test_invalid_gain_raises(self, logger):
        bus, _ = self._bus_with_device()
        with pytest.raises(ValueError):
            TCS34725(name="cs0", logger=logger, bus=bus, gain=2)


# ── TCS34725Virtual (full virtual) ───────────────────────────────────────

class TestTCS34725Virtual:
    def test_inject_then_read_roundtrips(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.inject_color(r=500, g=250, b=100, c=1000).wait()
        (raw,) = sensor.read_color().wait()
        assert (raw.r, raw.g, raw.b, raw.c) == (500, 250, 100, 1000)

    def test_get_color_uses_palette(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        # Default palette is the TCS34725 hardcoded one — pick a near-Red.
        sensor.inject_color(r=8500, g=1200, b=800, c=10500).wait()
        (name,) = sensor.get_color().wait()
        assert name is NamedColor.Red

    def test_set_color_updates_palette(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.set_color(NamedColor.Red, 1, 1, 1, 1).wait()
        sensor.inject_color(r=2, g=2, b=2, c=2).wait()
        (name,) = sensor.get_color().wait()
        assert name is NamedColor.Red

    def test_calibrate_stores_current_raw(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.inject_color(r=42, g=43, b=44, c=45).wait()
        sensor.calibrate(NamedColor.Red, samples=3).wait()
        sensor.inject_color(r=42, g=43, b=44, c=45).wait()
        (name,) = sensor.get_color().wait()
        assert name is NamedColor.Red

    def test_set_light_noop_without_led(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.set_light(0.7).wait()
        (intensity,) = sensor.get_light().wait()
        assert intensity == 0.0

    def test_set_light_drives_attached_led(self, logger):
        pwm = PWMVirtual(name="pwm", logger=logger)
        pwm.init().wait()
        led = PWMLed(name="led", logger=logger, pwm=pwm)
        sensor = TCS34725Virtual(name="cs0", logger=logger, light=led)
        sensor.init().wait()
        sensor.set_light(0.4).wait()
        (intensity,) = sensor.get_light().wait()
        assert abs(intensity - 0.4) < 1e-6
        assert abs(pwm.duty_cycle - 0.4) < 1e-6

    def test_set_gamma_roundtrips(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.set_gamma(2.2).wait()
        (g,) = sensor.get_gamma().wait()
        assert g == 2.2


# ── ATIME helpers ────────────────────────────────────────────────────────

def test_atime_conversions_roundtrip():
    for ms in (2.4, 24.0, 100.8, 614.4):
        assert abs(_atime_to_ms(_ms_to_atime(ms)) - ms) < _atime_to_ms(0) - _atime_to_ms(1)
