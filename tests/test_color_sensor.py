"""Tests for TCS34725 driver, the Color representation types and Palette classification."""

import struct

import pytest

from evo_lib.drivers.color_sensor.tcs34725 import (
    TCS34725,
    TCS34725_DEFAULT_PALETTE,
    TCS34725Virtual,
    _atime_to_ms,
    _ms_to_atime,
)
from evo_lib.drivers.i2c.virtual import I2CVirtual
from evo_lib.drivers.led.pwm_led import PWMLed
from evo_lib.drivers.pwm.virtual import PWMVirtual
from evo_lib.logger import Logger
from evo_lib.types.color import (
    PURE_COLORS,
    Color,
    ColorChroma,
    ColorHex,
    ColorHSV,
    ColorRGB,
    ColorRGBC,
    NamedColor,
    Palette,
)


_AVALID_READY = b"\x01"


@pytest.fixture
def logger():
    return Logger("test")


# ── Representation types ─────────────────────────────────────────────────

class TestColorRGBC:
    def test_to_rgb_normalizes_by_full_scale(self):
        rgbc = ColorRGBC(32768, 16384, 8192, 100000, full_scale=65535)
        rgb = rgbc.to_rgb()
        assert abs(rgb.r - 0.5) < 0.001
        assert abs(rgb.g - 0.25) < 0.001
        assert abs(rgb.b - 0.125) < 0.001

    def test_to_hsv_hue_indeprendent_of_scale(self):
        # Yellow-ish: R≈G >> B. Hue should be ~60° regardless of full_scale.
        a = ColorRGBC(1000, 1000, 0, 2000, full_scale=65535).to_hsv()
        b = ColorRGBC(10000, 10000, 0, 20000, full_scale=65535).to_hsv()
        assert abs(a.h - b.h) < 0.1
        assert abs(a.h - 60.0) < 1.0

    def test_to_chroma_zero_clear_returns_zero(self):
        ch = ColorRGBC(100, 100, 100, 0, full_scale=65535).to_chroma()
        assert ch == ColorChroma(0.0, 0.0, 0.0)

    def test_to_chroma_ratios(self):
        ch = ColorRGBC(1000, 500, 250, 2000, full_scale=65535).to_chroma()
        assert abs(ch.rc - 0.5) < 1e-6
        assert abs(ch.gc - 0.25) < 1e-6
        assert abs(ch.bc - 0.125) < 1e-6

    def test_chroma_invariant_to_intensity(self):
        # Doubling the illumination doubles all 4 channels → ratios unchanged.
        ch1 = ColorRGBC(1000, 500, 250, 2000).to_chroma()
        ch2 = ColorRGBC(2000, 1000, 500, 4000).to_chroma()
        assert ch1 == ch2


class TestColorHSV:
    def test_hue_wraps_modulo_360(self):
        assert ColorHSV(370.0, 0.5, 0.5).h == 10.0
        assert ColorHSV(-10.0, 0.5, 0.5).h == 350.0

    def test_to_rgb_primary_hues(self):
        # Red: h=0
        assert ColorHSV(0.0, 1.0, 1.0).to_rgb() == ColorRGB(1.0, 0.0, 0.0)
        # Green: h=120
        assert ColorHSV(120.0, 1.0, 1.0).to_rgb() == ColorRGB(0.0, 1.0, 0.0)
        # Blue: h=240
        assert ColorHSV(240.0, 1.0, 1.0).to_rgb() == ColorRGB(0.0, 0.0, 1.0)
        # Yellow: h=60
        assert ColorHSV(60.0, 1.0, 1.0).to_rgb() == ColorRGB(1.0, 1.0, 0.0)

    def test_grayscale_saturation_zero(self):
        rgb = ColorHSV(0.0, 0.0, 0.5).to_rgb()
        assert rgb == ColorRGB(0.5, 0.5, 0.5)


class TestColorHex:
    def test_out_of_range_raises(self):
        with pytest.raises(ValueError):
            ColorHex(-1)
        with pytest.raises(ValueError):
            ColorHex(0x1000000)

    def test_channel_accessors(self):
        c = ColorHex(0xAABBCC)
        assert (c.r8, c.g8, c.b8) == (0xAA, 0xBB, 0xCC)

    def test_roundtrip_through_rgb(self):
        assert ColorHex(0xFF8040).to_rgb().to_hex() == ColorHex(0xFF8040)


