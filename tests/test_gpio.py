"""Tests for GPIO driver using fake implementation."""

import pytest

from evo_hl.gpio.base import Edge
from evo_hl.gpio.fake import GPIOFake


@pytest.fixture
def gpio():
    drv = GPIOFake()
    drv.init()
    yield drv
    drv.close()


class TestGPIOFake:
    def test_setup_input(self, gpio):
        gpio.setup_input(17)
        assert 17 in gpio.pins
        assert gpio.pins[17]["output"] is False

    def test_setup_output(self, gpio):
        gpio.setup_output(18, default=True)
        assert gpio.pins[18]["output"] is True
        assert gpio.pins[18]["value"] is True

    def test_read_default_false(self, gpio):
        gpio.setup_input(5)
        assert gpio.read(5) is False

    def test_write_output(self, gpio):
        gpio.setup_output(12)
        gpio.write(12, True)
        assert gpio.read(12) is True

    def test_inject_input(self, gpio):
        gpio.setup_input(7)
        gpio.inject_input(7, True)
        assert gpio.read(7) is True

    def test_inject_ignored_on_output(self, gpio):
        gpio.setup_output(8, default=False)
        gpio.inject_input(8, True)
        assert gpio.read(8) is False

    def test_read_unknown_pin(self, gpio):
        assert gpio.read(99) is False

    def test_pwm_setup_and_set(self, gpio):
        gpio.setup_pwm(13, 1000.0)
        assert gpio.pins[13]["pwm"]["freq"] == 1000.0
        gpio.set_pwm(13, 50.0)
        assert gpio.pins[13]["pwm"]["duty"] == 50.0

    def test_pwm_stop(self, gpio):
        gpio.setup_pwm(13, 1000.0)
        gpio.set_pwm(13, 75.0)
        gpio.stop_pwm(13)
        assert gpio.pins[13]["pwm"] is None

    def test_close_clears(self, gpio):
        gpio.setup_output(1)
        gpio.setup_input(2)
        gpio.close()
        assert len(gpio.pins) == 0


class TestEdgeEnum:
    def test_values(self):
        assert Edge.FALLING.value == 0
        assert Edge.RISING.value == 1
        assert Edge.BOTH.value == 2
