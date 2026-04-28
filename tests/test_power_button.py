"""Tests for virtual power button driver."""

import pytest

from evo_lib.drivers.gpio.power_button import PowerButtonVirtual
from evo_lib.drivers.gpio.virtual import GPIOPinVirtual
from evo_lib.interfaces.gpio import GPIODirection
from evo_lib.logger import Logger


@pytest.fixture
def power_button():
    """Soft-power button wired active-low (POWER_INT-style: pull-up, falling = press)."""
    logger = Logger("test")
    gpio_int = GPIOPinVirtual(
        name="power_int", logger=logger, direction=GPIODirection.INPUT, pin=6
    )
    gpio_hold = GPIOPinVirtual(
        name="power_hold", logger=logger, direction=GPIODirection.OUTPUT, pin=5
    )
    gpio_int.init().wait()
    gpio_hold.init().wait()
    pb = PowerButtonVirtual(
        name="power_button",
        logger=logger,
        gpio_int=gpio_int,
        gpio_hold=gpio_hold,
        active_state=False,
    )
    pb.init().wait()
    # Idle state on the int line: HIGH (button not pressed).
    pb.release().wait()
    yield pb, gpio_int, gpio_hold
    pb.close()
    gpio_int.close()
    gpio_hold.close()


class TestPowerButtonVirtual:
    def test_init_latches_power_high(self, power_button):
        """init() must immediately drive gpio_hold HIGH so the robot stays alive."""
        _, _, gpio_hold = power_button
        assert gpio_hold.read().wait() == (True,)

    def test_press_triggers_shutdown_event(self, power_button):
        pb, _, _ = power_button
        received = []
        pb.get_trigger_event().register(lambda: received.append(()))

        pb.press().wait()
        assert received == [()]

    def test_release_does_not_trigger_event(self, power_button):
        """The trigger event only fires on press (release is meaningless for soft-power)."""
        pb, _, _ = power_button
        received = []
        pb.get_trigger_event().register(lambda: received.append(()))

        pb.press().wait()
        pb.release().wait()
        assert received == [()]

    def test_release_power_drops_hold_low(self, power_button):
        """release_power() must drive gpio_hold LOW (physical power cut)."""
        pb, _, gpio_hold = power_button
        assert gpio_hold.read().wait() == (True,)

        pb.release_power().wait()
        assert gpio_hold.read().wait() == (False,)

    def test_close_does_not_release_power(self, power_button):
        """close() must NOT touch gpio_hold (would power-off on dev reload)."""
        pb, _, gpio_hold = power_button
        assert gpio_hold.read().wait() == (True,)

        pb.close()
        # gpio_hold not closed yet (would reset _state); the latch must
        # still be HIGH after PowerButton.close().
        assert gpio_hold.read().wait() == (True,)

    def test_is_pressed_reflects_int_state(self, power_button):
        """is_pressed reads gpio_int (not gpio_hold) — verifies wiring."""
        pb, _, _ = power_button
        assert pb.is_pressed().wait() == (False,)
        pb.press().wait()
        assert pb.is_pressed().wait() == (True,)
        pb.release().wait()
        assert pb.is_pressed().wait() == (False,)
