"""TCS34725 driver: RGB color sensor over I2C (register-level).

The TCS34725 is an RGB color sensor with IR blocking filter.
Typically placed behind a TCA9548A I2C mux channel, one sensor per finger.

Uses the I2C abstraction for all I2C operations, no Adafruit dependency.
"""

import logging
import struct
import threading
import time

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.interfaces.color_sensor import ColorSensor
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.color import Color

# Command bit must be OR'd with register address
_COMMAND_BIT = 0x80

# Register addresses
_ENABLE = 0x00
_ATIME = 0x01
_CONTROL = 0x0F
_ID = 0x12
_STATUS = 0x13
_CDATA = 0x14
_RDATA = 0x16
_GDATA = 0x18
_BDATA = 0x1A

# Enable register bits
_ENABLE_PON = 0x01  # Power on
_ENABLE_AEN = 0x02  # RGBC enable

# Status register bits
_STATUS_AVALID = 0x01  # RGBC data ready

# Gain values
_GAIN_1X = 0x00
_GAIN_4X = 0x01
_GAIN_16X = 0x02
_GAIN_60X = 0x03

# Default integration time: 2.4ms (0xFF), 24ms (0xF6), 101ms (0xD5), 154ms (0xC0), 700ms (0x00)
_ATIME_DEFAULT = 0xD5  # 101ms


class TCS34725(ColorSensor):
    """TCS34725 RGB color sensor via I2C.

    Receives an I2C which may be a TCA9548A mux channel.
    """

    def __init__(
        self,
        name: str,
        bus: I2C,
        address: int = 0x29,
        integration_time: int = _ATIME_DEFAULT,
        gain: int = _GAIN_4X,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._bus = bus
        self._address = address
        self._integration_time = integration_time
        self._gain = gain
        self._log = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._power_color: float = 1.0
        self._min_color: float = 0.0
        self._max_color: float = 65535.0

    def init(self) -> None:
        # Power on
        self._write_register(_ENABLE, _ENABLE_PON)
        time.sleep(0.003)  # 2.4ms power-on delay
        # Enable RGBC
        self._write_register(_ENABLE, _ENABLE_PON | _ENABLE_AEN)
        # Set integration time and gain
        self._write_register(_ATIME, self._integration_time)
        self._write_register(_CONTROL, self._gain)
        self._log.info(
            "TCS34725 '%s' initialized at 0x%02x",
            self.name,
            self._address,
        )

    def close(self) -> None:
        # Disable sensor
        self._write_register(_ENABLE, 0x00)
        self._log.info("TCS34725 '%s' closed", self.name)

    def read_color(self) -> Task[Color]:
        """Read RGBC values and return normalized Color (0.0-1.0)."""
        with self._lock:
            data = self._bus.write_then_read(self._address, bytes([_COMMAND_BIT | _CDATA]), 8)
        c, r, g, b = struct.unpack("<HHHH", data)
        # Normalize using clear channel as reference, or max_color
        divisor = max(c, 1)
        color = Color(
            r=min(1.0, r / divisor),
            g=min(1.0, g / divisor),
            b=min(1.0, b / divisor),
        )
        return ImmediateResultTask(color)

    def calibrate(self, power_color: float, min_color: float, max_color: float) -> None:
        self._power_color = power_color
        self._min_color = min_color
        self._max_color = max_color

    def _write_register(self, register: int, value: int) -> None:
        with self._lock:
            self._bus.write_to(self._address, bytes([_COMMAND_BIT | register, value]))

    def _read_register(self, register: int) -> int:
        with self._lock:
            data = self._bus.write_then_read(self._address, bytes([_COMMAND_BIT | register]), 1)
        return data[0]


class TCS34725Definition(DriverDefinition):
    """Factory for TCS34725 from config args."""

    def __init__(self, bus: I2C, logger: Logger):
        self._bus = bus
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_optional("address", ArgTypes.U8(), 0x29)
        defn.add_optional("integration_time", ArgTypes.U8(), _ATIME_DEFAULT)
        defn.add_optional("gain", ArgTypes.U8(), _GAIN_4X)
        return defn

    def create(self, args: DriverInitArgs) -> TCS34725:
        name = args.get("name")
        return TCS34725(
            name=name,
            bus=self._bus,
            address=args.get("address"),
            integration_time=args.get("integration_time"),
            gain=args.get("gain"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
