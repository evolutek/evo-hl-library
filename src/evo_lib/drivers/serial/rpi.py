"""Serial bus driver: real implementation via pyserial."""

import logging
import threading

from evo_lib.interfaces.serial import SerialBus

# Lazy-loaded in open() so this module can be imported without pyserial installed
_serial = None


class RpiSerialBus(SerialBus):
    """Real serial bus via pyserial.

    Wraps serial.Serial with a threading.Lock so that multiple threads
    sharing the same port block properly.
    """

    def __init__(
        self,
        port: str,
        baudrate: int = 38400,
        timeout: float = 1.0,
        logger: logging.Logger | None = None,
    ):
        self._port_path = port
        self._baudrate = baudrate
        self._timeout = timeout
        self._log = logger or logging.getLogger(__name__)
        self._serial = None
        self._lock = threading.Lock()

    def open(self) -> None:
        global _serial
        if _serial is None:
            import serial

            _serial = serial

        self._serial = _serial.Serial(
            port=self._port_path,
            baudrate=self._baudrate,
            timeout=self._timeout,
        )
        self._log.info(
            "Serial '%s' opened at %d baud",
            self._port_path,
            self._baudrate,
        )

    def close(self) -> None:
        if self._serial is not None:
            self._serial.close()
            self._log.info("Serial '%s' closed", self._port_path)
            self._serial = None

    def _require_open(self) -> None:
        if self._serial is None:
            raise RuntimeError("Serial port not opened, call open() first")

    def write(self, data: bytes) -> None:
        self._require_open()
        with self._lock:
            self._serial.write(data)

    def read(self, count: int) -> bytes:
        self._require_open()
        with self._lock:
            data = self._serial.read(count)
            if len(data) < count:
                raise TimeoutError(f"Serial read timeout: expected {count} bytes, got {len(data)}")
            return data

    def read_available(self) -> bytes:
        self._require_open()
        with self._lock:
            n = self._serial.in_waiting
            if n == 0:
                return b""
            return self._serial.read(n)

    def flush(self) -> None:
        self._require_open()
        with self._lock:
            self._serial.flush()

    @property
    def in_waiting(self) -> int:
        self._require_open()
        with self._lock:
            return self._serial.in_waiting
