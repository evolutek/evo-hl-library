"""TCA9548A I2C multiplexer driver.

The TCA9548A sits on a parent I2C bus and exposes 8 downstream channels.
Each channel is itself an I2C: selecting a channel writes a control byte
to the TCA's address, then forwards operations on the parent bus.
"""

import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task

NUM_CHANNELS = 8


class TCA9548A(InterfaceHolder):
    """TCA9548A 8-channel I2C multiplexer.

    Sits on a parent I2C and provides get_channel() to obtain
    child I2C instances for each downstream channel.

    A lock ensures that channel selection + I2C operation are atomic,
    preventing race conditions when multiple threads use different channels.
    """

    def __init__(self, name: str, logger: Logger, parent_bus: I2C, address: int = 0x70):
        super().__init__(name)
        self._log = logger
        self.parent_bus = parent_bus
        self.address = address
        self._lock = threading.Lock()
        self._current_channel: int | None = None
        self._channels: dict[int, "TCA9548AChannel"] = {}

    def init(self) -> Task[()]:
        # Deselect all channels (write 0x00) to start from a known state,
        # even if a previous run left a channel active.
        self.parent_bus.write_to(self.address, bytes([0x00])).wait()
        self._current_channel = None
        self._log.info(f"TCA9548A '{self.name}' initialized at 0x{self.address:02x}")
        return ImmediateResultTask()

    def close(self) -> None:
        """Deselect all channels, close children, and reset internal state."""
        try:
            # Write 0x00 to the control register: deselects every channel,
            # leaving the mux in a known state for the next consumer.
            self.parent_bus.write_to(self.address, bytes([0x00])).wait()
        except OSError:
            self._log.warning(f"TCA9548A '{self.name}': I2C error during close")
        for ch in self._channels.values():
            ch.close()
        self._channels.clear()
        self._current_channel = None
        self._log.info(f"TCA9548A '{self.name}' closed")

    def get_subcomponents(self) -> list[Peripheral]:
        return list(self._channels.values())

    def select_channel(self, channel: int) -> None:
        """Write the channel bitmask to the TCA control register."""
        if self._current_channel == channel:
            return
        self.parent_bus.write_to(self.address, bytes([1 << channel])).wait()
        self._current_channel = channel
        self._log.debug(f"TCA9548A 0x{self.address:02x}: selected channel {channel}")

    def get_channel(self, channel: int) -> "TCA9548AChannel":
        """Return an I2C for the given mux channel (0-7)."""
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        if channel not in self._channels:
            self._channels[channel] = TCA9548AChannel(self, channel)
            self._log.info(f"TCA9548A 0x{self.address:02x}: created channel {channel}")
        return self._channels[channel]


class TCA9548AChannel(I2C):
    """One channel of a TCA9548A mux, presented as an I2C.

    Each operation acquires the mux lock, selects the channel, performs
    the I2C operation, then releases the lock. This guarantees that no
    other channel can be selected between select and operation.
    """

    def __init__(self, mux: TCA9548A, channel: int):
        super().__init__(f"{mux.name}.ch{channel}")
        self._mux = mux
        self._channel = channel
        self._opened = False

    def init(self) -> Task[()]:
        self._opened = True
        return ImmediateResultTask()

    def close(self) -> None:
        self._opened = False

    def _check_ready(self) -> None:
        if not self._opened:
            raise RuntimeError(f"TCA9548A channel '{self.name}' not opened, call init() first")

    def write_to(self, address: int, data: bytes) -> Task[()]:
        self._check_ready()
        with self._mux._lock:
            self._mux.select_channel(self._channel)
            self._mux.parent_bus.write_to(address, data).wait()
        return ImmediateResultTask(None)

    def read_from(self, address: int, count: int) -> Task[bytes]:
        self._check_ready()
        with self._mux._lock:
            self._mux.select_channel(self._channel)
            (data,) = self._mux.parent_bus.read_from(address, count).wait()
        return ImmediateResultTask(data)

    def write_then_read(self, address: int, out_data: bytes, in_count: int) -> Task[bytes]:
        self._check_ready()
        with self._mux._lock:
            self._mux.select_channel(self._channel)
            (data,) = self._mux.parent_bus.write_then_read(address, out_data, in_count).wait()
        return ImmediateResultTask(data)

    def scan(self) -> Task[list[int]]:
        self._check_ready()
        with self._mux._lock:
            self._mux.select_channel(self._channel)
            (addresses,) = self._mux.parent_bus.scan().wait()
        return ImmediateResultTask([addr for addr in addresses if addr != self._mux.address])


class TCA9548ADefinition(DriverDefinition):
    """Factory for TCA9548A from config args. Parent bus is resolved by name.

    The mux itself is an InterfaceHolder, not a bus, so it exposes no
    commands directly. Channels created via get_channel() are TCA9548AChannel
    instances that inherit I2C.commands via class-attribute lookup.
    """

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("address", ArgTypes.U8(), 0x70)
        return defn

    def create(self, args: DriverInitArgs) -> TCA9548A:
        return TCA9548A(
            name=args.get_name(),
            logger=self._logger,
            parent_bus=args.get("bus"),
            address=args.get("address"),
        )


class TCA9548AVirtual(TCA9548A):
    """Virtual twin of TCA9548A: inherits the real driver and bypasses writes
    to the mux control register.

    Follows the TiretteVirtual pattern: TCA9548A is mostly glue over the
    parent bus, so the virtual just overrides the 3 methods that touch the
    mux hardware (init, close, select_channel) to track state without any
    I2C write. Channel I/O still flows through parent_bus so downstream
    devices (on a virtual bus) work as usual.
    """

    def init(self) -> Task[()]:
        self._current_channel = None
        self._log.info(f"TCA9548AVirtual '{self.name}' initialized at 0x{self.address:02x}")
        return ImmediateResultTask()

    def close(self) -> None:
        for ch in self._channels.values():
            ch.close()
        self._channels.clear()
        self._current_channel = None
        self._log.info(f"TCA9548AVirtual '{self.name}' closed")

    def select_channel(self, channel: int) -> None:
        if self._current_channel == channel:
            return
        self._current_channel = channel
        self._log.debug(f"TCA9548AVirtual 0x{self.address:02x}: selected channel {channel} (simulated)")


class TCA9548AVirtualDefinition(DriverDefinition):
    """Factory for TCA9548AVirtual from config args."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("address", ArgTypes.U8(), 0x70)
        return defn

    def create(self, args: DriverInitArgs) -> TCA9548AVirtual:
        return TCA9548AVirtual(
            name=args.get_name(),
            logger=self._logger,
            parent_bus=args.get("bus"),
            address=args.get("address"),
        )
