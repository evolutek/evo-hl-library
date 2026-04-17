from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition, DriverCommands
from evo_lib.drivers.board.base import BoardDriver
from evo_lib.interfaces.i2c import I2C
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral, Placable
from evo_lib.registry import Registry

import struct


class ElevatorBoard(BoardDriver):
    """Board made to control a elevator with a stepper.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        i2c: I2C,
        address: int
    ):
        super().__init__(name, logger, children=[])
        self._i2c = i2c
        self._address = address

    def send_command(self, cmd_id: int, stepper_id: int, data: bytes):
        self._i2c.write_to(self._address, bytes([cmd_id, stepper_id]) + data)


class ElevatorBoardStepper(Placable):
    commands = DriverCommands()

    def __init__(self, name: str, logger: Logger, board: ElevatorBoard, stepper_id: int):
        super().__init__(name)
        self._logger = logger
        self._board = board
        self._stepper_id = stepper_id

    @commands.register(args = [
        ArgTypes.I32("steps"),
        ArgTypes.I32("speed")
    ])
    def goto(self, steps: int, speed: int) -> bool:
        if speed < 0:
            return False
        if steps < -0x7FFFFFFF or steps > 0x7FFFFFFF:
            return False
        self._board.send_command(0x02, self._stepper_id, struct.pack(">iI", steps, speed))
        return True

    @commands.register(args = [
        ArgTypes.I32("steps"),
        ArgTypes.I32("speed")
    ])
    def move(self, steps: int, speed: int) -> bool:
        self._board.send_command(0x03, self._stepper_id, struct.pack(">iI", steps, speed))
        return True

    @commands.register(args = [
        ArgTypes.I32("speed")
    ])
    def home(self, speed: int) -> bool:
        self._board.send_command(0x01, self._stepper_id, struct.pack(">i", speed))
        return True


class ElevatorBoardDefinition(DriverDefinition):
    """Factory for CarteMobile from config args. Parent bus resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("i2c", ArgTypes.Component(I2C, self._peripherals))
        defn.add_optional("address", ArgTypes.U8(), 0x69)
        return defn

    def create(self, args: DriverInitArgs) -> ElevatorBoard:
        name = args.get_name()
        return ElevatorBoard(
            name = name,
            logger = self._logger.get_sublogger(name),
            i2c = args.get("i2c"),
            address = args.get("address")
        )


class ElevatorBoardStepperDefinition(DriverDefinition):
    """Factory for CarteMobile from config args. Parent bus resolved by name."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(ElevatorBoardStepper.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("board", ArgTypes.Component(ElevatorBoard, self._peripherals))
        defn.add_required("stepper_id", ArgTypes.U8())
        return defn

    def create(self, args: DriverInitArgs) -> ElevatorBoardStepper:
        name = args.get_name()
        return ElevatorBoardStepper(
            name = name,
            logger = self._logger.get_sublogger(name),
            board = args.get("board"),
            stepper_id = args.get("stepper_id")
        )


# class ElevatorBoardVirtual(BoardDriver):
#     """Virtual drop-in twin of CarteMobile: substitutes each child with its
#     virtual equivalent. Interface is identical so consumers swap transparently.
#     """

#     def __init__(
#         self,
#         name: str,
#         logger: Logger
#     ):
#         super().__init__(name, logger, children=[])

#     @property
#     def gpio(self) -> GPIOChipVirtual:
#         return self._gpio

#     @property
#     def mux(self) -> TCA9548AVirtual:
#         return self._mux


# class ElevatorBoardVirtualDefinition(ElevatorBoardDefinition):
#     """Factory for CarteMobileVirtual from config args."""

#     def create(self, args: DriverInitArgs) -> ElevatorBoardVirtual:
#         name = args.get_name()
#         return ElevatorBoardVirtual(
#             name=name,
#             logger=self._logger.get_sublogger(name)
#         )
