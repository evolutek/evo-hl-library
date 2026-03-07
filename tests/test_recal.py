"""Tests for recalibration sensor drivers."""

import threading

import pytest

from evo_lib.drivers.gpio.fake import GPIOFake
from evo_lib.drivers.recal.fake import RecalFake
from evo_lib.drivers.recal.sensor import RecalGPIO
from evo_lib.interfaces.recal import RecalSensor


# -- RecalFake tests ----------------------------------------------------------


@pytest.fixture
def recal():
    sensor = RecalFake("test_recal")
    sensor.init()
    yield sensor
    sensor.close()


class TestRecalFake:
    def test_is_recal_sensor(self, recal):
        assert isinstance(recal, RecalSensor)

    def test_default_not_triggered(self, recal):
        assert recal.is_triggered().wait() is False

    def test_inject_triggered(self, recal):
        recal.inject(True)
        assert recal.is_triggered().wait() is True

    def test_inject_not_triggered(self, recal):
        recal.inject(True)
        recal.inject(False)
        assert recal.is_triggered().wait() is False

    def test_on_trigger_fires_on_change(self, recal):
        results = []
        event = recal.on_trigger()
        event.register(lambda v: results.append(v))

        recal.inject(True)
        assert results == [True]

        recal.inject(False)
        assert results == [True, False]

    def test_on_trigger_no_fire_on_same_state(self, recal):
        results = []
        event = recal.on_trigger()
        event.register(lambda v: results.append(v))

        recal.inject(False)  # same as default
        assert results == []

    def test_event_wait(self, recal):
        event = recal.on_trigger()
        got = threading.Event()

        def _wait():
            event.wait(timeout=1.0)
            got.set()

        t = threading.Thread(target=_wait, daemon=True)
        t.start()

        recal.inject(True)
        assert got.wait(timeout=1.0)

    def test_close_resets(self, recal):
        recal.inject(True)
        recal.close()
        assert recal.is_triggered().wait() is False

    def test_name(self, recal):
        assert recal.name == "test_recal"


# -- RecalGPIO tests (with injected GPIOFake) ---------------------------------


@pytest.fixture
def gpio():
    pin = GPIOFake("test_gpio_pin", pin=0)
    pin.init()
    yield pin
    pin.close()


@pytest.fixture
def recal_gpio(gpio):
    sensor = RecalGPIO("test_recal_gpio", gpio=gpio)
    sensor.init()
    yield sensor
    sensor.close()


class TestRecalGPIO:
    def test_is_recal_sensor(self, recal_gpio):
        assert isinstance(recal_gpio, RecalSensor)

    def test_default_triggered_when_pin_low(self, recal_gpio):
        # GPIOFake defaults to False (low), active-low means triggered
        assert recal_gpio.is_triggered().wait() is True

    def test_not_triggered_when_pin_high(self, gpio, recal_gpio):
        gpio.inject_input(True)
        assert recal_gpio.is_triggered().wait() is False

    def test_triggered_when_pin_goes_low(self, gpio, recal_gpio):
        gpio.inject_input(True)
        assert recal_gpio.is_triggered().wait() is False
        gpio.inject_input(False)
        assert recal_gpio.is_triggered().wait() is True

    def test_on_trigger_fires_inverted(self, gpio, recal_gpio):
        results = []
        recal_gpio.on_trigger().register(lambda v: results.append(v))

        # Pin goes high: recal event fires with not(True) = False
        gpio.inject_input(True)
        assert results == [False]

        # Pin goes low: recal event fires with not(False) = True
        gpio.inject_input(False)
        assert results == [False, True]

    def test_on_trigger_event_wait(self, gpio, recal_gpio):
        event = recal_gpio.on_trigger()
        got = threading.Event()

        def _wait():
            event.wait(timeout=1.0)
            got.set()

        t = threading.Thread(target=_wait, daemon=True)
        t.start()

        gpio.inject_input(True)
        assert got.wait(timeout=1.0)

    def test_name(self, recal_gpio):
        assert recal_gpio.name == "test_recal_gpio"
