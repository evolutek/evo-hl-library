"""TCA9548A + TCS34725 driver — Adafruit CircuitPython implementation."""

from __future__ import annotations

import logging

from evo_hl.tca9548a.base import TCA9548A, Color, NUM_CHANNELS

log = logging.getLogger(__name__)

# Color detection sensitivity threshold.
# Higher = more false positives, lower = more false negatives.
_SENSITIVITY = 1.25


class TCA9548AAdafruit(TCA9548A):
    """TCA9548A mux + TCS34725 color sensors using Adafruit CircuitPython."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._tca = None
        self._sensors: dict[int, object] = {}
        self._calibration: dict[int, list[float]] = {}

    def init(self) -> None:
        import board
        import busio
        import adafruit_tca9548a

        i2c = busio.I2C(board.SCL, board.SDA)
        self._tca = adafruit_tca9548a.TCA9548A(i2c, address=self.address)
        log.info("TCA9548A initialized at 0x%02x", self.address)

    def setup_sensor(self, channel: int) -> bool:
        """Initialize a TCS34725 on the given TCA channel. Returns True on success."""
        import adafruit_tcs34725

        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        try:
            sensor = adafruit_tcs34725.TCS34725(self._tca[channel])
            self._sensors[channel] = sensor
            self._calibration[channel] = [0.0, 0.0, 0.0]
            log.info("TCS34725 found on TCA channel %d", channel)
            return True
        except Exception as e:
            log.warning("No TCS34725 on TCA channel %d: %s", channel, e)
            return False

    def calibrate(self, channel: int, samples: int = 10) -> None:
        """Calibrate ambient light on a sensor (average over samples)."""
        sensor = self._sensors.get(channel)
        if sensor is None:
            raise ValueError(f"No sensor on channel {channel}")

        cal = [0.0, 0.0, 0.0]
        import time
        for _ in range(samples):
            rgb = sensor.color_rgb_bytes
            cal[0] += rgb[0]
            cal[1] += rgb[1]
            cal[2] += rgb[2]
            time.sleep(0.1)
        self._calibration[channel] = [c / samples for c in cal]

    def read_rgb(self, channel: int) -> tuple[int, int, int]:
        sensor = self._sensors.get(channel)
        if sensor is None:
            raise ValueError(f"No sensor on channel {channel}")
        return sensor.color_rgb_bytes

    def read_color(self, channel: int) -> Color:
        sensor = self._sensors.get(channel)
        if sensor is None:
            raise ValueError(f"No sensor on channel {channel}")

        rgb = sensor.color_rgb_bytes
        cal = self._calibration[channel]
        values = [rgb[0] - cal[0], rgb[1] - cal[1], rgb[2] - cal[2]]
        index = values.index(max(values))

        if rgb[index] < cal[index] * _SENSITIVITY:
            return Color.Unknown

        return [Color.Red, Color.Green, Color.Blue][index]

    def close(self) -> None:
        self._sensors.clear()
        self._calibration.clear()
        self._tca = None
        log.info("TCA9548A closed")
