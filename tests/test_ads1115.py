"""Tests for ADS1115 driver using fake implementation."""

import pytest

from evo_hl.ads1115.fake import ADS1115Fake


@pytest.fixture
def adc():
    drv = ADS1115Fake(address=0x48)
    drv.init()
    yield drv
    drv.close()


class TestADS1115Fake:
    def test_init_all_zero(self, adc):
        for ch in range(4):
            assert adc.read_voltage(ch) == 0.0

    def test_inject_and_read(self, adc):
        adc.set_voltage(2, 1.65)
        assert adc.read_voltage(2) == pytest.approx(1.65)

    def test_channels_independent(self, adc):
        adc.set_voltage(0, 3.3)
        adc.set_voltage(3, 0.5)
        assert adc.read_voltage(0) == pytest.approx(3.3)
        assert adc.read_voltage(1) == pytest.approx(0.0)
        assert adc.read_voltage(3) == pytest.approx(0.5)

    def test_bad_channel(self, adc):
        with pytest.raises(ValueError):
            adc.read_voltage(4)

    def test_close_clears(self, adc):
        adc.set_voltage(0, 1.0)
        adc.close()
        assert len(adc.voltages) == 0
