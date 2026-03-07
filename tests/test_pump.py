"""Tests for pump driver using fake and GPIO implementations."""

import pytest

from evo_lib.drivers.pump import PumpFake, PumpGPIO
from evo_lib.task import ImmediateResultTask


class _GPIOStub:
    """Minimal GPIO stub for testing (single-pin, matches GPIO interface)."""

    def __init__(self):
        self.state: bool = False

    def write(self, value: bool) -> ImmediateResultTask[None]:
        self.state = value
        return ImmediateResultTask(None)

    def read(self) -> ImmediateResultTask[bool]:
        return ImmediateResultTask(self.state)


@pytest.fixture
def pump():
    p = PumpFake()
    p.init()
    return p


@pytest.fixture
def gpio_pump():
    pin_pump = _GPIOStub()
    pin_ev = _GPIOStub()
    p = PumpGPIO("test-pump", pin_pump=pin_pump, pin_ev=pin_ev)
    p.init()
    return p, pin_pump, pin_ev


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

    def test_methods_return_tasks(self, pump):
        assert isinstance(pump.grab(), ImmediateResultTask)
        assert isinstance(pump.release(), ImmediateResultTask)
        assert isinstance(pump.stop_ev(), ImmediateResultTask)


class TestPumpGPIO:
    def test_grab_sets_pins(self, gpio_pump):
        pump, pin_pump, pin_ev = gpio_pump
        pump.grab()
        assert pin_pump.state is True
        assert pin_ev.state is False

    def test_release_sets_pins(self, gpio_pump):
        pump, pin_pump, pin_ev = gpio_pump
        pump.grab()
        pump.release()
        assert pin_pump.state is False
        assert pin_ev.state is True

    def test_stop_ev(self, gpio_pump):
        pump, pin_pump, pin_ev = gpio_pump
        pump.release()
        pump.stop_ev()
        assert pin_ev.state is False

    def test_no_ev_pin(self):
        pin_pump = _GPIOStub()
        pump = PumpGPIO("no-ev", pin_pump=pin_pump, pin_ev=None)
        pump.init()
        pump.grab()
        assert pin_pump.state is True
        pump.release()
        assert pin_pump.state is False
        pump.stop_ev()  # no-op, should not raise

    def test_methods_return_tasks(self, gpio_pump):
        pump, _, _ = gpio_pump
        assert isinstance(pump.grab(), ImmediateResultTask)
        assert isinstance(pump.release(), ImmediateResultTask)
        assert isinstance(pump.stop_ev(), ImmediateResultTask)

    def test_close_turns_off(self, gpio_pump):
        pump, pin_pump, pin_ev = gpio_pump
        pump.grab()
        pump.close()
        assert pin_pump.state is False
        assert pin_ev.state is False
