"""Tests for magnet driver using fake and GPIO implementations."""

import pytest

from evo_lib.drivers.magnet import MagnetFake, MagnetGPIO
from evo_lib.interfaces.gpio import GPIO, GPIOEdge
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.event import Event


class _GPIOStub(GPIO):
    """Minimal GPIO stub for testing MagnetGPIO without the full GPIO driver."""

    def __init__(self):
        super().__init__("stub-gpio")
        self._state: bool = False

    def init(self) -> None:
        self._state = False

    def close(self) -> None:
        self._state = False

    def read(self) -> Task[bool]:
        return ImmediateResultTask(self._state)

    def write(self, state: bool) -> Task[None]:
        self._state = state
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        return Event()


@pytest.fixture
def magnet():
    m = MagnetFake("test-magnet")
    m.init()
    return m


@pytest.fixture
def gpio_magnet():
    gpio = _GPIOStub()
    gpio.init()
    mag = MagnetGPIO("test-gpio-magnet", gpio)
    mag.init()
    return mag, gpio


class TestMagnetFake:
    def test_initial_state(self, magnet):
        assert magnet.is_active().wait() is False

    def test_activate(self, magnet):
        magnet.activate().wait()
        assert magnet.is_active().wait() is True

    def test_deactivate(self, magnet):
        magnet.activate().wait()
        magnet.deactivate().wait()
        assert magnet.is_active().wait() is False


class TestMagnetGPIO:
    def test_activate_sets_pin(self, gpio_magnet):
        mag, gpio = gpio_magnet
        mag.activate().wait()
        assert gpio.read().wait() is True
        assert mag.is_active().wait() is True

    def test_deactivate_clears_pin(self, gpio_magnet):
        mag, gpio = gpio_magnet
        mag.activate().wait()
        mag.deactivate().wait()
        assert gpio.read().wait() is False
        assert mag.is_active().wait() is False

    def test_close_deactivates(self, gpio_magnet):
        mag, gpio = gpio_magnet
        mag.activate().wait()
        mag.close()
        assert gpio.read().wait() is False
        assert mag.is_active().wait() is False
