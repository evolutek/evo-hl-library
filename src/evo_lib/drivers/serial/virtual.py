"""Serial driver: in-memory virtual implementation for testing and simulation."""

import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.serial import DEFAULT_BAUDRATE, DEFAULT_TIMEOUT, Serial
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task


class SerialVirtual(Serial):
    """In-memory serial bus for testing.

    Reads consume from an injectable buffer. Writes are recorded in a list
    for assertions. Thread-safe so it can be used with async reader threads.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        super().__init__(name)
        self._log = logger
        self._timeout = timeout
        self._baudrate = DEFAULT_BAUDRATE
        self._lock = threading.Lock()
        self._read_buffer = bytearray()
        self._read_event = threading.Event()
        self.written: list[bytes] = []
        self._opened = False

    def init(self) -> Task[()]:
        self._opened = True
        self._log.info(f"SerialVirtual '{self.name}' opened")
        return ImmediateResultTask()

    def close(self) -> None:
        self._opened = False
        self._read_event.set()  # Unblock any waiting reads
        self._log.info(f"SerialVirtual '{self.name}' closed")

    def _check_ready(self) -> None:
        if not self._opened:
            raise RuntimeError("Virtual serial not opened, call init() first")

    def write(self, data: bytes) -> None:
        self._check_ready()
        with self._lock:
            self.written.append(bytes(data))

    def read(self, count: int) -> bytes:
        self._check_ready()
        # Wait until enough bytes are available
        while True:
            with self._lock:
                if len(self._read_buffer) >= count:
                    result = bytes(self._read_buffer[:count])
                    del self._read_buffer[:count]
                    return result
                self._read_event.clear()
            if not self._read_event.wait(timeout=self._timeout):
                with self._lock:
                    available = len(self._read_buffer)
                raise TimeoutError(
                    f"Virtual serial read timeout: expected {count} bytes, got {available}"
                )

    def read_available(self) -> bytes:
        self._check_ready()
        with self._lock:
            data = bytes(self._read_buffer)
            self._read_buffer.clear()
            return data

    def flush(self) -> None:
        self._check_ready()

    def reset_input_buffer(self) -> None:
        self._check_ready()
        with self._lock:
            self._read_buffer.clear()
            # Drop any pending wake-up: a concurrent reader must re-wait
            # instead of consuming an empty buffer and timing out.
            self._read_event.clear()

    def set_baudrate(self, baudrate: int) -> None:
        self._check_ready()
        # No hardware to reconfigure; record the value for assertions.
        self._baudrate = baudrate
        self._log.info(f"SerialVirtual '{self.name}' baudrate set to {baudrate}")

    @property
    def in_waiting(self) -> int:
        self._check_ready()
        with self._lock:
            return len(self._read_buffer)

    # --- Test helpers ---

    def inject_read(self, data: bytes) -> None:
        """Queue bytes that will be returned by the next read call."""
        with self._lock:
            self._read_buffer.extend(data)
        self._read_event.set()


class SerialVirtualDefinition(DriverDefinition):
    """Factory for SerialVirtual from config args."""

    def __init__(self, logger: Logger):
        super().__init__()
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_optional("timeout", ArgTypes.F32(), DEFAULT_TIMEOUT)
        return defn

    def create(self, args: DriverInitArgs) -> SerialVirtual:
        return SerialVirtual(
            name=args.get_name(),
            logger=self._logger,
            timeout=args.get("timeout"),
        )