# ── Composite Color (lazy multi-repr) ────────────────────────────────────

class TestColor:
    def test_needs_at_least_one_source(self):
        with pytest.raises(ValueError):
            Color()

    def test_rgbc_source_derives_hsv_and_chroma(self):
        c = Color.from_rgbc(10000, 5000, 2500, 15000)
        # HSV derived from RGBC (preserves intensity).
        assert abs(c.hsv.h - 20.0) < 1.0  # orange-red
        # Chroma from RGBC uses the Clear channel.
        assert abs(c.chroma.rc - 10000 / 15000) < 1e-6

    def test_hex_source_gives_rgb_and_hsv(self):
        c = Color.from_hex(0x00FF00)
        assert c.rgb == ColorRGB(0.0, 1.0, 0.0)
        assert abs(c.hsv.h - 120.0) < 0.001

    def test_lazy_cache_is_stable_across_reads(self):
        c = Color.from_hex(0xABCDEF)
        first = c.hsv
        second = c.hsv
        assert first is second  # cached, same instance

    def test_name_is_preserved_in_repr(self):
        c = Color.from_hex(0xFF0000, name="Red")
        assert "Red" in repr(c)


class TestPureColors:
    def test_contains_all_named_colors_except_unknown(self):
        missing = [n for n in NamedColor if n is not NamedColor.Unknown and n not in PURE_COLORS]
        assert missing == []

    def test_red_hsv_is_zero(self):
        assert abs(PURE_COLORS[NamedColor.Red].hsv.h) < 0.001

    def test_yellow_hue_is_60(self):
        assert abs(PURE_COLORS[NamedColor.Yellow].hsv.h - 60.0) < 0.001


# ── Palette classification ───────────────────────────────────────────────

class TestPaletteHSV:
    def _palette(self):
        return Palette(refs=dict(TCS34725_DEFAULT_PALETTE))

    def test_empty_palette_returns_unknown(self):
        assert Palette().classify(Color.from_hex(0xFFFFFF)) is NamedColor.Unknown

    def test_yellow_sample_classifies_yellow(self):
        # Warm yellowish raw: r=8500, g=6500, b=800 → hue ≈ 44°, closest to palette's Yellow (~55°).
        measured = Color.from_rgbc(8500, 6500, 800, 15000)
        assert self._palette().classify(measured) is NamedColor.Yellow

    def test_blue_sample_classifies_blue(self):
        # Cool blueish: r=500, g=3500, b=5000 → hue ≈ 200°, closest to Blue (~232°).
        measured = Color.from_rgbc(500, 3500, 5000, 9000)
        assert self._palette().classify(measured) is NamedColor.Blue

    def test_low_saturation_is_unknown(self):
        # All channels near equal → saturation < 0.15 → Unknown.
        measured = Color.from_rgbc(1000, 1000, 950, 3000)
        assert self._palette().classify(measured) is NamedColor.Unknown

    def test_max_distance_caps_the_answer(self):
        # Cyan (hue 180°) is > 30° from every entry in the default palette
        # (closest is Blue at ~52°) → Unknown under a 30° cap.
        measured = Color.from_hsv(180.0, 1.0, 1.0)
        assert self._palette().classify(measured, max_distance=30.0) is NamedColor.Unknown


class TestPaletteChroma:
    def test_invariant_to_intensity(self):
        # Same ratios at two very different intensities → same classification.
        p = Palette(refs={
            NamedColor.Red: Color.from_rgbc(8500, 1200, 800, 10500),
            NamedColor.Blue: Color.from_rgbc(800, 1400, 5500, 7700),
        })
        dim = Color.from_rgbc(425, 60, 40, 525)   # 20× dimmer Red
        bright = Color.from_rgbc(17000, 2400, 1600, 21000)  # 2× brighter Red
        assert p.classify(dim, method="chroma") is NamedColor.Red
        assert p.classify(bright, method="chroma") is NamedColor.Red


