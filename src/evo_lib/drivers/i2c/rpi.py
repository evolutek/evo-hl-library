"""I2C driver: real Raspberry Pi implementation via Adafruit Blinka."""

import logging
import threading

from evo_lib.interfaces.i2c import I2C

log = logging.getLogger(__name__)


class RpiI2C(I2C):
    """Real I2C bus on a Raspberry Pi (or any Blinka-supported SBC).

    Wraps busio.I2C with the board's default SCL/SDA pins for the given
    bus number. Hardware libraries are lazily imported in init() so that
    this module can be imported on dev machines without Blinka installed.

    All operations are serialized with a threading.Lock so that multiple
    threads sharing the same bus block properly instead of spin-waiting.
    """

    def __init__(self, name: str, bus: int = 1):
        super().__init__(name)
        self._bus_number = bus
        self._i2c = None
        self._lock = threading.Lock()

    def init(self) -> None:
        """Open the I2C bus. Must be called before any read/write."""
        import busio

        scl, sda = self._get_i2c_pins(self._bus_number)
        self._i2c = busio.I2C(scl, sda)
        log.info("I2C bus %d opened", self._bus_number)

    def close(self) -> None:
        """Release the I2C bus."""
        if self._i2c is not None:
            self._i2c.deinit()
            self._i2c = None
            log.info("I2C bus %d closed", self._bus_number)

    def _check_ready(self) -> None:
        if self._i2c is None:
            raise RuntimeError("I2C bus not opened, call init() first")

    def write_to(self, address: int, data: bytes) -> None:
        self._check_ready()
        with self._lock:
            self._i2c.writeto(address, data)

    def read_from(self, address: int, count: int) -> bytes:
        self._check_ready()
        buf = bytearray(count)
        with self._lock:
            self._i2c.readfrom_into(address, buf)
        return bytes(buf)

    def write_then_read(
        self, address: int, out_data: bytes, in_count: int
    ) -> bytes:
        self._check_ready()
        buf = bytearray(in_count)
        with self._lock:
            self._i2c.writeto_then_readfrom(address, out_data, buf)
        return bytes(buf)

    def scan(self) -> list[int]:
        self._check_ready()
        with self._lock:
            return self._i2c.scan()

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
        raise ValueError(
            f"I2C bus {bus} not supported: board has no {scl_attr}/{sda_attr} pins"
        )
