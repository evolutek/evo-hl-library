"""TCA9548A + TCS34725 fake implementation for testing without hardware."""

from __future__ import annotations

import logging

from evo_lib.component import Component, ComponentHolder
from evo_lib.interfaces.color_sensor import ColorSensor
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.color import Color

log = logging.getLogger(__name__)

NUM_CHANNELS = 8


class TCS34725SensorFake(ColorSensor):
    """Fake TCS34725 sensor for testing. Use inject_color() to set readings.

    Calibration values (power_color, min_color, max_color) are stored here
    for external use by omnissiah's color classification logic. Raw readings
    from read_color() are not normalized against calibration -- that is the
    caller's responsibility.
    """

    def __init__(self, name: str, channel: int) -> None:
        super().__init__(name)
        self._channel = channel
        self._color = Color(0.0, 0.0, 0.0)
        self._power_color: float = 0.0
        self._min_color: float = 0.0
        self._max_color: float = 1.0

    def init(self) -> None:
        pass

    def close(self) -> None:
        pass

    def read_color(self) -> Task[Color]:
        """Return the injected color."""
        return ImmediateResultTask(self._color)

    def calibrate(self, power_color: float, min_color: float, max_color: float) -> None:
        """Store calibration thresholds for external use. Not applied in read_color()."""
        self._power_color = power_color
        self._min_color = min_color
        self._max_color = max_color

    def inject_color(self, color: Color) -> None:
        """Inject a color reading for testing."""
        self._color = color


class TCA9548AFake(ComponentHolder):
    """In-memory TCA9548A mux for tests and simulation."""

    def __init__(self, name: str, i2c_bus: int = 1, address: int = 0x70) -> None:
        super().__init__(name)
        self._i2c_bus = i2c_bus
        self._address = address
        self._children: list[TCS34725SensorFake] = []

    def init(self) -> None:
        self._children.clear()
        log.info("TCA9548A fake initialized at 0x%02x", self._address)

    def close(self) -> None:
        self._children.clear()
        log.info("TCA9548A fake closed")

    def get_subcomponents(self) -> list[Component]:
        """Return all registered fake sensor components."""
        return list(self._children)

    def get_sensor(self, channel: int, name: str) -> TCS34725SensorFake:
        """Create and register a fake TCS34725 sensor on the given channel."""
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")

        child = TCS34725SensorFake(name, channel)
        self._children.append(child)
        log.info("Fake TCS34725 registered on TCA channel %d", channel)
        return child
