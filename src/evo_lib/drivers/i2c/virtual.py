"""I2C driver: in-memory virtual implementation for testing and simulation."""

import logging

from evo_lib.interfaces.i2c import I2C

log = logging.getLogger(__name__)


class I2CDeviceVirtual:
    """A virtual I2C device that responds to reads with injectable data.

    Register a device on a virtual bus to simulate hardware responses.
    The read buffer is consumed sequentially: each read_from pops bytes
    from the front.
    """

    def __init__(self, address: int):
        self.address = address
        self.written: list[bytes] = []
        self._read_buffer: bytearray = bytearray()

    def inject_read(self, data: bytes) -> None:
        """Queue bytes that will be returned by the next read_from."""
        self._read_buffer.extend(data)

    def consume_read(self, count: int) -> bytes:
        """Pop count bytes from the read buffer."""
        if len(self._read_buffer) < count:
            raise OSError(
                f"Virtual device 0x{self.address:02x}: read buffer underflow "
                f"(requested {count}, available {len(self._read_buffer)})"
            )
        result = bytes(self._read_buffer[:count])
        del self._read_buffer[:count]
        return result


class I2CVirtual(I2C):
    """In-memory I2C bus for testing.

    Devices must be registered with add_device() before they can be
    addressed. Reads consume from the device's injectable buffer,
    writes are recorded in the device's written list.
    """

    def __init__(self, name: str = "virtual"):
        super().__init__(name)
        self._devices: dict[int, I2CDeviceVirtual] = {}
        self._opened = False

    def init(self) -> None:
        self._opened = True

    def close(self) -> None:
        self._opened = False

    def _check_ready(self) -> None:
        if not self._opened:
            raise RuntimeError("Virtual I2C bus not opened, call init() first")

    def add_device(self, address: int) -> I2CDeviceVirtual:
        """Register a virtual device at the given address and return it."""
        device = I2CDeviceVirtual(address)
        self._devices[address] = device
        return device

    def get_device(self, address: int) -> I2CDeviceVirtual:
        """Retrieve a registered virtual device."""
        if address not in self._devices:
            raise OSError(f"No device at address 0x{address:02x}")
        return self._devices[address]

    def write_to(self, address: int, data: bytes) -> None:
        self._check_ready()
        device = self.get_device(address)
        device.written.append(data)

    def read_from(self, address: int, count: int) -> bytes:
        self._check_ready()
        device = self.get_device(address)
        return device.consume_read(count)

    def write_then_read(self, address: int, out_data: bytes, in_count: int) -> bytes:
        self._check_ready()
        device = self.get_device(address)
        device.written.append(out_data)
        return device.consume_read(in_count)

    def scan(self) -> list[int]:
        self._check_ready()
        return sorted(self._devices.keys())
