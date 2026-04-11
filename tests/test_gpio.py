"""Tests for GPIO driver using virtual implementation."""

import pytest

from evo_lib.drivers.gpio.virtual import GPIOPinVirtual
from evo_lib.interfaces.gpio import GPIODirection, GPIOEdge
from evo_lib.logger import Logger
from evo_lib.task import ImmediateErrorTask


@pytest.fixture
def gpio_in():
    logger = Logger("test")
    drv = GPIOPinVirtual(name="test-in", logger=logger, direction=GPIODirection.INPUT, pin=17)
    drv.init()
    yield drv
    drv.close()


class TestGPIOInput:
    def test_inject_input(self, gpio_in):
        gpio_in.inject_input(True)
        assert gpio_in.read().wait() == (True,)

    def test_write_on_input_fails(self, gpio_in):
        task = gpio_in.write(True)
        assert isinstance(task, ImmediateErrorTask)
        with pytest.raises(NotImplementedError):
            task.wait()

    def test_close_prevents_use(self, gpio_in):
        gpio_in.close()
        with pytest.raises(RuntimeError):
            gpio_in.read()


class TestGPIOInterrupt:
    def test_interrupt_triggers_on_change(self, gpio_in):
        event = gpio_in.interrupt(GPIOEdge.BOTH)
        received = []
        event.register(lambda v: received.append(v))
        gpio_in.inject_input(True)
        gpio_in.inject_input(False)
        assert received == [True, False]

    def test_interrupt_rising_only(self, gpio_in):
        event = gpio_in.interrupt(GPIOEdge.RISING)
        received = []
        event.register(lambda v: received.append(v))
        gpio_in.inject_input(True)
        gpio_in.inject_input(False)
        assert received == [True]

    def test_interrupt_no_fire_on_same_value(self, gpio_in):
        event = gpio_in.interrupt(GPIOEdge.BOTH)
        received = []
        event.register(lambda v: received.append(v))
        gpio_in.inject_input(False)  # same as initial
        assert received == []
