"""Tests for virtual tirette driver."""

import pytest

from evo_lib.drivers.gpio.tirette import TiretteVirtual
from evo_lib.drivers.gpio.virtual import GPIOPinVirtual
from evo_lib.interfaces.gpio import GPIODirection
from evo_lib.logger import Logger


@pytest.fixture
def tirette():
    logger = Logger("test")
    gpio = GPIOPinVirtual(name="tirette_gpio", logger=logger, direction=GPIODirection.INPUT, pin=17)
    gpio.init().wait()
    t = TiretteVirtual(name="tirette", logger=logger, gpio=gpio, active_state=True)
    t.init().wait()
    # Tirette starts in place (like on the real robot)
    t.put().wait()
    yield t
    t.close()
    gpio.close()


class TestTiretteVirtual:
    def test_pull_triggers_pulled_event(self, tirette):
        received = []
        tirette.get_trigger_event().register(lambda pulled: received.append(pulled))

        tirette.pull().wait()
        assert received == [True]

    def test_put_after_pull_triggers_not_pulled(self, tirette):
        received = []
        tirette.get_trigger_event().register(lambda pulled: received.append(pulled))

        tirette.pull().wait()
        tirette.put().wait()
        assert received == [True, False]

    def test_no_event_on_same_state(self, tirette):
        """Putting when already in place should not trigger."""
        received = []
        tirette.get_trigger_event().register(lambda pulled: received.append(pulled))

        tirette.put().wait()
        assert received == []

    def test_full_cycle(self, tirette):
        received = []
        tirette.get_trigger_event().register(lambda pulled: received.append(pulled))

        tirette.pull().wait()
        tirette.put().wait()
        tirette.pull().wait()
        tirette.put().wait()
        assert received == [True, False, True, False]
