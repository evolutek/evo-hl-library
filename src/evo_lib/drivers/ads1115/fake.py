"""ADS1115 fake driver for testing without hardware."""

from __future__ import annotations

import logging

from evo_lib.interfaces.analog_input import AnalogInput
from evo_lib.task import ImmediateResultTask, Task

log = logging.getLogger(__name__)


class ADS1115Fake(AnalogInput):
    """In-memory ADS1115 single-channel analog input for tests and simulation."""

    def __init__(
        self, name: str, *, i2c_bus: int = 1, address: int = 0x48, channel: int = 0,
    ):
        super().__init__(name)
        self._i2c_bus = i2c_bus
        self._address = address
        self._channel = channel
        self._voltage: float = 0.0
        self._initialized: bool = False

    def init(self) -> None:
        if not 0 <= self._channel <= 3:
            raise ValueError(
                f"Channel {self._channel} out of range (0-3)"
            )
        self._voltage = 0.0
        self._initialized = True
        log.info(
            "ADS1115 fake channel %d initialized at 0x%02x",
            self._channel, self._address,
        )

    def inject_voltage(self, voltage: float) -> None:
        """Inject a voltage value for testing."""
        self._voltage = voltage

    def read_voltage(self) -> Task[float]:
        if not self._initialized:
            raise RuntimeError("ADS1115 not initialized, call init() first")
        return ImmediateResultTask(self._voltage)

    def close(self) -> None:
        self._voltage = 0.0
        self._initialized = False
        log.info("ADS1115 fake channel %d closed", self._channel)
