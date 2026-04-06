"""Serial driver: in-memory virtual implementation for testing and simulation."""

import threading

from evo_lib.interfaces.serial import Serial


class SerialVirtual(Serial):
    """In-memory serial bus for testing.

    Reads consume from an injectable buffer. Writes are recorded in a list
    for assertions. Thread-safe so it can be used with async reader threads.
    """

    def __init__(self, name: str = "virtual", timeout: float = 1.0):
        super().__init__(name)
        self._timeout = timeout
        self._lock = threading.Lock()
        self._read_buffer = bytearray()
        self._read_event = threading.Event()
        self.written: list[bytes] = []
        self._opened = False

    def init(self) -> None:
        self._opened = True

    def close(self) -> None:
        self._opened = False
        self._read_event.set()  # Unblock any waiting reads

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
