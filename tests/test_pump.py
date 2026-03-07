"""Tests for pump driver using fake and GPIO implementations."""

import pytest

from evo_hl.gpio.fake import GPIOFake
from evo_hl.pump.fake import PumpFake
from evo_hl.pump.gpio_pump import PumpGPIO


@pytest.fixture
def pump():
    return PumpFake()


@pytest.fixture
def gpio_pump():
    gpio = GPIOFake()
    gpio.init()
    gpio.setup_output(10)
    gpio.setup_output(11)
    return PumpGPIO(gpio, pump_pin=10, ev_pin=11), gpio


class TestPumpFake:
    def test_initial_state(self, pump):
        assert pump.pump_on is False
        assert pump.ev_open is False

    def test_grab(self, pump):
        pump.grab()
        assert pump.pump_on is True
        assert pump.ev_open is False

    def test_release(self, pump):
        pump.grab()
        pump.release()
        assert pump.pump_on is False
        assert pump.ev_open is True

    def test_stop_ev(self, pump):
        pump.release()
        pump.stop_ev()
        assert pump.ev_open is False

    def test_grab_release_cycle(self, pump):
        pump.grab()
        pump.release()
        pump.stop_ev()
        assert pump.pump_on is False
        assert pump.ev_open is False


class TestPumpGPIO:
    def test_grab_sets_pins(self, gpio_pump):
        pump, gpio = gpio_pump
        pump.grab()
        assert gpio.read(10) is True
        assert gpio.read(11) is False

    def test_release_sets_pins(self, gpio_pump):
        pump, gpio = gpio_pump
        pump.grab()
        pump.release()
        assert gpio.read(10) is False
        assert gpio.read(11) is True

    def test_stop_ev(self, gpio_pump):
        pump, gpio = gpio_pump
        pump.release()
        pump.stop_ev()
        assert gpio.read(11) is False

    def test_no_ev_pin(self):
        gpio = GPIOFake()
        gpio.init()
        gpio.setup_output(10)
        pump = PumpGPIO(gpio, pump_pin=10, ev_pin=None)
        pump.grab()
        assert gpio.read(10) is True
        pump.release()
        assert gpio.read(10) is False
        pump.stop_ev()  # no-op, should not raise
