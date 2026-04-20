"""ADS1115 driver: 4-channel 16-bit ADC over I2C (register-level).

The ADS1115 is a precision ADC with programmable gain. This module exposes it as:
- ADS1115Chip (InterfaceHolder): manages I2C connection and gain config
- ADS1115Channel (AnalogInput): one instance per input channel (0-3)

Uses the I2C abstraction for all I2C operations, no Adafruit dependency.
"""

import struct
import threading
import time

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.analog_input import AnalogInput
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task

NUM_CHANNELS = 4

# Register addresses
_REG_CONVERSION = 0x00
_REG_CONFIG = 0x01

# Config register defaults
_OS_START = 1 << 15  # Start single-shot conversion
_MODE_SINGLE = 1 << 8  # Single-shot mode
_DR_128SPS = 0x04 << 5  # 128 samples per second
_COMP_DISABLE = 0x03  # Disable comparator (bits 1:0 = 11)

# MUX values for single-ended channels (bits 14:12)
_MUX_SINGLE = {
    0: 0x04 << 12,  # AIN0 vs GND
    1: 0x05 << 12,  # AIN1 vs GND
    2: 0x06 << 12,  # AIN2 vs GND
    3: 0x07 << 12,  # AIN3 vs GND
}

# PGA gain to full-scale range (volts)
_PGA_FSR = {
    6.144: 0x00 << 9,
    4.096: 0x01 << 9,
    2.048: 0x02 << 9,
    1.024: 0x03 << 9,
    0.512: 0x04 << 9,
    0.256: 0x05 << 9,
}

# 128 SPS data rate = 7.8ms per conversion, rounded up to 8ms
_CONVERSION_DELAY = 0.008


class ADS1115Channel(AnalogInput):
    """A single analog input channel on an ADS1115 chip."""

    def __init__(self, name: str, logger: Logger, chip: "ADS1115Chip", channel: int):
        super().__init__(name)
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        self._log = logger
        self._chip = chip
        self._channel = channel

    def init(self) -> Task[()]:
        return ImmediateResultTask()

    def close(self) -> None:
        pass

    def read_voltage(self) -> Task[float]:
        """Trigger a single-shot conversion and return the voltage."""
        raw = self._chip.read_channel_raw(self._channel)
        voltage = raw * self._chip.fsr / 32768.0
        return ImmediateResultTask(voltage)


class ADS1115Chip(InterfaceHolder):
    """Manages the I2C connection to one ADS1115 chip.

    Channels are numbered 0-3 (single-ended vs GND).
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        address: int = 0x48,
        fsr: float = 2.048,
    ):
        super().__init__(name)
        self._log = logger
        self._bus = bus
        self._address = address
        self._fsr = fsr
        self._pga_bits = _PGA_FSR.get(fsr, _PGA_FSR[2.048])
        self._lock = threading.Lock()
        self._channels: dict[int, ADS1115Channel] = {}

    @property
    def fsr(self) -> float:
        return self._fsr

    def init(self) -> Task[()]:
        self._log.info(
            f"ADS1115 '{self.name}' initialized at 0x{self._address:02x}, "
            f"FSR=±{self._fsr:.3f}V"
        )
        return ImmediateResultTask()

    def close(self) -> None:
        self._channels.clear()
        self._log.info(f"ADS1115 '{self.name}' closed")

    def get_subcomponents(self) -> list[Peripheral]:
        return list(self._channels.values())

    def get_channel(self, channel: int, name: str) -> ADS1115Channel:
        """Create or retrieve an ADS1115Channel for the given channel number."""
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        if channel in self._channels:
            return self._channels[channel]
        ch = ADS1115Channel(name, self._log, self, channel)
        self._channels[channel] = ch
        return ch

    def read_channel_raw(self, channel: int) -> int:
        """Trigger a single-shot conversion and return the raw signed 16-bit value."""
        config = (
            _OS_START
            | _MUX_SINGLE[channel]
            | self._pga_bits
            | _MODE_SINGLE
            | _DR_128SPS
            | _COMP_DISABLE
        )
        config_bytes = struct.pack(">H", config)
        with self._lock:
            self._bus.write_to(self._address, bytes([_REG_CONFIG]) + config_bytes).wait()
            time.sleep(_CONVERSION_DELAY)
            (data,) = self._bus.write_then_read(
                self._address, bytes([_REG_CONVERSION]), 2
            ).wait()
        return struct.unpack(">h", data)[0]


class ADS1115ChipDefinition(DriverDefinition):
    """Factory for ADS1115Chip from config args. Parent bus resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("address", ArgTypes.U8(), 0x48)
        defn.add_optional("fsr", ArgTypes.F32(), 2.048)
        return defn

    def create(self, args: DriverInitArgs) -> ADS1115Chip:
        return ADS1115Chip(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("bus"),
            address=args.get("address"),
            fsr=args.get("fsr"),
        )


class ADS1115ChannelDefinition(DriverDefinition):
    """Factory for an ADS1115Channel on a parent ADS1115Chip.

    The channel is created (or retrieved) via chip.get_channel(), so the
    chip remains the single source of truth for its 4 channels and will
    close them alongside its own close().
    """

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("chip", ArgTypes.Component(ADS1115Chip, self._peripherals))
        defn.add_required("channel", ArgTypes.U8(min_value=0, max_value=NUM_CHANNELS - 1))
        return defn

    def create(self, args: DriverInitArgs) -> ADS1115Channel:
        chip: ADS1115Chip = args.get("chip")
        return chip.get_channel(args.get("channel"), args.get_name())
