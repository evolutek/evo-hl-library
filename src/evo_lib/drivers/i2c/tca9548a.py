"""TCA9548A I2C multiplexer driver.

The TCA9548A sits on a parent I2C bus and exposes 8 downstream channels.
Each channel is itself an I2C: selecting a channel writes a control byte
to the TCA's address, then forwards operations on the parent bus.
"""

import logging
import threading

from evo_lib.interfaces.i2c import I2C
from evo_lib.peripheral import InterfaceHolder, Peripheral

log = logging.getLogger(__name__)

NUM_CHANNELS = 8


class TCA9548A(InterfaceHolder):
    """TCA9548A 8-channel I2C multiplexer.

    Sits on a parent I2C and provides get_channel() to obtain
    child I2C instances for each downstream channel.

    A lock ensures that channel selection + I2C operation are atomic,
    preventing race conditions when multiple threads use different channels.
    """

    def __init__(self, name: str, parent_bus: I2C, address: int = 0x70):
        super().__init__(name)
        self.parent_bus = parent_bus
        self.address = address
        self._lock = threading.Lock()
        self._current_channel: int | None = None
        self._channels: dict[int, TCA9548AChannel] = {}

    def init(self) -> None:
        pass

    def close(self) -> None:
        pass

    def get_subcomponents(self) -> list[Peripheral]:
        return list(self._channels.values())

    def select_channel(self, channel: int) -> None:
        """Write the channel bitmask to the TCA control register."""
        if self._current_channel == channel:
            return
        self.parent_bus.write_to(self.address, bytes([1 << channel]))
        self._current_channel = channel

    def get_channel(self, channel: int) -> TCA9548AChannel:
        """Return an I2C for the given mux channel (0-7)."""
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        if channel not in self._channels:
            self._channels[channel] = TCA9548AChannel(self, channel)
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

    def init(self) -> None:
        self._opened = True

    def close(self) -> None:
        self._opened = False

    def _check_ready(self) -> None:
        if not self._opened:
            raise RuntimeError(f"TCA9548A channel '{self.name}' not opened, call init() first")

    def write_to(self, address: int, data: bytes) -> None:
        self._check_ready()
        with self._mux._lock:
            self._mux.select_channel(self._channel)
            self._mux.parent_bus.write_to(address, data)

    def read_from(self, address: int, count: int) -> bytes:
        self._check_ready()
        with self._mux._lock:
            self._mux.select_channel(self._channel)
            return self._mux.parent_bus.read_from(address, count)

    def write_then_read(
        self, address: int, out_data: bytes, in_count: int
    ) -> bytes:
        self._check_ready()
        with self._mux._lock:
            self._mux.select_channel(self._channel)
            return self._mux.parent_bus.write_then_read(address, out_data, in_count)

    def scan(self) -> list[int]:
        self._check_ready()
        with self._mux._lock:
            self._mux.select_channel(self._channel)
            return [
                addr
                for addr in self._mux.parent_bus.scan()
                if addr != self._mux.address
            ]
