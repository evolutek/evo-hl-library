"""Tests for virtual button driver."""

import pytest

from evo_lib.drivers.gpio.button import ButtonVirtual
from evo_lib.drivers.gpio.virtual import GPIOPinVirtual
from evo_lib.interfaces.gpio import GPIODirection
from evo_lib.logger import Logger


@pytest.fixture
def button():
    logger = Logger("test")
    gpio = GPIOPinVirtual(name="button_gpio", logger=logger, direction=GPIODirection.INPUT, pin=21)
    gpio.init().wait()
    b = ButtonVirtual(name="button", logger=logger, gpio=gpio, active_state=True)
    b.init().wait()
    # Button starts released (matches the physical idle state on a pull-down circuit).
    b.release().wait()
    yield b
    b.close()
    gpio.close()


@pytest.fixture
def active_low_button():
    """Button wired active-low (POWER_INT-style: pull-up + press pulls to GND)."""
    logger = Logger("test")
    gpio = GPIOPinVirtual(name="button_gpio", logger=logger, direction=GPIODirection.INPUT, pin=6)
    gpio.init().wait()
    b = ButtonVirtual(name="button", logger=logger, gpio=gpio, active_state=False)
    b.init().wait()
    b.release().wait()
    yield b
    b.close()
    gpio.close()


class TestButtonVirtual:
    def test_press_triggers_pressed_event(self, button):
        received = []
        button.get_trigger_event().register(lambda pressed: received.append(pressed))

        button.press().wait()
        assert received == [True]

    def test_release_after_press_triggers_not_pressed(self, button):
        received = []
        button.get_trigger_event().register(lambda pressed: received.append(pressed))

        button.press().wait()
        button.release().wait()
        assert received == [True, False]

    def test_is_pressed_reflects_state(self, button):
        assert button.is_pressed().wait() == (False,)
        button.press().wait()
        assert button.is_pressed().wait() == (True,)
        button.release().wait()
        assert button.is_pressed().wait() == (False,)

    def test_active_low_button_event_polarity(self, active_low_button):
        """For active-low wiring, the pressed event arg is still True on press."""
        received = []
        active_low_button.get_trigger_event().register(lambda pressed: received.append(pressed))

        active_low_button.press().wait()
        active_low_button.release().wait()
        assert received == [True, False]
