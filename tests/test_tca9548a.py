"""Tests for TCA9548A + TCS34725 driver using fake implementation."""

import pytest

from evo_lib.drivers.tca9548a.config import TCA9548AConfig
from evo_lib.drivers.tca9548a.factory import create_tca9548a
from evo_lib.drivers.tca9548a.fake import TCA9548AFake, TCS34725SensorFake
from evo_lib.types.color import Color


@pytest.fixture
def tca():
    mux = TCA9548AFake(name="tca_test", i2c_bus=1, address=0x70)
    mux.init()
    yield mux
    mux.close()


class TestTCA9548AFake:
    def test_get_sensor(self, tca):
        sensor = tca.get_sensor(0, "sensor_0")
        assert isinstance(sensor, TCS34725SensorFake)
        assert sensor.name == "sensor_0"

    def test_subcomponents(self, tca):
        s0 = tca.get_sensor(0, "s0")
        s1 = tca.get_sensor(3, "s1")
        subs = tca.get_subcomponents()
        assert len(subs) == 2
        assert s0 in subs
        assert s1 in subs

    def test_read_default_black(self, tca):
        sensor = tca.get_sensor(1, "s1")
        color = sensor.read_color().wait()
        assert color.r == 0.0
        assert color.g == 0.0
        assert color.b == 0.0

    def test_inject_and_read_color(self, tca):
        sensor = tca.get_sensor(2, "s2")
        red = Color(1.0, 0.0, 0.0)
        sensor.inject_color(red)
        result = sensor.read_color().wait()
        assert result.r == 1.0
        assert result.g == 0.0
        assert result.b == 0.0

    def test_calibrate(self, tca):
        sensor = tca.get_sensor(0, "s0")
        sensor.calibrate(power_color=0.5, min_color=0.1, max_color=0.9)
        assert sensor._power_color == 0.5
        assert sensor._min_color == 0.1
        assert sensor._max_color == 0.9

    def test_bad_channel(self, tca):
        with pytest.raises(ValueError):
            tca.get_sensor(8, "bad")

    def test_close_clears(self, tca):
        tca.get_sensor(0, "s0")
        tca.close()
        assert len(tca.get_subcomponents()) == 0


class TestTCA9548AConfig:
    def test_defaults(self):
        cfg = TCA9548AConfig(name="tca")
        assert cfg.address == 0x70
        assert cfg.i2c_bus == 1
        assert cfg.channels == {}

    def test_custom(self):
        cfg = TCA9548AConfig(
            name="tca_mux",
            address=0x71,
            i2c_bus=2,
            channels={0: "color_left", 3: "color_right"},
        )
        assert cfg.name == "tca_mux"
        assert cfg.address == 0x71
        assert cfg.channels[3] == "color_right"


class TestTCA9548AFactory:
    def test_create_fake(self):
        cfg = TCA9548AConfig(
            name="tca_test",
            channels={0: "sensor_0", 3: "sensor_3"},
        )
        mux, sensors = create_tca9548a(cfg, fake=True)
        assert isinstance(mux, TCA9548AFake)
        assert len(sensors) == 2
        assert sensors[0].name == "sensor_0"
        assert sensors[3].name == "sensor_3"
        mux.close()

    def test_create_fake_empty(self):
        cfg = TCA9548AConfig(name="tca_empty")
        mux, sensors = create_tca9548a(cfg, fake=True)
        assert len(sensors) == 0
        mux.close()
