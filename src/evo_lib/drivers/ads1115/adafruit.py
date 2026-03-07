"""ADS1115 driver using Adafruit CircuitPython (blinka-compatible SBCs)."""

from __future__ import annotations

import logging

from evo_lib.interfaces.analog_input import AnalogInput
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class ADS1115Adafruit(AnalogInput):
    """Single-channel ADS1115 analog input over I2C (Adafruit backend)."""

    def __init__(
        self, name: str, *, i2c_bus: int = 1, address: int = 0x48, channel: int = 0,
    ):
        super().__init__(name)
        self._i2c_bus = i2c_bus
        self._address = address
        self._channel = channel
        self._analog_in = None  # adafruit AnalogIn object
        self._i2c = None

    def init(self) -> None:
        # Lazy imports: only available on real hardware
        import board
        import busio
        from adafruit_ads1x15.ads1115 import ADS1115 as _HwADS1115
        from adafruit_ads1x15.ads1115 import P0, P1, P2, P3
        from adafruit_ads1x15.analog_in import AnalogIn as _AnalogIn

        pins = [P0, P1, P2, P3]
        if not 0 <= self._channel < len(pins):
            raise ValueError(
                f"Channel {self._channel} out of range (0-{len(pins) - 1})"
            )

        self._i2c = busio.I2C(board.SCL, board.SDA)
        ads = _HwADS1115(self._i2c, address=self._address)
        self._analog_in = _AnalogIn(ads, pins[self._channel])

        log.info(
            "ADS1115 channel %d initialized at 0x%02x (bus %d)",
            self._channel, self._address, self._i2c_bus,
        )

    def read_voltage(self) -> Task[float]:
        voltage = self._analog_in.voltage
        return ImmediateResultTask(voltage)

    def close(self) -> None:
        self._analog_in = None
        if self._i2c is not None:
            self._i2c.deinit()
            self._i2c = None
        log.info("ADS1115 channel %d closed", self._channel)
