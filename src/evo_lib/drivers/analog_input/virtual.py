"""AnalogInput drivers: virtual implementations for testing and simulation."""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.analog_input import AnalogInput
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task

NUM_CHANNELS = 4


class AnalogInputVirtual(AnalogInput):
    """In-memory analog input for tests and simulation."""

    def __init__(self, name: str, logger: Logger):
        super().__init__(name)
        self._log = logger
        self._voltage: float = 0.0

    def init(self) -> Task[()]:
        self._log.info(f"AnalogInputVirtual '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    def read_voltage(self) -> Task[float]:
        return ImmediateResultTask(self._voltage)

    def inject_voltage(self, voltage: float) -> None:
        """Set the voltage value returned by read_voltage (for testing)."""
        self._voltage = voltage


class AnalogInputChipVirtual(InterfaceHolder):
    """In-memory virtual ADC chip, for tests and simulation."""

    def __init__(self, name: str, logger: Logger):
        super().__init__(name)
        self._log = logger
        self._channels: dict[int, AnalogInputVirtual] = {}

    def init(self) -> Task[()]:
        self._log.info(f"AnalogInputChipVirtual '{self.name}' initialized")
        return ImmediateResultTask()

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
        ch = AnalogInputVirtual(name, self._log)
        self._channels[channel] = ch
        return ch


class ADS1115ChipVirtual(AnalogInputChipVirtual):
    """Virtual twin of ADS1115Chip: same constructor signature, in-memory.

    Delegates all ADC logic to AnalogInputChipVirtual. Accepts bus, address and
    fsr for drop-in config compatibility with ADS1115Chip, but ignores them
    (the virtual has no real I2C transport). Kept for signature parity —
    orthogonal to simulation.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        address: int = 0x48,
        fsr: float = 2.048,
    ):
        super().__init__(name, logger)
        self._bus = bus
        self._address = address
        self._fsr = fsr

    @property
    def fsr(self) -> float:
        return self._fsr

    def init(self) -> Task[()]:
        self._log.info(
            f"ADS1115ChipVirtual '{self.name}' initialized at 0x{self._address:02x}, "
            f"FSR=±{self._fsr:.3f}V"
        )
        return super().init()


class ADS1115ChipVirtualDefinition(DriverDefinition):
    """Factory for ADS1115ChipVirtual. Parent bus resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("address", ArgTypes.U8(), 0x48)
        defn.add_optional("fsr", ArgTypes.F32(), 2.048)
        return defn

    def create(self, args: DriverInitArgs) -> ADS1115ChipVirtual:
        return ADS1115ChipVirtual(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("bus"),
            address=args.get("address"),
            fsr=args.get("fsr"),
        )


class ADS1115ChannelVirtualDefinition(DriverDefinition):
    """Factory for a virtual ADS1115 channel on an ADS1115ChipVirtual.

    Mirrors ADS1115ChannelDefinition: resolves the chip by name, delegates
    channel creation to chip.get_channel() which returns an AnalogInputVirtual.
    """

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("chip", ArgTypes.Component(ADS1115ChipVirtual, self._peripherals))
        defn.add_required("channel", ArgTypes.U8(min_value=0, max_value=NUM_CHANNELS - 1))
        return defn

    def create(self, args: DriverInitArgs) -> AnalogInputVirtual:
        chip: ADS1115ChipVirtual = args.get("chip")
        return chip.get_channel(args.get("channel"), args.get_name())
