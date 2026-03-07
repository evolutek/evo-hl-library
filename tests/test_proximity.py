"""Tests for proximity sensor driver using fake and GPIO implementations."""

import pytest

from evo_hl.gpio.fake import GPIOFake
from evo_hl.proximity.fake import ProximityFake
from evo_hl.proximity.gpio_proximity import ProximityGPIO


@pytest.fixture
def prox():
    return ProximityFake()


@pytest.fixture
def gpio_prox():
    gpio = GPIOFake()
    gpio.init()
    gpio.setup_input(20)
    gpio.setup_input(21)
    return ProximityGPIO(gpio, pin_map={0: 20, 1: 21}), gpio


class TestProximityFake:
    def test_default_not_detected(self, prox):
        assert prox.read(0) is False

    def test_inject_detected(self, prox):
        prox.inject(0, True)
        assert prox.read(0) is True

    def test_inject_not_detected(self, prox):
        prox.inject(1, True)
        prox.inject(1, False)
        assert prox.read(1) is False

    def test_independent_sensors(self, prox):
        prox.inject(0, True)
        prox.inject(1, False)
        assert prox.read(0) is True
        assert prox.read(1) is False


class TestProximityGPIO:
    def test_read_from_gpio(self, gpio_prox):
        prox, gpio = gpio_prox
        gpio.inject_input(20, True)
        assert prox.read(0) is True
        assert prox.read(1) is False

    def test_unknown_sensor_raises(self, gpio_prox):
        prox, gpio = gpio_prox
        with pytest.raises(ValueError, match="Unknown sensor ID"):
            prox.read(99)
