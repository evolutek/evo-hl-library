"""PCA9685 driver: 16-channel PWM controller over I2C.

The PCA9685 generates PWM signals at a configurable frequency (typically
50 Hz for servos). This module exposes it as:
- PCA9685Chip (ComponentHolder): manages I2C connection, frequency, prescaler
- PCA9685Channel (PWM): one instance per physical output channel
"""

import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.drivers.pwm.virtual import PWMChipVirtual, PWMVirtual
from evo_lib.interfaces.i2c import I2C
from evo_lib.interfaces.pwm import PWM
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task

NUM_CHANNELS = 16
_OSC_CLOCK_HZ = 25_000_000

# Register addresses
_MODE1 = 0x00
_PRESCALE = 0xFE
_LED0_ON_L = 0x06
_ALL_LED_ON_L = 0xFA  # broadcast registers: writing here affects all 16 channels

# MODE1 bits
_MODE1_SLEEP = 0x10  # bit 4
_MODE1_AI = 0x20  # bit 5: auto-increment
_MODE1_RESTART = 0x80  # bit 7

# Channel control bits (in ON_H / OFF_H)
_FULL_ON = 0x10  # bit 4 of ON_H
_FULL_OFF = 0x10  # bit 4 of OFF_H


class PCA9685Channel(PWM):
    """A single PWM output channel on a PCA9685 chip.

    Read-back commands (`get_duty_cycle`, `get_pulse_width_us`, `is_enabled`)
    report the last-commanded value, not a hardware measurement: the PCA9685
    output registers are technically readable but hold stale data on warm
    reset, so we memorize the value on write instead.
    """

    commands = DriverCommands(parents=[PWM.commands])

    def __init__(self, name: str, logger: Logger, chip: PCA9685Chip, channel: int):
        super().__init__(name)
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        self._log = logger
        self._chip = chip
        self._channel = channel
        self._base_reg = _LED0_ON_L + 4 * channel
        self._last_duty_cycle: float = 0.0
        self._last_pulse_width_us: float = 0.0

    def init(self) -> Task[()]:
        # Force the channel to full-off at init. PCA9685's RESTART bit
        # preserves previous duty cycles across a sleep/wake cycle, so
        # without this a servo could snap back to its pre-reset angle.
        self.free().wait()
        return ImmediateResultTask()

    def close(self) -> None:
        self.free().wait()

    def set_duty_cycle(self, duty: float) -> Task[()]:
        """Set duty cycle as a fraction (0.0 to 1.0)."""
        duty = max(0.0, min(1.0, duty))
        if duty == 0.0:
            # Full off: set bit 4 of OFF_H, clear ON
            self._chip.write_channel(self._base_reg, 0, 0, 0, _FULL_OFF)
        elif duty == 1.0:
            # Full on: set bit 4 of ON_H, clear OFF
            self._chip.write_channel(self._base_reg, 0, _FULL_ON, 0, 0)
        else:
            off_count = round(duty * 4096)
            self._chip.write_channel(
                self._base_reg, 0, 0, off_count & 0xFF, (off_count >> 8) & 0x0F
            )
        self._last_duty_cycle = duty
        self._last_pulse_width_us = duty * 1_000_000.0 / self._chip.freq_hz
        return ImmediateResultTask(None)

    def set_pulse_width_us(self, width_us: float) -> Task[()]:
        """Convert pulse width to duty cycle and apply."""
        period_us = 1_000_000.0 / self._chip.freq_hz
        duty = width_us / period_us
        return self.set_duty_cycle(duty)

    def free(self) -> Task[()]:
        """Disable this channel (full off)."""
        return self.set_duty_cycle(0.0)

    @commands.register(
        args=[],
        result=[("duty", ArgTypes.F32(help="Last commanded duty cycle (0.0 to 1.0)"))],
    )
    def get_duty_cycle(self) -> Task[float]:
        return ImmediateResultTask(self._last_duty_cycle)

    @commands.register(
        args=[],
        result=[("width_us", ArgTypes.F32(help="Last commanded pulse width in microseconds"))],
    )
    def get_pulse_width_us(self) -> Task[float]:
        return ImmediateResultTask(self._last_pulse_width_us)

    @commands.register(
        args=[],
        result=[("enabled", ArgTypes.Bool(help="True if a non-zero pulse is currently commanded"))],
    )
    def is_enabled(self) -> Task[bool]:
        return ImmediateResultTask(self._last_duty_cycle > 0.0)


