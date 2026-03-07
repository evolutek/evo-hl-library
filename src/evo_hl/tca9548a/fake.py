"""TCA9548A + TCS34725 driver — fake implementation for testing without hardware."""

from __future__ import annotations

import logging

from evo_hl.tca9548a.base import TCA9548A, Color, NUM_CHANNELS

log = logging.getLogger(__name__)


class TCA9548AFake(TCA9548A):
    """In-memory TCA9548A + TCS34725 for tests and simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sensors: dict[int, dict] = {}

    def init(self) -> None:
        self.sensors.clear()
        log.info("TCA9548A fake initialized at 0x%02x", self.address)

    def setup_sensor(self, channel: int) -> bool:
        """Register a fake sensor on the given channel."""
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        self.sensors[channel] = {"color": Color.Unknown, "rgb": (0, 0, 0)}
        return True

    def inject_color(self, channel: int, color: Color) -> None:
        """Inject a color reading for testing."""
        if channel not in self.sensors:
            raise ValueError(f"No sensor on channel {channel}")
        self.sensors[channel]["color"] = color

    def inject_rgb(self, channel: int, rgb: tuple[int, int, int]) -> None:
        """Inject raw RGB values for testing."""
        if channel not in self.sensors:
            raise ValueError(f"No sensor on channel {channel}")
        self.sensors[channel]["rgb"] = rgb

    def read_color(self, channel: int) -> Color:
        if channel not in self.sensors:
            raise ValueError(f"No sensor on channel {channel}")
        return self.sensors[channel]["color"]

    def read_rgb(self, channel: int) -> tuple[int, int, int]:
        if channel not in self.sensors:
            raise ValueError(f"No sensor on channel {channel}")
        return self.sensors[channel]["rgb"]

    def close(self) -> None:
        self.sensors.clear()
        log.info("TCA9548A fake closed")
