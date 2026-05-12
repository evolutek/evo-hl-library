"""Serial driver: real implementation via pyserial."""

import threading
import time

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.drivers.serial.virtual import SerialVirtual
from evo_lib.interfaces.serial import DEFAULT_BAUDRATE, DEFAULT_TIMEOUT, Serial
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class RpiSerial(Serial):
    """Real serial bus via pyserial.

    Wraps serial.Serial with a threading.Lock so that multiple threads
    sharing the same port block properly.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        super().__init__(name)
        self._port_path = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._log = logger
        self._serial = None
        self._read_lock = threading.Lock()
        self._write_lock = threading.Lock()

    def init(self) -> Task[()]:
        # pyserial imported lazily so this module stays importable without it.
        # sys.modules caches the module, so repeated init() calls are free.
        import serial

        self._serial = serial.Serial(
            port=self._port_path,
            baudrate=self._baudrate,
            timeout=self._timeout,
        )
        self._log.info(
            f"RpiSerial '{self.name}' opened on {self._port_path} @ {self._baudrate} baud"
        )
        return ImmediateResultTask()

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._log.info(f"RpiSerial '{self.name}' closed")
            self._serial = None

    def _check_ready(self) -> None:
        if self._serial is None:
            raise RuntimeError("Serial port not opened, call init() first")

    def write_sync(self, data: bytes) -> None:
        self._check_ready()
        assert self._serial is not None
        with self._write_lock:
            self._serial.write(data)

    def read_exactly_sync(self, size: int, timeout: float | None = None) -> bytes:
        self._check_ready()
        assert self._serial is not None
        with self._read_lock:
            self._serial.timeout = timeout
            data = self._serial.read(size)
            if len(data) < size:
                raise TimeoutError(f"Serial read timeout: expected {size} bytes, got {len(data)}")
            return data

    def read_sync(self, max_size: int | None = None, timeout: float | None = None) -> bytes:
        self._check_ready()
        assert self._serial is not None

        if max_size is not None and max_size == 0:
            return b""

        start_time = time.time()
        with self._read_lock:
            # Wait at least one byte
            if self._serial.in_waiting == 0:
                if timeout is not None and timeout == 0:
                    return b""
                self._serial.timeout = timeout
                data = self._serial.read(1)
                if len(data) == 0:
                    return b""
            else:
                data = b""

            # Set read timeout with remaining time
            remaining_time = time.time() - start_time
            if timeout is not None:
                if timeout - remaining_time <= 0:
                    return b""
                self._serial.timeout = timeout - remaining_time
            else:
                self._serial.timeout = None

            # Read remaining bytes
            to_read = self._serial.in_waiting
            if max_size is not None:
                to_read = min(to_read, max_size - len(data))
            data += self._serial.read(to_read)

            return data

    def flush_sync(self) -> None:
        self._check_ready()
        with self._write_lock:
            self._serial.flush()

    def reset_input_buffer(self) -> None:
        self._check_ready()
        with self._read_lock:
            self._serial.reset_input_buffer()

    def set_baudrate(self, baudrate: int) -> None:
        self._check_ready()
        with self._read_lock:
            # pyserial reconfigures termios in-place on assignment.
            self._serial.baudrate = baudrate
            self._baudrate = baudrate
        self._log.info(f"RpiSerial '{self.name}' baudrate set to {baudrate}")

    @property
    def in_waiting(self) -> int:
        self._check_ready()
        with self._read_lock:
            return self._serial.in_waiting


class RpiSerialDefinition(DriverDefinition):
    """Factory for RpiSerial from config args."""

    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("port", ArgTypes.String())
        defn.add_optional("baudrate", ArgTypes.U32(), DEFAULT_BAUDRATE)
        defn.add_optional("timeout", ArgTypes.F32(), DEFAULT_TIMEOUT)
        return defn

    def create(self, args: DriverInitArgs) -> RpiSerial:
        return RpiSerial(
            name=args.get_name(),
            logger=self._logger,
            port=args.get("port"),
            baudrate=args.get("baudrate"),
            timeout=args.get("timeout"),
        )


class RpiSerialVirtual(Serial):
    """Virtual twin of RpiSerial: same constructor signature, pure in-memory.

    Delegates to SerialVirtual for all serial logic. Accepts the same
    arguments as RpiSerial so the factory can swap them transparently
    in config. Exposes inject_read() / written for simulation setups.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        port: str,
        baudrate: int = DEFAULT_BAUDRATE,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        super().__init__(name)
        self._log = logger
        self._port_path = port
        self._baudrate = baudrate
        self._inner = SerialVirtual(name, logger, timeout=timeout)

    def init(self) -> Task[()]:
        self._log.info(
            f"RpiSerialVirtual '{self.name}' initialized "
            f"(port={self._port_path}, baudrate={self._baudrate})"
        )
        return self._inner.init()

    def close(self) -> None:
        self._inner.close()

    def write_sync(self, data: bytes) -> None:
        self._inner.write_sync(data)

    def read_exactly_sync(self, size: int, timeout: float | None = None) -> bytes:
        return self._inner.read_exactly_sync(size, timeout)

    def read_sync(self, max_size: int | None = None, timeout: float | None = None) -> bytes:
        return self._inner.read_sync(max_size, timeout)

    def flush_sync(self) -> None:
        self._inner.flush()

    def reset_input_buffer(self) -> None:
        self._inner.reset_input_buffer()

    def set_baudrate(self, baudrate: int) -> None:
        self._baudrate = baudrate
        self._inner.set_baudrate(baudrate)

    @property
    def in_waiting(self) -> int:
        return self._inner.in_waiting

    # --- Simulation helpers ---

    @property
    def written(self) -> list[bytes]:
        return self._inner.written

    def inject_read(self, data: bytes) -> None:
        self._inner.inject_read(data)


class RpiSerialVirtualDefinition(DriverDefinition):
    """Factory for RpiSerialVirtual from config args."""

    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("port", ArgTypes.String())
        defn.add_optional("baudrate", ArgTypes.U32(), DEFAULT_BAUDRATE)
        defn.add_optional("timeout", ArgTypes.F32(), DEFAULT_TIMEOUT)
        return defn

    def create(self, args: DriverInitArgs) -> RpiSerialVirtual:
        return RpiSerialVirtual(
            name=args.get_name(),
            logger=self._logger,
            port=args.get("port"),
            baudrate=args.get("baudrate"),
            timeout=args.get("timeout"),
        )
