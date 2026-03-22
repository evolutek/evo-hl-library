"""Tests for GPIO driver using fake implementation."""

import threading
import time

import pytest

from evo_lib.drivers.gpio.fake import GPIOFake, INPUT, OUTPUT
from evo_lib.interfaces.gpio import GPIOEdge
from evo_lib.task import ImmediateErrorTask


@pytest.fixture
def gpio_in():
    drv = GPIOFake(name="test-in", pin=17, direction=INPUT)
    drv.init()
    yield drv
    drv.close()


@pytest.fixture
def gpio_out():
    drv = GPIOFake(name="test-out", pin=23, direction=OUTPUT)
    drv.init()
    yield drv
    drv.close()


class TestGPIOInput:
    def test_read_default_false(self, gpio_in):
        assert gpio_in.read().wait() is False

    def test_inject_input(self, gpio_in):
        gpio_in.inject_input(True)
        assert gpio_in.read().wait() is True

    def test_write_on_input_fails(self, gpio_in):
        task = gpio_in.write(True)
        assert isinstance(task, ImmediateErrorTask)
        with pytest.raises(NotImplementedError):
            task.wait()

    def test_close_prevents_use(self, gpio_in):
        gpio_in.close()
        with pytest.raises(RuntimeError):
            gpio_in.read()

    def test_name(self, gpio_in):
        assert gpio_in.name == "test-in"


class TestGPIOOutput:
    def test_write_and_default(self, gpio_out):
        gpio_out.write(True).wait()

    def test_read_on_output_fails(self, gpio_out):
        task = gpio_out.read()
        assert isinstance(task, ImmediateErrorTask)
        with pytest.raises(NotImplementedError):
            task.wait()

    def test_interrupt_on_output_fails(self, gpio_out):
        with pytest.raises(NotImplementedError):
            gpio_out.interrupt()


class TestGPIOInterrupt:
    def test_interrupt_triggers_on_change(self, gpio_in):
        event = gpio_in.interrupt(GPIOEdge.BOTH)
        received = []
        event.register(lambda v: received.append(v))
        gpio_in.inject_input(True)
        assert received == [True]

    def test_interrupt_rising_only(self, gpio_in):
        event = gpio_in.interrupt(GPIOEdge.RISING)
        received = []
        event.register(lambda v: received.append(v))
        gpio_in.inject_input(True)   # rising: should fire
        gpio_in.inject_input(False)  # falling: should NOT fire
        assert received == [True]

    def test_interrupt_falling_only(self, gpio_in):
        gpio_in.inject_input(True)
        event = gpio_in.interrupt(GPIOEdge.FALLING)
        received = []
        event.register(lambda v: received.append(v))
        gpio_in.inject_input(False)  # falling: should fire
        gpio_in.inject_input(True)   # rising: should NOT fire
        assert received == [False]

    def test_interrupt_no_fire_on_same_value(self, gpio_in):
        event = gpio_in.interrupt(GPIOEdge.BOTH)
        received = []
        event.register(lambda v: received.append(v))
        gpio_in.inject_input(False)  # same as default
        assert received == []

    def test_interrupt_wait(self, gpio_in):
        event = gpio_in.interrupt(GPIOEdge.BOTH)

        def inject_later():
            time.sleep(0.05)
            gpio_in.inject_input(True)

        t = threading.Thread(target=inject_later)
        t.start()
        assert event.wait(timeout=1.0) is True
        t.join()


class TestGPIOEdgeEnum:
    def test_values(self):
        assert GPIOEdge.RISING.value == "rising"
        assert GPIOEdge.FALLING.value == "falling"
        assert GPIOEdge.BOTH.value == "both"
