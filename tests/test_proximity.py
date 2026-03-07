"""Tests for proximity sensor drivers (read-only detection sensors)."""

import threading
import time

import pytest

from evo_lib.drivers.gpio.fake import GPIOFake
from evo_lib.drivers.proximity.fake import ProximityFake
from evo_lib.drivers.proximity.gpio_proximity import ProximityGPIO
from evo_lib.interfaces.gpio import GPIOEdge
from evo_lib.interfaces.proximity import ProximitySensor


@pytest.fixture
def prox():
    drv = ProximityFake(name="test-prox", pin=20)
    drv.init()
    yield drv
    drv.close()


@pytest.fixture
def gpio_fake():
    gpio = GPIOFake(name="pin-20", pin=20)
    gpio.init()
    yield gpio
    gpio.close()


@pytest.fixture
def prox_gpio(gpio_fake):
    drv = ProximityGPIO(name="test-prox-gpio", gpio=gpio_fake)
    drv.init()
    yield drv, gpio_fake
    drv.close()


class TestProximityFake:
    def test_is_proximity_sensor(self, prox):
        assert isinstance(prox, ProximitySensor)

    def test_read_default_false(self, prox):
        assert prox.read().wait() is False

    def test_inject_detected(self, prox):
        prox.inject_input(True)
        assert prox.read().wait() is True

    def test_inject_not_detected(self, prox):
        prox.inject_input(True)
        prox.inject_input(False)
        assert prox.read().wait() is False

    def test_no_write_method(self, prox):
        assert not hasattr(prox, "write")

    def test_name(self, prox):
        assert prox.name == "test-prox"

    def test_close_resets_state(self, prox):
        prox.inject_input(True)
        prox.close()
        assert prox.read().wait() is False


class TestProximityInterrupt:
    def test_interrupt_triggers_on_change(self, prox):
        event = prox.interrupt(GPIOEdge.BOTH)
        received = []
        event.register(lambda v: received.append(v))

        prox.inject_input(True)
        assert received == [True]

    def test_interrupt_rising_only(self, prox):
        event = prox.interrupt(GPIOEdge.RISING)
        received = []
        event.register(lambda v: received.append(v))

        prox.inject_input(True)   # rising: should fire
        prox.inject_input(False)  # falling: should NOT fire
        assert received == [True]

    def test_interrupt_falling_only(self, prox):
        prox.inject_input(True)  # start high, no event yet
        event = prox.interrupt(GPIOEdge.FALLING)
        received = []
        event.register(lambda v: received.append(v))

        prox.inject_input(False)  # falling: should fire
        prox.inject_input(True)   # rising: should NOT fire
        assert received == [False]

    def test_interrupt_no_fire_on_same_value(self, prox):
        event = prox.interrupt(GPIOEdge.BOTH)
        received = []
        event.register(lambda v: received.append(v))

        prox.inject_input(False)  # same as default, no change
        assert received == []

    def test_interrupt_wait(self, prox):
        event = prox.interrupt(GPIOEdge.BOTH)

        def inject_later():
            time.sleep(0.05)
            prox.inject_input(True)

        t = threading.Thread(target=inject_later)
        t.start()
        assert event.wait(timeout=1.0) is True
        t.join()


class TestProximityGPIO:
    """Tests for ProximityGPIO wrapping a GPIOFake via dependency injection."""

    def test_is_proximity_sensor(self, prox_gpio):
        prox, _ = prox_gpio
        assert isinstance(prox, ProximitySensor)

    def test_read_delegates_to_gpio(self, prox_gpio):
        prox, gpio = prox_gpio
        assert prox.read().wait() is False
        gpio.inject_input(True)
        assert prox.read().wait() is True

    def test_no_write_method(self, prox_gpio):
        prox, _ = prox_gpio
        assert not hasattr(prox, "write")

    def test_name(self, prox_gpio):
        prox, _ = prox_gpio
        assert prox.name == "test-prox-gpio"

    def test_interrupt_delegates_to_gpio(self, prox_gpio):
        prox, gpio = prox_gpio
        event = prox.interrupt(GPIOEdge.BOTH)
        received = []
        event.register(lambda v: received.append(v))

        gpio.inject_input(True)
        assert received == [True]

    def test_interrupt_rising_only(self, prox_gpio):
        prox, gpio = prox_gpio
        event = prox.interrupt(GPIOEdge.RISING)
        received = []
        event.register(lambda v: received.append(v))

        gpio.inject_input(True)   # rising: should fire
        gpio.inject_input(False)  # falling: should NOT fire
        assert received == [True]

    def test_interrupt_wait(self, prox_gpio):
        prox, gpio = prox_gpio
        event = prox.interrupt(GPIOEdge.BOTH)

        def inject_later():
            time.sleep(0.05)
            gpio.inject_input(True)

        t = threading.Thread(target=inject_later)
        t.start()
        assert event.wait(timeout=1.0) is True
        t.join()
