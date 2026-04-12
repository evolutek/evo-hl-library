"""I2C driver: real Raspberry Pi implementation via Adafruit Blinka."""

import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.drivers.i2c.virtual import I2CDeviceVirtual, I2CVirtual
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class RpiI2C(I2C):
    """Real I2C bus on a Raspberry Pi (or any Blinka-supported SBC).

    Wraps busio.I2C with the board's default SCL/SDA pins for the given
    bus number. Hardware libraries are lazily imported in init() so that
    this module can be imported on dev machines without Blinka installed.

    All operations are serialized with a threading.Lock so that multiple
    threads sharing the same bus block properly instead of spin-waiting.
    Each I/O returns an ImmediateResultTask wrapping the synchronous busio
    call, matching the library-wide Task-returning driver contract.
    """

    def __init__(self, name: str, logger: Logger, bus: int = 1):
        super().__init__(name)
        self._log = logger
        self._bus_number = bus
        self._i2c = None
        self._lock = threading.Lock()

    def init(self) -> Task[()]:
        """Open the I2C bus. Must be called before any read/write."""
        import busio

        scl, sda = self._get_i2c_pins(self._bus_number)
        self._i2c = busio.I2C(scl, sda)
        self._log.info(f"I2C bus {self._bus_number} opened")
        return ImmediateResultTask()

    def close(self) -> None:
        """Release the I2C bus."""
        if self._i2c is not None:
            self._i2c.deinit()
            self._i2c = None
            self._log.info(f"I2C bus {self._bus_number} closed")

    def _check_ready(self) -> None:
        if self._i2c is None:
            raise RuntimeError("I2C bus not opened, call init() first")

    def write_to(self, address: int, data: bytes) -> Task[None]:
        self._check_ready()
        with self._lock:
            self._i2c.writeto(address, data)
        return ImmediateResultTask(None)

    def read_from(self, address: int, count: int) -> Task[bytes]:
        self._check_ready()
        buf = bytearray(count)
        with self._lock:
            self._i2c.readfrom_into(address, buf)
        return ImmediateResultTask(bytes(buf))

    def write_then_read(self, address: int, out_data: bytes, in_count: int) -> Task[bytes]:
        self._check_ready()
        buf = bytearray(in_count)
        with self._lock:
            self._i2c.writeto_then_readfrom(address, out_data, buf)
        return ImmediateResultTask(bytes(buf))

    def scan(self) -> Task[list[int]]:
        self._check_ready()
        with self._lock:
            return ImmediateResultTask(self._i2c.scan())

    @staticmethod
    def _get_i2c_pins(bus: int) -> tuple:
        """Return (SCL, SDA) board pins for the given I2C bus number."""
        import board

        if bus == 1:
            return board.SCL, board.SDA
        scl_attr = f"SCL{bus}"
        sda_attr = f"SDA{bus}"
        if hasattr(board, scl_attr) and hasattr(board, sda_attr):
            return getattr(board, scl_attr), getattr(board, sda_attr)
        raise ValueError(f"I2C bus {bus} not supported: board has no {scl_attr}/{sda_attr} pins")


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

    def write_to(self, address: int, data: bytes) -> Task[None]:
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
