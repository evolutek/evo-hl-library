import struct

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.registry import Registry
from evo_lib.peripheral import Peripheral
from evo_lib.drivers.board.base import BoardDriver
from evo_lib.interfaces.can import CAN, CANMessage
from evo_lib.interfaces.obstacles_provider import Event, Obstacle, ObstacleProvider
from evo_lib.logger import Logger
from evo_lib.task import Task
from evo_lib.types.vect import Vect2D
from evo_lib.interfaces.can import CAN


class LocalisationBoard(BoardDriver, ObstacleProvider):
    def __init__(self, name: str, logger: Logger, can: CAN) -> None:
        super().__init__(name, logger, [])
        self._can = can
        self._on_obstacles = Event[list[Obstacle]]()
        self._obstacles: dict[int, list[Obstacle]] = {}

    def _update_obstacles(self) -> None:
        all_obstacles: list[Obstacle] = []
        for group, obstacles in self._obstacles.items():
            all_obstacles.extend(obstacles)
        self._on_obstacles.trigger(all_obstacles)

    def _handle_message(self, message: CANMessage) -> None:
        if message.heading == 0x400:
            (group, x, y) = struct.unpack("<Hhh", message.data)
            x /= 4
            y /= 4
            #self._log.info(f"Received obstacle: group: {group}, x: {x}, y: {y}")
            if group not in self._obstacles:
                self._obstacles[group] = []
            self._obstacles[group].append(Obstacle(Vect2D(x, y)))

        elif message.heading == 0x401:
            (group,) = struct.unpack("<H", message.data)
            #self._log.info(f"Received end of obstacles group: {group}")
            self._update_obstacles()
            self._obstacles[group] = []

    def init(self) -> Task[()]:
        self._can.read_async().register(self._handle_message)
        return super().init()

    def on_obstacles(self) -> Event[list[Obstacle]]:
        return self._on_obstacles


class LocalisationBoardDefinition(DriverDefinition):
    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]) -> None:
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        args = DriverInitArgsDefinition()
        args.add_required("can", ArgTypes.Component(CAN, self._peripherals))
        return args

    def create(self, args: DriverInitArgs) -> BoardDriver:
        return LocalisationBoard(
            name = args.get_name(),
            logger = self._logger,
            can = args.get("can")
        )
