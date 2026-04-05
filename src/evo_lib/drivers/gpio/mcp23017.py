"""MCP23017 driver: register-level I2C implementation.

The MCP23017 is a 16-pin I2C GPIO expander. This module exposes it as:
- MCP23017Chip (ComponentHolder): manages I2C connection to the chip
- MCP23017Pin (GPIO): one instance per physical pin

Uses the I2CBus abstraction for all I2C operations, enabling both real
hardware access and virtual bus testing without any Adafruit dependency.
"""

import logging
import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.component import Component, ComponentHolder
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.event import Event
from evo_lib.interfaces.gpio import GPIO, GPIODirection, GPIOEdge
from evo_lib.interfaces.i2c import I2CBus
from evo_lib.logger import Logger
from evo_lib.task import ImmediateErrorTask, ImmediateResultTask, Task

NUM_PINS = 16

# MCP23017 register addresses (BANK=0, default)
_IODIR_A = 0x00
_IODIR_B = 0x01
_GPIO_A = 0x12
_GPIO_B = 0x13
_GPPU_A = 0x0C
_GPPU_B = 0x0D
_OLAT_A = 0x14
_OLAT_B = 0x15


def _port_regs(pin: int) -> tuple[int, int, int, int, int]:
    """Return (iodir_reg, gpio_reg, gppu_reg, olat_reg, bit) for a pin number."""
    if pin < 8:
        return _IODIR_A, _GPIO_A, _GPPU_A, _OLAT_A, pin
    return _IODIR_B, _GPIO_B, _GPPU_B, _OLAT_B, pin - 8


class MCP23017Pin(GPIO):
    """A single pin on an MCP23017 chip, implementing the GPIO interface."""

    def __init__(
        self,
        name: str,
        chip: "MCP23017Chip",
        pin: int,
        direction: GPIODirection = GPIODirection.INPUT,
        pull_up: bool = False,
    ):
        super().__init__(name)
        if not 0 <= pin < NUM_PINS:
            raise ValueError(f"Pin {pin} out of range (0-{NUM_PINS - 1})")
        self._chip = chip
        self._pin_number = pin
        self._direction = direction
        self._pull_up = pull_up
        self._log = chip._log
        self._iodir_reg, self._gpio_reg, self._gppu_reg, self._olat_reg, self._bit = _port_regs(pin)

    def init(self) -> None:
        if self._direction == GPIODirection.INPUT:
            self._chip.set_bit(self._iodir_reg, self._bit, True)
            self._chip.set_bit(self._gppu_reg, self._bit, self._pull_up)
        else:
            self._chip.set_bit(self._iodir_reg, self._bit, False)
            self._chip.set_bit(self._olat_reg, self._bit, False)
        self._log.debug(
            "MCP23017 pin %d (%s, %s) initialized",
            self._pin_number,
            self.name,
            self._direction.value,
        )

    def close(self) -> None:
        pass

    def read(self) -> Task[bool]:
        """Read the pin state via the chip's I2C connection."""
        if self._direction != GPIODirection.INPUT:
            return ImmediateErrorTask(NotImplementedError("read() requires INPUT direction"))
        val = self._chip.read_register(self._gpio_reg)
        return ImmediateResultTask(bool(val & (1 << self._bit)))

    def write(self, state: bool) -> Task[None]:
        """Set the pin output state via the chip's I2C connection."""
        if self._direction != GPIODirection.OUTPUT:
            return ImmediateErrorTask(NotImplementedError("write() requires OUTPUT direction"))
        self._chip.set_bit(self._olat_reg, self._bit, state)
        return ImmediateResultTask(None)

    def interrupt(self, edge: GPIOEdge = GPIOEdge.BOTH) -> Event[bool]:
        """Not yet supported on MCP23017."""
        raise NotImplementedError("MCP23017 interrupt is not yet supported")


class MCP23017Chip(ComponentHolder):
    """Manages the I2C connection to one MCP23017 chip.

    Pins are numbered 0-15 (GPA0-GPA7 = 0-7, GPB0-GPB7 = 8-15).
    """

    def __init__(
        self,
        name: str,
        bus: I2CBus,
        address: int = 0x20,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._bus = bus
        self._address = address
        self._log = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._pins: dict[int, MCP23017Pin] = {}

    def init(self) -> None:
        """Initialize the MCP23017: set all pins as inputs (default state)."""
        self.write_register(_IODIR_A, 0xFF)
        self.write_register(_IODIR_B, 0xFF)
        self._log.info(
            "MCP23017 '%s' initialized at 0x%02x",
            self.name,
            self._address,
        )

    def close(self) -> None:
        self._pins.clear()
        self._log.info("MCP23017 '%s' closed", self.name)

    def get_subcomponents(self) -> list[Component]:
        """Return all pins that have been created via get_pin."""
        return list(self._pins.values())

    def get_pin(
        self,
        pin: int,
        name: str,
        direction: GPIODirection = GPIODirection.INPUT,
        pull_up: bool = False,
    ) -> MCP23017Pin:
        """Create or retrieve a MCP23017Pin for the given pin number."""
        if not 0 <= pin < NUM_PINS:
            raise ValueError(f"Pin {pin} out of range (0-{NUM_PINS - 1})")
        if pin in self._pins:
            return self._pins[pin]
        gpio_pin = MCP23017Pin(name, self, pin, direction, pull_up)
        self._pins[pin] = gpio_pin
        return gpio_pin

    def read_register(self, register: int) -> int:
        """Read a single byte from a MCP23017 register."""
        with self._lock:
            data = self._bus.write_then_read(self._address, bytes([register]), 1)
        return data[0]

    def write_register(self, register: int, value: int) -> None:
        """Write a single byte to a MCP23017 register."""
        with self._lock:
            self._bus.write_to(self._address, bytes([register, value]))

    def set_bit(self, register: int, bit: int, value: bool) -> None:
        """Read-modify-write a single bit in a register (atomic)."""
        with self._lock:
            current = self._bus.write_then_read(self._address, bytes([register]), 1)[0]
            if value:
                current |= 1 << bit
            else:
                current &= ~(1 << bit)
            self._bus.write_to(self._address, bytes([register, current]))


class MCP23017ChipDefinition(DriverDefinition):
    """Factory for MCP23017Chip from config args.

    The I2C bus and logger are construction-time dependencies (not config args),
    because buses and logging are infrastructure managed by the ComponentsManager.
    """

    def __init__(self, bus: I2CBus, logger: Logger):
        self._bus = bus
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        defn.add_optional("address", ArgTypes.U8(), 0x20)
        return defn

    def create(self, args: DriverInitArgs) -> MCP23017Chip:
        name = args.get("name")
        return MCP23017Chip(
            name=name,
            bus=self._bus,
            address=args.get("address"),
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