class PCA9685Chip(InterfaceHolder):
    """Manages the I2C connection to one PCA9685 chip.

    Channels are numbered 0-15.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        address: int = 0x40,
        freq_hz: float = 50.0,
    ):
        super().__init__(name)
        self._bus = bus
        self._address = address
        self._freq_hz = freq_hz
        self._log = logger
        self._lock = threading.Lock()
        self._channels: dict[int, PCA9685Channel] = {}

    @property
    def freq_hz(self) -> float:
        return self._freq_hz

    def init(self) -> Task[()]:
        """Configure prescaler for the target frequency and start the chip."""
        # Enter sleep mode (required to change prescaler)
        mode1 = self._read_register(_MODE1)
        self._write_register(_MODE1, (mode1 | _MODE1_SLEEP) & ~_MODE1_RESTART)

        # Set prescaler
        prescale = round(_OSC_CLOCK_HZ / (4096 * self._freq_hz)) - 1
        prescale = max(3, min(255, prescale))
        self._write_register(_PRESCALE, prescale)

        # Wake up: clear sleep, set auto-increment
        mode1 = (mode1 | _MODE1_AI) & ~_MODE1_SLEEP
        self._write_register(_MODE1, mode1)

        # Force every channel to full-off BEFORE setting RESTART. On a warm
        # reset the output registers still hold the previous run's duty
        # cycles; RESTART would then resume them and snap connected servos
        # to stale positions. Writing to ALL_LED_{ON,OFF} is a broadcast
        # that clears all 16 channels in a single I2C transaction.
        with self._lock:
            self._bus.write_to(
                self._address,
                bytes([_ALL_LED_ON_L, 0, 0, 0, _FULL_OFF]),
            ).wait()

        # Restart (must be set after clearing sleep)
        self._write_register(_MODE1, mode1 | _MODE1_RESTART)

        self._log.info(
            f"PCA9685 '{self.name}' initialized at 0x{self._address:02x}, "
            f"freq={self._freq_hz:.1f} Hz, prescale={prescale}"
        )
        return ImmediateResultTask()

    def close(self) -> None:
        try:
            for ch in self._channels.values():
                ch.free().wait()
            mode1 = self._read_register(_MODE1)
            self._write_register(_MODE1, mode1 | _MODE1_SLEEP)
        except OSError:
            self._log.warning(f"PCA9685 '{self.name}': I2C error during close")
        self._channels.clear()
        self._log.info(f"PCA9685 '{self.name}' closed")

    def get_subcomponents(self) -> list[Peripheral]:
        """Return all channels that have been created via get_channel."""
        return list(self._channels.values())

    def get_channel(self, channel: int, name: str) -> PCA9685Channel:
        """Create or retrieve a PCA9685Channel for the given channel number."""
        if not 0 <= channel < NUM_CHANNELS:
            raise ValueError(f"Channel {channel} out of range (0-{NUM_CHANNELS - 1})")
        if channel in self._channels:
            return self._channels[channel]
        pwm_channel = PCA9685Channel(name, self._log, self, channel)
        self._channels[channel] = pwm_channel
        return pwm_channel

    def write_channel(self, base_reg: int, on_l: int, on_h: int, off_l: int, off_h: int) -> None:
        """Write the 4 channel registers using auto-increment."""
        with self._lock:
            self._bus.write_to(self._address, bytes([base_reg, on_l, on_h, off_l, off_h])).wait()

    def _read_register(self, register: int) -> int:
        with self._lock:
            (data,) = self._bus.write_then_read(self._address, bytes([register]), 1).wait()
        return data[0]

    def _write_register(self, register: int, value: int) -> None:
        with self._lock:
            self._bus.write_to(self._address, bytes([register, value])).wait()


class PCA9685ChipDefinition(DriverDefinition):
    """Factory for PCA9685Chip from config args. Parent bus resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("address", ArgTypes.U8(), 0x40)
        defn.add_optional("freq_hz", ArgTypes.F32(), 50.0)
        return defn

    def create(self, args: DriverInitArgs) -> PCA9685Chip:
        return PCA9685Chip(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("bus"),
            address=args.get("address"),
            freq_hz=args.get("freq_hz"),
        )


class PCA9685ChannelDefinition(DriverDefinition):
    """Factory for a PCA9685Channel on a parent PCA9685Chip.

    The channel is created (or retrieved) via chip.get_channel(), so the
    chip remains the single source of truth for its 16 channels and will
    free/close them during its own close().
    """

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(PCA9685Channel.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("chip", ArgTypes.Component(PCA9685Chip, self._peripherals))
        defn.add_required("channel", ArgTypes.U8(min_value=0, max_value=NUM_CHANNELS - 1))
        return defn

    def create(self, args: DriverInitArgs) -> PCA9685Channel:
        chip: PCA9685Chip = args.get("chip")
        return chip.get_channel(args.get("channel"), args.get_name())


class PCA9685ChipVirtual(PWMChipVirtual):
    """Virtual twin of PCA9685Chip: same constructor signature, in-memory.

    Delegates all PWM logic to PWMChipVirtual. Accepts bus and address for
    drop-in config compatibility with PCA9685Chip, but ignores them (the
    virtual has no real I2C transport).
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        address: int = 0x40,
        freq_hz: float = 50.0,
    ):
        super().__init__(name, logger, freq_hz)
        self._bus = bus
        self._address = address

    def init(self) -> Task[()]:
        self._log.info(
            f"PCA9685ChipVirtual '{self.name}' initialized at 0x{self._address:02x}, "
            f"freq={self._freq_hz:.1f} Hz"
        )
        return super().init()


class PCA9685ChipVirtualDefinition(DriverDefinition):
    """Factory for PCA9685ChipVirtual. Parent bus resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("address", ArgTypes.U8(), 0x40)
        defn.add_optional("freq_hz", ArgTypes.F32(), 50.0)
        return defn

    def create(self, args: DriverInitArgs) -> PCA9685ChipVirtual:
        return PCA9685ChipVirtual(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("bus"),
            address=args.get("address"),
            freq_hz=args.get("freq_hz"),
        )


class PCA9685ChannelVirtualDefinition(DriverDefinition):
    """Factory for a virtual PCA9685 channel on a PCA9685ChipVirtual.

    Mirrors PCA9685ChannelDefinition: resolves the chip by name, delegates
    channel creation to chip.get_channel() which returns a PWMVirtual (the
    standard virtual drop-in for a PWM channel, with read-back commands).
    """

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(PWMVirtual.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("chip", ArgTypes.Component(PCA9685ChipVirtual, self._peripherals))
        defn.add_required("channel", ArgTypes.U8(min_value=0, max_value=NUM_CHANNELS - 1))
        return defn

    def create(self, args: DriverInitArgs) -> PWMVirtual:
        chip: PCA9685ChipVirtual = args.get("chip")
        return chip.get_channel(args.get("channel"), args.get_name())
