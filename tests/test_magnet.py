"""Tests for magnet driver using fake and GPIO implementations."""

import pytest

from evo_hl.gpio.fake import GPIOFake
from evo_hl.magnet.fake import MagnetFake
from evo_hl.magnet.gpio_magnet import MagnetGPIO


@pytest.fixture
def magnet():
    return MagnetFake()


@pytest.fixture
def gpio_magnet():
    gpio = GPIOFake()
    gpio.init()
    gpio.setup_output(5)
    return MagnetGPIO(gpio, pin=5), gpio


class TestMagnetFake:
    def test_initial_state(self, magnet):
        assert magnet.active is False

    def test_on(self, magnet):
        magnet.on()
        assert magnet.active is True

    def test_off(self, magnet):
        magnet.on()
        magnet.off()
        assert magnet.active is False


class TestMagnetGPIO:
    def test_on_sets_pin(self, gpio_magnet):
        mag, gpio = gpio_magnet
        mag.on()
        assert gpio.read(5) is True

    def test_off_clears_pin(self, gpio_magnet):
        mag, gpio = gpio_magnet
        mag.on()
        mag.off()
        assert gpio.read(5) is False
