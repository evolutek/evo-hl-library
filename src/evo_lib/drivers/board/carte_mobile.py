"""Carte Mobile driver: passthrough board on the Evolutek PAL robot arm.

Hardware (KiCad: carte-actionneurs branch cartes-bras-pal-2026, folder
"Cartes PAL 2026/Carte Mobile/"):
- 1x MCP23017: 16-pin I2C GPIO expander
- 1x TCA9548APWR: 8-channel I2C multiplexer
- No MCU, no firmware: the RPi I2C bus traverses the card and addresses
  each chip directly via its own I2C address.
"""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.drivers.board.base import BoardDriver
from evo_lib.drivers.gpio.mcp23017 import MCP23017Chip
from evo_lib.drivers.gpio.virtual import GPIOChipVirtual
from evo_lib.drivers.i2c.tca9548a import TCA9548A, TCA9548AVirtual
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry


class CarteMobile(BoardDriver):
    """Carte Mobile: MCP23017 GPIO expander + TCA9548A I2C multiplexer.

    Both chips share the same parent I2C bus and are differentiated by
    their I2C addresses. Helper accessors re-expose children for ergonomics.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        gpio_address: int = 0x20,
        mux_address: int = 0x70,
    ):
        self._gpio = MCP23017Chip(
            name=f"{name}.gpio",
            bus=bus,
            address=gpio_address,
            logger=logger.get_sublogger(f"{name}.gpio").get_stdlib_logger(),
        )
        self._mux = TCA9548A(
            name=f"{name}.mux",
            logger=logger.get_sublogger(f"{name}.mux"),
            parent_bus=bus,
            address=mux_address,
        )
        super().__init__(name, logger, children=[self._gpio, self._mux])

    @property
    def gpio(self) -> MCP23017Chip:
        return self._gpio

    @property
    def mux(self) -> TCA9548A:
        return self._mux


class CarteMobileDefinition(DriverDefinition):
    """Factory for CarteMobile from config args. Parent bus resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("gpio_address", ArgTypes.U8(), 0x20)
        defn.add_optional("mux_address", ArgTypes.U8(), 0x70)
        return defn

    def create(self, args: DriverInitArgs) -> CarteMobile:
        name = args.get_name()
        return CarteMobile(
            name=name,
            logger=self._logger.get_sublogger(name),
            bus=args.get("bus"),
            gpio_address=args.get("gpio_address"),
            mux_address=args.get("mux_address"),
        )


class CarteMobileVirtual(BoardDriver):
    """Virtual drop-in twin of CarteMobile: substitutes each child with its
    virtual equivalent. Interface is identical so consumers swap transparently.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        gpio_address: int = 0x20,
        mux_address: int = 0x70,
    ):
        self._gpio = GPIOChipVirtual(
            name=f"{name}.gpio",
            logger=logger.get_sublogger(f"{name}.gpio"),
            address=gpio_address,
        )
        self._mux = TCA9548AVirtual(
            name=f"{name}.mux",
            logger=logger.get_sublogger(f"{name}.mux"),
            parent_bus=bus,
            address=mux_address,
        )
        super().__init__(name, logger, children=[self._gpio, self._mux])

    @property
    def gpio(self) -> GPIOChipVirtual:
        return self._gpio

    @property
    def mux(self) -> TCA9548AVirtual:
        return self._mux


class CarteMobileVirtualDefinition(DriverDefinition):
    """Factory for CarteMobileVirtual from config args."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("gpio_address", ArgTypes.U8(), 0x20)
        defn.add_optional("mux_address", ArgTypes.U8(), 0x70)
        return defn

    def create(self, args: DriverInitArgs) -> CarteMobileVirtual:
        name = args.get_name()
        return CarteMobileVirtual(
            name=name,
            logger=self._logger.get_sublogger(name),
            bus=args.get("bus"),
            gpio_address=args.get("gpio_address"),
            mux_address=args.get("mux_address"),
        )
