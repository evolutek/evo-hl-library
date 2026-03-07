"""ADS1115 driver — fake implementation for testing without hardware."""

from __future__ import annotations

import logging

from evo_hl.ads1115.base import ADS1115, NUM_CHANNELS

log = logging.getLogger(__name__)


class ADS1115Fake(ADS1115):
    """In-memory ADS1115 for tests and simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.voltages: dict[int, float] = {}

    def init(self) -> None:
        self.voltages = {ch: 0.0 for ch in range(NUM_CHANNELS)}
        log.info("ADS1115 fake initialized at 0x%02x", self.address)

    def set_voltage(self, channel: int, voltage: float) -> None:
        """Inject a voltage value for testing."""
        self.voltages[channel] = voltage

    def read_voltage(self, channel: int) -> float:
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        return self.voltages[channel]

    def close(self) -> None:
        self.voltages.clear()
        log.info("ADS1115 fake closed")
