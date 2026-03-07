"""ADS1115 driver — Adafruit CircuitPython implementation."""

from __future__ import annotations

import logging

from evo_hl.ads1115.base import ADS1115, NUM_CHANNELS

log = logging.getLogger(__name__)


class ADS1115Adafruit(ADS1115):
    """ADS1115 over I2C using Adafruit CircuitPython (any blinka-supported SBC)."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._ads = None
        self._channels = {}

    def init(self) -> None:
        import board
        import busio
        from adafruit_ads1x15.ads1115 import ADS1115 as _HwADS1115, P0, P1, P2, P3
        from adafruit_ads1x15.analog_in import AnalogIn

        i2c = busio.I2C(board.SCL, board.SDA)
        self._ads = _HwADS1115(i2c, address=self.address)

        pins = [P0, P1, P2, P3]
        for ch in range(NUM_CHANNELS):
            self._channels[ch] = AnalogIn(self._ads, pins[ch])

        log.info("ADS1115 initialized at 0x%02x", self.address)

    def read_voltage(self, channel: int) -> float:
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        return self._channels[channel].voltage

    def close(self) -> None:
        self._channels.clear()
        self._ads = None
        log.info("ADS1115 closed")
