"""Tests for ADS1115 driver using fake implementation."""

import pytest

from evo_lib.drivers.ads1115.fake import ADS1115Fake


@pytest.fixture
def adc():
    drv = ADS1115Fake("adc_ch0", channel=0)
    drv.init()
    yield drv
    drv.close()


class TestADS1115Fake:
    def test_init_zero(self, adc):
        assert adc.read_voltage().wait() == 0.0

    def test_inject_and_read(self, adc):
        adc.inject_voltage(1.65)
        assert adc.read_voltage().wait() == pytest.approx(1.65)

    def test_multiple_channels_independent(self):
        ch0 = ADS1115Fake("adc_ch0", channel=0)
        ch1 = ADS1115Fake("adc_ch1", channel=1)
        ch0.init()
        ch1.init()

        ch0.inject_voltage(3.3)
        ch1.inject_voltage(0.5)

        assert ch0.read_voltage().wait() == pytest.approx(3.3)
        assert ch1.read_voltage().wait() == pytest.approx(0.5)

        ch0.close()
        ch1.close()

    def test_close_resets(self, adc):
        adc.inject_voltage(1.0)
        adc.close()
        assert adc._voltage == 0.0

    def test_name(self, adc):
        assert adc.name == "adc_ch0"
