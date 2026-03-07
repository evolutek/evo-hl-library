"""Tests for TCA9548A + TCS34725 driver using fake implementation."""

import pytest

from evo_hl.tca9548a.base import Color
from evo_hl.tca9548a.fake import TCA9548AFake


@pytest.fixture
def tca():
    drv = TCA9548AFake(address=0x70)
    drv.init()
    yield drv
    drv.close()


class TestTCA9548AFake:
    def test_setup_sensor(self, tca):
        assert tca.setup_sensor(0)
        assert 0 in tca.sensors

    def test_read_default_unknown(self, tca):
        tca.setup_sensor(3)
        assert tca.read_color(3) == Color.Unknown

    def test_inject_color(self, tca):
        tca.setup_sensor(1)
        tca.inject_color(1, Color.Red)
        assert tca.read_color(1) == Color.Red

    def test_inject_rgb(self, tca):
        tca.setup_sensor(2)
        tca.inject_rgb(2, (255, 128, 64))
        assert tca.read_rgb(2) == (255, 128, 64)

    def test_read_no_sensor_raises(self, tca):
        with pytest.raises(ValueError, match="No sensor"):
            tca.read_color(5)

    def test_bad_channel(self, tca):
        with pytest.raises(ValueError):
            tca.setup_sensor(8)

    def test_close_clears(self, tca):
        tca.setup_sensor(0)
        tca.close()
        assert len(tca.sensors) == 0
