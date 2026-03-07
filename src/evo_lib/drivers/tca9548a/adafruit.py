"""TCA9548A mux + TCS34725 color sensor, Adafruit CircuitPython implementation."""

from __future__ import annotations

import logging

from evo_lib.component import Component, ComponentHolder
from evo_lib.interfaces.color_sensor import ColorSensor
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.color import Color

log = logging.getLogger(__name__)

NUM_CHANNELS = 8


class TCS34725Sensor(ColorSensor):
    """A single TCS34725 color sensor behind a TCA9548A mux channel.

    Calibration values (power_color, min_color, max_color) are stored here
    for external use by omnissiah's color classification logic. Raw readings
    from read_color() are not normalized against calibration -- that is the
    caller's responsibility.
    """

    def __init__(self, name: str, hw_sensor: object, channel: int) -> None:
        super().__init__(name)
        self._hw_sensor = hw_sensor
        self._channel = channel
        self._power_color: float = 0.0
        self._min_color: float = 0.0
        self._max_color: float = 1.0

    def init(self) -> None:
        # The mux handles hardware init.
        pass

    def close(self) -> None:
        # The mux handles hardware cleanup.
        pass

    def read_color(self) -> Task[Color]:
        """Read the TCS34725 and return raw Color (0.0-1.0 per channel).

        Channel selection is handled automatically by the Adafruit TCA9548A
        library: each hw_sensor holds a reference to the correct mux channel.
        """
        rgb = self._hw_sensor.color_rgb_bytes
        return ImmediateResultTask(Color(rgb[0] / 255.0, rgb[1] / 255.0, rgb[2] / 255.0))

    def calibrate(self, power_color: float, min_color: float, max_color: float) -> None:
        """Store calibration thresholds for this sensor.

        These values are stored for external use by omnissiah's color
        classification logic. They are not applied in read_color().
        """
        self._power_color = power_color
        self._min_color = min_color
        self._max_color = max_color


class TCA9548A(ComponentHolder):
    """TCA9548A I2C multiplexer managing TCS34725 color sensors on its channels.

    The Adafruit TCA9548A library handles channel selection transparently:
    accessing ``self._tca[channel]`` returns a virtual I2C bus for that channel.
    Sensors created via get_sensor() hold a reference to the correct channel,
    so no explicit channel switching is needed.
    """

    def __init__(self, name: str, i2c_bus: int, address: int = 0x70) -> None:
        super().__init__(name)
        self._i2c_bus = i2c_bus
        self._address = address
        self._tca = None
        self._children: list[TCS34725Sensor] = []

    def init(self) -> None:
        """Initialize the TCA9548A using Adafruit CircuitPython libs (lazy import)."""
        import board
        import busio
        import adafruit_tca9548a

        i2c = busio.I2C(board.SCL, board.SDA)
        self._tca = adafruit_tca9548a.TCA9548A(i2c, address=self._address)
        log.info("TCA9548A initialized at 0x%02x on bus %d", self._address, self._i2c_bus)

    def close(self) -> None:
        """Release hardware resources."""
        self._children.clear()
        self._tca = None
        log.info("TCA9548A closed")

    def get_subcomponents(self) -> list[Component]:
        """Return all registered TCS34725 sensor components."""
        return list(self._children)

    def get_sensor(self, channel: int, name: str) -> TCS34725Sensor:
        """Create and register a TCS34725 sensor on the given mux channel.

        The Adafruit library automatically selects the mux channel when the
        sensor performs I2C operations, so no explicit switching is needed.
        Returns the TCS34725Sensor component for that channel.
        """
        import adafruit_tcs34725

        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")

        hw_sensor = adafruit_tcs34725.TCS34725(self._tca[channel])
        log.info("TCS34725 found on TCA channel %d", channel)

        child = TCS34725Sensor(name, hw_sensor, channel)
        self._children.append(child)
        return child
