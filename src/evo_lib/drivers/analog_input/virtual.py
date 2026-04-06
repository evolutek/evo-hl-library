"""AnalogInput drivers: virtual implementations for testing and simulation."""

import logging

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.analog_input import AnalogInput
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.task import ImmediateResultTask, Task

NUM_CHANNELS = 4


class AnalogInputVirtual(AnalogInput):
    """In-memory analog input for tests and simulation."""

    def __init__(self, name: str, logger: logging.Logger | None = None):
        super().__init__(name)
        self._log = logger or logging.getLogger(__name__)
        self._voltage: float = 0.0

    def init(self) -> None:
        self._log.info("AnalogInputVirtual '%s' initialized", self.name)

    def close(self) -> None:
        pass

    def read_voltage(self) -> Task[float]:
        return ImmediateResultTask(self._voltage)

    def inject_voltage(self, voltage: float) -> None:
        """Set the voltage value returned by read_voltage (for testing)."""
        self._voltage = voltage


class AnalogInputChipVirtual(InterfaceHolder):
    """In-memory virtual for the ADS1115 chip, for tests and simulation."""

    def __init__(self, name: str, logger: logging.Logger | None = None):
        super().__init__(name)
        self._log = logger or logging.getLogger(__name__)
        self._channels: dict[int, AnalogInputVirtual] = {}

    def init(self) -> None:
        self._log.info("AnalogInputChipVirtual '%s' initialized", self.name)

    def close(self) -> None:
        self._channels.clear()

    def get_subcomponents(self) -> list[Peripheral]:
        return list(self._channels.values())

    def get_channel(self, channel: int, name: str) -> AnalogInputVirtual:
        """Create or retrieve an AnalogInputVirtual for the given channel."""
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        if channel in self._channels:
            return self._channels[channel]
        ch = AnalogInputVirtual(name, logger=self._log)
        self._channels[channel] = ch
        return ch


class ADS1115ChipVirtualDefinition(DriverDefinition):
    """Factory for AnalogInputChipVirtual from config args."""

    def __init__(self, logger: Logger):
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        return defn

    def create(self, args: DriverInitArgs) -> AnalogInputChipVirtual:
        name = args.get("name")
        return AnalogInputChipVirtual(
            name=name,
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
