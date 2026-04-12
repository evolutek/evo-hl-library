"""I2C driver: real Raspberry Pi implementation via smbus2 / i2c_rdwr."""

import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.drivers.i2c.virtual import I2CDeviceVirtual, I2CVirtual
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class RpiI2C(I2C):
    """Real I2C bus on a Raspberry Pi via smbus2.

    Opens /dev/i2c-N through smbus2.SMBus and uses i2c_rdwr for the three
    raw transaction flavours (write, read, write-then-read). smbus2 is a
    pure-Python wrapper on the kernel ioctl interface, so no GPIO-backend
    library is needed at import time.

    All operations are serialized with a threading.Lock so that multiple
    threads sharing the same bus block properly instead of spin-waiting.
    """

    def __init__(self, name: str, logger: Logger, bus: int = 1):
        super().__init__(name)
        self._log = logger
        self._bus_number = bus
        self._i2c = None
        self._lock = threading.Lock()

    def init(self) -> Task[()]:
        """Open the I2C bus. Must be called before any read/write."""
        from smbus2 import SMBus

        self._i2c = SMBus(self._bus_number)
        self._log.info(f"I2C bus {self._bus_number} opened")
        return ImmediateResultTask()

    def close(self) -> None:
        """Release the I2C bus."""
        if self._i2c is not None:
            self._i2c.close()
            self._i2c = None
            self._log.info(f"I2C bus {self._bus_number} closed")

    def _check_ready(self) -> None:
        if self._i2c is None:
            raise RuntimeError("I2C bus not opened, call init() first")

    def write_to(self, address: int, data: bytes) -> Task[()]:
        from smbus2 import i2c_msg
        self._check_ready()
        with self._lock:
            self._i2c.i2c_rdwr(i2c_msg.write(address, data))
        return ImmediateResultTask(None)

    def read_from(self, address: int, count: int) -> Task[bytes]:
        from smbus2 import i2c_msg
        self._check_ready()
        msg = i2c_msg.read(address, count)
        with self._lock:
            self._i2c.i2c_rdwr(msg)
        return ImmediateResultTask(bytes(msg))

    def write_then_read(self, address: int, out_data: bytes, in_count: int) -> Task[bytes]:
        from smbus2 import i2c_msg
        self._check_ready()
        write = i2c_msg.write(address, out_data)
        read = i2c_msg.read(address, in_count)
        with self._lock:
            # Combined write+read in one transaction (repeated-START between).
            self._i2c.i2c_rdwr(write, read)
        return ImmediateResultTask(bytes(read))

    def scan(self) -> Task[list[int]]:
        """Probe each valid 7-bit I2C address and return the ones that ACK.

        smbus2 has no built-in scan; we iterate the standard range 0x03-0x77
        and count a write_quick ACK as "device present". Reserved addresses
        (0x00-0x02, 0x78-0x7F) are skipped per the I2C spec.
        """
        self._check_ready()
        found: list[int] = []
        with self._lock:
            for addr in range(0x03, 0x78):
                try:
                    self._i2c.write_quick(addr)
                    found.append(addr)
                except OSError:
                    pass
        return ImmediateResultTask(found)


class RpiI2CDefinition(DriverDefinition):
    """Factory for RpiI2C from config args."""

    def __init__(self, logger: Logger):
        super().__init__(RpiI2C.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_optional("bus", ArgTypes.U8(), 1)
        return defn

    def create(self, args: DriverInitArgs) -> RpiI2C:
        return RpiI2C(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("bus"),
        )


class RpiI2CVirtual(I2C):
    """Virtual twin of RpiI2C: same constructor signature, pure in-memory.

    Delegates to I2CVirtual for all I2C logic. Accepts the same arguments
    as RpiI2C so the factory can swap them transparently in config.
    Exposes add_device() / get_device() for simulation setups.
    """

    def __init__(self, name: str, logger: Logger, bus: int = 1):
        super().__init__(name)
        self._log = logger
        self._bus_number = bus
        self._inner = I2CVirtual(name)

    def init(self) -> Task[()]:
        self._log.info(f"RpiI2CVirtual '{self.name}' initialized (bus {self._bus_number})")
        return self._inner.init()

    def close(self) -> None:
        self._inner.close()
        self._log.info(f"RpiI2CVirtual '{self.name}' closed")

    def write_to(self, address: int, data: bytes) -> Task[()]:
        return self._inner.write_to(address, data)

    def read_from(self, address: int, count: int) -> Task[bytes]:
        return self._inner.read_from(address, count)

    def write_then_read(self, address: int, out_data: bytes, in_count: int) -> Task[bytes]:
        return self._inner.write_then_read(address, out_data, in_count)

    def scan(self) -> Task[list[int]]:
        return self._inner.scan()

    def add_device(self, address: int) -> I2CDeviceVirtual:
        """Register a virtual device for simulation (inject reads, observe writes)."""
        return self._inner.add_device(address)

    def get_device(self, address: int) -> I2CDeviceVirtual:
        return self._inner.get_device(address)


class RpiI2CVirtualDefinition(DriverDefinition):
    """Factory for RpiI2CVirtual from config args."""

    def __init__(self, logger: Logger):
        super().__init__(RpiI2CVirtual.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_optional("bus", ArgTypes.U8(), 1)
        return defn

    def create(self, args: DriverInitArgs) -> RpiI2CVirtual:
        return RpiI2CVirtual(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("bus"),
        )