class TestPaletteRGBC:
    def test_closest_raw_wins(self):
        p = Palette(refs={
            NamedColor.Red: Color.from_rgbc(8000, 1000, 1000, 10000),
            NamedColor.Green: Color.from_rgbc(1000, 8000, 1000, 10000),
        })
        measured = Color.from_rgbc(7500, 1100, 900, 9500)
        assert p.classify(measured, method="rgbc") is NamedColor.Red

    def test_unknown_ref_is_never_returned(self):
        # Even with a spot-on match on Unknown, classify must fall back to a real entry.
        p = Palette(refs={
            NamedColor.Unknown: Color.from_rgbc(0, 0, 0, 0),
            NamedColor.Red: Color.from_rgbc(8000, 1000, 1000, 10000),
        })
        assert p.classify(Color.from_rgbc(0, 0, 0, 0), method="rgbc") is NamedColor.Red


class TestPaletteMisc:
    def test_unknown_method_raises(self):
        with pytest.raises(ValueError):
            Palette(refs={NamedColor.Red: Color.from_hex(0xFF0000)}).classify(
                Color.from_hex(0xFF0000), method="bogus"
            )

    def test_default_method_is_hsv(self):
        p = Palette(refs={NamedColor.Red: Color.from_hex(0xFF0000)})
        # Low-saturation measurement triggers the HSV-only saturation floor.
        assert p.classify(Color.from_rgbc(500, 500, 500, 2000)) is NamedColor.Unknown


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

    def test_read_color_parses_rgbc_without_flash(self, logger):
        # No light wired → flash differential auto-disabled; single read path.
        bus, dev = self._bus_with_device()
        sensor = TCS34725(name="cs0", logger=logger, bus=bus)
        sensor.init().wait()
        dev.inject_read(_AVALID_READY)
        dev.inject_read(struct.pack("<HHHH", 1000, 500, 250, 100))

        (raw,) = sensor.read_color().wait()
        assert (raw.r, raw.g, raw.b, raw.c) == (500, 250, 100, 1000)
        assert raw.full_scale == sensor.get_full_scale()

    def test_flash_differential_subtracts_ambient(self, logger):
        # With a wired LED, read_color must produce a 2-read ON/OFF diff.
        bus, dev = self._bus_with_device()
        pwm = PWMVirtual(name="pwm", logger=logger)
        pwm.init().wait()
        led = PWMLed(name="led", logger=logger, pwm=pwm)
        sensor = TCS34725(
            name="cs0",
            logger=logger,
            bus=bus,
            light=led,
            integration_time_ms=3.0,  # keep the 1.5× sleep tiny
        )
        sensor.init().wait()
        dev.written.clear()

        # OFF (ambient only)
        dev.inject_read(_AVALID_READY)
        dev.inject_read(struct.pack("<HHHH", 300, 100, 100, 100))
        # ON (ambient + LED)
        dev.inject_read(_AVALID_READY)
        dev.inject_read(struct.pack("<HHHH", 2000, 1500, 500, 500))

        (raw,) = sensor.read_color().wait()
        assert (raw.r, raw.g, raw.b, raw.c) == (1400, 400, 400, 1700)

    def test_flash_disabled_skips_ambient_read(self, logger):
        bus, dev = self._bus_with_device()
        pwm = PWMVirtual(name="pwm", logger=logger)
        pwm.init().wait()
        led = PWMLed(name="led", logger=logger, pwm=pwm)
        sensor = TCS34725(
            name="cs0", logger=logger, bus=bus, light=led,
            integration_time_ms=3.0, use_flash_differential=False,
        )
        sensor.init().wait()
        dev.inject_read(_AVALID_READY)
        dev.inject_read(struct.pack("<HHHH", 2000, 1500, 500, 500))

        (raw,) = sensor.read_color().wait()
        # Single read → returned as-is, no subtraction.
        assert (raw.r, raw.g, raw.b, raw.c) == (1500, 500, 500, 2000)

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

    def test_get_full_scale_tracks_atime(self, logger):
        bus, _ = self._bus_with_device()
        sensor = TCS34725(name="cs0", logger=logger, bus=bus)
        sensor.init().wait()
        assert sensor.get_full_scale() == (256 - 0xD5) * 1024
        sensor.set_integration_time(614.4).wait()
        assert sensor.get_full_scale() == 65535

    def test_set_flash_differential_requires_wired_led(self, logger):
        bus, _ = self._bus_with_device()
        # No LED wired → setter must refuse to enable.
        sensor = TCS34725(name="cs0", logger=logger, bus=bus, use_flash_differential=False)
        sensor.set_flash_differential(True).wait()
        (enabled,) = sensor.get_flash_differential().wait()
        assert enabled is False

    def test_auto_expose_converges_immediately_at_target(self, logger):
        bus, dev = self._bus_with_device()
        sensor = TCS34725(name="cs0", logger=logger, bus=bus, integration_time_ms=3.0)
        sensor.init().wait()
        atime_before = sensor._atime
        # Reading already at target → ratio ≈ 1 → break immediately, no register write.
        dev.inject_read(_AVALID_READY)
        dev.inject_read(struct.pack("<HHHH", 30000, 100, 100, 100))
        sensor.auto_expose(target_c=30000).wait()
        assert sensor._atime == atime_before

    def test_calibrate_not_exposed_as_command(self):
        names = {cmd.name for cmd in TCS34725.commands.get_all()}
        assert "calibrate" not in names


