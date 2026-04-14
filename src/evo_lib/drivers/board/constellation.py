"""Constellation driver: passthrough board on the Hololutek robot.

Hardware (KiCad: carte-actionneurs branch Constellation-Hololutek-2026,
folder "Constellations actionneurs/Hololutek 2026 - {Repartiteur,Doigts}/"):
- 1x PCA9685PW: 16-channel PWM servo controller (servo outputs J1-J8)
- 1x TCA9548APWR: 8-channel I2C multiplexer (for color sensors on the
  Doigts sub-board)
- AX12 connectors (J12-J15) traverse the board passively to the parent
  AX12 daisy chain: no chip on the Constellation handles smart-servo
  traffic.
- No MCU, no firmware. The RPi I2C bus reaches both chips directly.

Three Constellations share the robot I2C bus on Hololutek (one per face of
the hexagonal frame). Address offsets are set by jumpers JP1-JP6 on PCA9685
and TCA9548A: base addresses 0x40 and 0x70 plus a per-face offset.
"""

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.drivers.board.base import BoardDriver
from evo_lib.drivers.i2c.tca9548a import TCA9548A, TCA9548AVirtual
from evo_lib.drivers.pwm.pca9685 import PCA9685Chip, PCA9685ChipVirtual
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry

_DEFAULT_PWM_ADDRESS = 0x40
_DEFAULT_MUX_ADDRESS = 0x70
_DEFAULT_SERVO_FREQ_HZ = 50.0


class Constellation(BoardDriver):
    """Constellation: PCA9685 servo controller + TCA9548A I2C multiplexer.

    Both chips share the same parent I2C bus, differentiated by addresses
    set via board jumpers. Helper accessors re-expose children for
    ergonomics (get_servo_channel, get_sensor_bus).
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        pwm_address: int = _DEFAULT_PWM_ADDRESS,
        mux_address: int = _DEFAULT_MUX_ADDRESS,
        servo_freq_hz: float = _DEFAULT_SERVO_FREQ_HZ,
    ):
        self._pwm = PCA9685Chip(
            name=f"{name}.pwm",
            logger=logger.get_sublogger(f"{name}.pwm"),
            bus=bus,
            address=pwm_address,
            freq_hz=servo_freq_hz,
        )
        self._mux = TCA9548A(
            name=f"{name}.mux",
            logger=logger.get_sublogger(f"{name}.mux"),
            parent_bus=bus,
            address=mux_address,
        )
        super().__init__(name, logger, children=[self._pwm, self._mux])

    @property
    def pwm(self) -> PCA9685Chip:
        return self._pwm

    @property
    def mux(self) -> TCA9548A:
        return self._mux


class ConstellationDefinition(DriverDefinition):
    """Factory for Constellation from config args. Parent bus resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("pwm_address", ArgTypes.U8(), _DEFAULT_PWM_ADDRESS)
        defn.add_optional("mux_address", ArgTypes.U8(), _DEFAULT_MUX_ADDRESS)
        defn.add_optional("servo_freq_hz", ArgTypes.F32(), _DEFAULT_SERVO_FREQ_HZ)
        return defn

    def create(self, args: DriverInitArgs) -> Constellation:
        name = args.get_name()
        return Constellation(
            name=name,
            logger=self._logger.get_sublogger(name),
            bus=args.get("bus"),
            pwm_address=args.get("pwm_address"),
            mux_address=args.get("mux_address"),
            servo_freq_hz=args.get("servo_freq_hz"),
        )


class ConstellationVirtual(BoardDriver):
    """Virtual drop-in twin of Constellation: virtual PWM + virtual mux.

    Same public interface as Constellation for transparent simulation swap.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: I2C,
        pwm_address: int = _DEFAULT_PWM_ADDRESS,
        mux_address: int = _DEFAULT_MUX_ADDRESS,
        servo_freq_hz: float = _DEFAULT_SERVO_FREQ_HZ,
    ):
        self._pwm = PCA9685ChipVirtual(
            name=f"{name}.pwm",
            logger=logger.get_sublogger(f"{name}.pwm"),
            bus=bus,
            address=pwm_address,
            freq_hz=servo_freq_hz,
        )
        self._mux = TCA9548AVirtual(
            name=f"{name}.mux",
            logger=logger.get_sublogger(f"{name}.mux"),
            parent_bus=bus,
            address=mux_address,
        )
        super().__init__(name, logger, children=[self._pwm, self._mux])

    @property
    def pwm(self) -> PCA9685ChipVirtual:
        return self._pwm

    @property
    def mux(self) -> TCA9548AVirtual:
        return self._mux


class ConstellationVirtualDefinition(DriverDefinition):
    """Factory for ConstellationVirtual from config args."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("pwm_address", ArgTypes.U8(), _DEFAULT_PWM_ADDRESS)
        defn.add_optional("mux_address", ArgTypes.U8(), _DEFAULT_MUX_ADDRESS)
        defn.add_optional("servo_freq_hz", ArgTypes.F32(), _DEFAULT_SERVO_FREQ_HZ)
        return defn

    def create(self, args: DriverInitArgs) -> ConstellationVirtual:
        name = args.get_name()
        return ConstellationVirtual(
            name=name,
            logger=self._logger.get_sublogger(name),
            bus=args.get("bus"),
            pwm_address=args.get("pwm_address"),
            mux_address=args.get("mux_address"),
            servo_freq_hz=args.get("servo_freq_hz"),
        )
