"""Tests for GPIO driver using fake implementation."""

import threading
import time

import pytest

from evo_lib.drivers.gpio.fake import GPIOFake
from evo_lib.interfaces.gpio import GPIOEdge


@pytest.fixture
def gpio():
    drv = GPIOFake(name="test-pin", pin=17)
    drv.init()
    yield drv
    drv.close()


class TestGPIOFake:
    def test_read_default_false(self, gpio):
        assert gpio.read().wait() is False

    def test_write_and_read(self, gpio):
        gpio.write(True).wait()
        assert gpio.read().wait() is True

    def test_write_false(self, gpio):
        gpio.write(True).wait()
        gpio.write(False).wait()
        assert gpio.read().wait() is False

    def test_inject_input(self, gpio):
        gpio.inject_input(True)
        assert gpio.read().wait() is True

    def test_close_resets_state(self, gpio):
        gpio.write(True).wait()
        gpio.close()
        assert gpio.read().wait() is False

    def test_name(self, gpio):
        assert gpio.name == "test-pin"


class TestGPIOInterrupt:
    def test_interrupt_triggers_on_change(self, gpio):
        event = gpio.interrupt(GPIOEdge.BOTH)
        received = []

        def on_trigger(value):
            received.append(value)

        event.register(on_trigger)
        gpio.inject_input(True)
        assert received == [True]

    def test_interrupt_rising_only(self, gpio):
        event = gpio.interrupt(GPIOEdge.RISING)
        received = []
        event.register(lambda v: received.append(v))

        gpio.inject_input(True)   # rising: should fire
        gpio.inject_input(False)  # falling: should NOT fire
        assert received == [True]

    def test_interrupt_falling_only(self, gpio):
        gpio.inject_input(True)  # start high, no event yet
        event = gpio.interrupt(GPIOEdge.FALLING)
        received = []
        event.register(lambda v: received.append(v))

        gpio.inject_input(False)  # falling: should fire
        gpio.inject_input(True)   # rising: should NOT fire
        assert received == [False]

    def test_interrupt_no_fire_on_same_value(self, gpio):
        event = gpio.interrupt(GPIOEdge.BOTH)
        received = []
        event.register(lambda v: received.append(v))

        gpio.inject_input(False)  # same as default, no change
        assert received == []

    def test_interrupt_wait(self, gpio):
        event = gpio.interrupt(GPIOEdge.BOTH)

        def inject_later():
            time.sleep(0.05)
            gpio.inject_input(True)

        t = threading.Thread(target=inject_later)
        t.start()
        assert event.wait(timeout=1.0) is True
        t.join()


class TestGPIOEdgeEnum:
    def test_values(self):
        assert GPIOEdge.RISING.value == "rising"
        assert GPIOEdge.FALLING.value == "falling"
        assert GPIOEdge.BOTH.value == "both"