# ── TCS34725Virtual ──────────────────────────────────────────────────────

class TestTCS34725Virtual:
    def test_inject_then_read_roundtrips(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.inject_color(r=500, g=250, b=100, c=1000).wait()
        (raw,) = sensor.read_color().wait()
        assert (raw.r, raw.g, raw.b, raw.c) == (500, 250, 100, 1000)

    def test_get_color_classifies_yellow_via_hsv(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.inject_color(r=8500, g=6500, b=800, c=15000).wait()
        (name,) = sensor.get_color().wait()
        assert name is NamedColor.Yellow

    def test_get_color_classifies_blue_via_hsv(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.inject_color(r=500, g=3500, b=5000, c=9000).wait()
        (name,) = sensor.get_color().wait()
        assert name is NamedColor.Blue

    def test_get_color_low_saturation_is_unknown(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.inject_color(r=1000, g=1000, b=950, c=3000).wait()
        (name,) = sensor.get_color().wait()
        assert name is NamedColor.Unknown

    def test_set_color_simulates_perception_of_named_entry(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.set_color(NamedColor.Red).wait()
        (raw,) = sensor.read_color().wait()
        ref = sensor._palette.get(NamedColor.Red)
        assert (raw.r, raw.g, raw.b, raw.c) == (
            ref.rgbc.r, ref.rgbc.g, ref.rgbc.b, ref.rgbc.c,
        )

    def test_set_color_raises_on_missing_palette_entry(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger, palette=Palette())
        sensor.init().wait()
        with pytest.raises(ValueError):
            sensor.set_color(NamedColor.Red).wait()

    def test_calibrate_stores_current_raw_in_palette(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger)
        sensor.init().wait()
        sensor.inject_color(r=42, g=43, b=44, c=45).wait()
        sensor.calibrate(NamedColor.Red, samples=3).wait()
        ref = sensor._palette.get(NamedColor.Red)
        assert (ref.rgbc.r, ref.rgbc.g, ref.rgbc.b, ref.rgbc.c) == (42, 43, 44, 45)

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

    def test_flash_differential_flag_roundtrips(self, logger):
        sensor = TCS34725Virtual(name="cs0", logger=logger, use_flash_differential=False)
        (enabled,) = sensor.get_flash_differential().wait()
        assert enabled is False
        sensor.set_flash_differential(True).wait()
        (enabled,) = sensor.get_flash_differential().wait()
        assert enabled is True

    def test_calibrate_exposed_as_command_on_virtual(self):
        names = {cmd.name for cmd in TCS34725Virtual.commands.get_all()}
        assert "calibrate" in names


# ── ATIME helpers ────────────────────────────────────────────────────────

def test_atime_conversions_roundtrip():
    for ms in (2.4, 24.0, 100.8, 614.4):
        assert abs(_atime_to_ms(_ms_to_atime(ms)) - ms) < _atime_to_ms(0) - _atime_to_ms(1)
