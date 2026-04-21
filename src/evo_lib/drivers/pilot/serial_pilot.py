"""Pilot driver: DifferentialPilot over carte-asserv serial binary protocol.

Implements the legacy trajectory manager protocol: binary packets over UART,
with asynchronous ACKNOWLEDGE/MOVE_BEGIN/MOVE_END events from the board.
"""

import math
import struct
import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.drivers.pilot.protocol import (
    NO_ACK_COMMANDS,
    RESPONSE_FORMATS,
    Commands,
    Errors,
    build_packet,
)
from evo_lib.drivers.pilot.virtual import HolonomicPilotVirtual, DifferentialPilotVirtual
from evo_lib.event import Event
from evo_lib.interfaces.pilot import (
    DifferentialPilot,
    DifferentialPilotWaypoint,
    HolonomicPilot,
    HolonomicPilotWaypoint,
    PilotMoveStatus,
)
from evo_lib.interfaces.serial import Serial
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry
from evo_lib.task import DelayedTask, ImmediateResultTask, Task
from evo_lib.types.pose import Pose2D
from evo_lib.types.vect import Vect2D

_ACK_TIMEOUT = 1.0
_RESPONSE_TIMEOUT = 1.0


class DifferentialSerialPilot(DifferentialPilot):
    """Trajectory manager communicating with carte-asserv via serial binary protocol."""

    commands = DriverCommands([DifferentialPilot.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        bus: Serial,
    ):
        super().__init__(name)
        self._bus = bus
        self._log = logger
        self._lock = threading.Lock()
        self._ack_event = threading.Event()
        self._move_task: DelayedTask[PilotMoveStatus] | None = None
        self._reader_thread: threading.Thread | None = None
        self._running = False
        self._last_position: Pose2D = Pose2D()
        self._last_speed: float = 0
        self._last_velocity: Vect2D = Vect2D(0, 0)
        self._moving = False
        self._rx_buffer = bytearray()
        self._response_event = threading.Event()
        self._response_data: tuple = ()
        self._pose_or_velocity_update_event: Event[Pose2D, Vect2D] = Event()

    def init(self) -> Task[()]:
        self._running = True
        self._reader_thread = threading.Thread(target=self._reader_loop)
        self._reader_thread.start()
        # Send init packet
        # with self._lock:
        #     self._bus.write(INIT_PACKET)
        self._log.info(f"DifferentialSerialPilot '{self.name}' initialized")
        return ImmediateResultTask()

    def close(self) -> None:
        self._running = False
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            if self._reader_thread.is_alive():
                self._log.error(f"Failed to stop serial pilot '{self.name}' reader thread")
            self._reader_thread = None
        self._log.info(f"DifferentialSerialPilot '{self.name}' closed", self.name)

    # Movement commands

    def go_to(self, x: float, y: float) -> Task[PilotMoveStatus]:
        return self._send_move(Commands.GOTO_XY, x, y)

    def go_to_then_head_to(self, x: float, y: float, heading: float) -> Task[PilotMoveStatus]:
        raise NotImplementedError("go_to_then_head_to not implemented yet")

    def go_to_then_rotate(self, x: float, y: float, angle: float) -> Task[PilotMoveStatus]:
        raise NotImplementedError("go_to_then_rotate not implemented yet")

    def go_to_then_look_at(
        self, x: float, y: float, look_x: float, look_y: float
    ) -> Task[PilotMoveStatus]:
        raise NotImplementedError("go_to_then_look_at not implemented yet")

    def forward(self, distance: float) -> Task[PilotMoveStatus]:
        target = self._last_position + Pose2D.from_polar(distance, self._last_position.heading)
        return self.go_to(target.x, target.y)

    def head_to(self, heading: float) -> Task[PilotMoveStatus]:
        return self._send_move(Commands.GOTO_THETA, heading)

    def look_at(self, x: float, y: float) -> Task[PilotMoveStatus]:
        dx = x - self._last_position[0]
        dy = y - self._last_position[1]
        heading = math.atan2(dy, dx)
        return self.head_to(heading)

    def rotate(self, angle: float) -> Task[PilotMoveStatus]:
        target = self._last_position.heading + angle
        return self.head_to(target)

    def follow_path(self, waypoints: list[DifferentialPilotWaypoint]) -> Task[PilotMoveStatus]:
        raise NotImplementedError("follow_path not implemented yet")

    def stop(self) -> Task[()]:
        self._send_command(Commands.STOP_ASAP, 0.0, 0.0)
        if self._move_task is not None:
            self._move_task.complete(PilotMoveStatus.CANCELLED)
            self._move_task = None
        return ImmediateResultTask()

    def free(self) -> Task[()]:
        self._send_command(Commands.FREE)
        return ImmediateResultTask()

    def unfree(self) -> Task[()]:
        """Re-enable motors after a free() call."""
        self._send_command(Commands.UNFREE)
        return ImmediateResultTask()

    def on_pose_or_velocity_update(self) -> Event[Pose2D, Vect2D]:
        return self._pose_or_velocity_update_event

    def get_velocity(self) -> Task[Vect2D]:
        pass

    def get_pose(self) -> Task[Pose2D]:
        """Return the last known position from telemetry (x, y, theta)."""
        return ImmediateResultTask(self._last_position)

    def get_pose_and_velocity(self) -> Task[Pose2D, Vect2D]:
        """Return the last known position from telemetry (x, y, theta)."""
        return ImmediateResultTask(self._last_position, self._last_velocity)

    def set_pose(self, pose: Pose2D) -> Task[()]:
        """Set the robot's absolute position on the board."""
        self._send_command(Commands.SET_X, pose.x).wait()
        self._send_command(Commands.SET_Y, pose.y).wait()
        self._send_command(Commands.SET_THETA, pose.heading).wait()
        self._last_position = pose.copy()
        return ImmediateResultTask()

    # SerialPilot specific commands

    @commands.register(
        args=[
            ("p", ArgTypes.F32()),
            ("i", ArgTypes.F32()),
            ("d", ArgTypes.F32()),
        ],
        result=[],
    )
    def set_pid_trsl(self, p: float, i: float, d: float) -> Task[()]:
        return self._send_command(Commands.SET_PID_TRSL, p, i, d)

    @commands.register(
        args=[
            ("p", ArgTypes.F32()),
            ("i", ArgTypes.F32()),
            ("d", ArgTypes.F32()),
        ],
        result=[],
    )
    def set_pid_rot(self, p: float, i: float, d: float) -> Task[()]:
        return self._send_command(Commands.SET_PID_ROT, p, i, d)

    @commands.register(
        args=[
            ("trsl_acc", ArgTypes.F32()),
            ("trsl_dec", ArgTypes.F32()),
            ("trsl_max", ArgTypes.F32()),
            ("rot_acc", ArgTypes.F32()),
            ("rot_dec", ArgTypes.F32()),
            ("rot_max", ArgTypes.F32()),
        ],
        result=[],
    )
    def set_speeds(
        self,
        trsl_acc: float,
        trsl_dec: float,
        trsl_max: float,
        rot_acc: float,
        rot_dec: float,
        rot_max: float,
    ) -> Task[()]:
        self._send_command(Commands.SET_TRSL_ACC, trsl_acc).wait()
        self._send_command(Commands.SET_TRSL_DEC, trsl_dec).wait()
        self._send_command(Commands.SET_TRSL_MAXSPEED, trsl_max).wait()
        self._send_command(Commands.SET_ROT_ACC, rot_acc).wait()
        self._send_command(Commands.SET_ROT_DEC, rot_dec).wait()
        self._send_command(Commands.SET_ROT_MAXSPEED, rot_max).wait()
        return ImmediateResultTask()

    @commands.register(
        args=[
            ("diam_left", ArgTypes.F32()),
            ("diam_right", ArgTypes.F32()),
            ("spacing", ArgTypes.F32()),
        ],
        result=[],
    )
    def set_wheels(self, diam_left: float, diam_right: float, spacing: float) -> Task[()]:
        self._send_command(Commands.SET_WHEELS_DIAM, diam_left, diam_right).wait()
        self._send_command(Commands.SET_WHEELS_SPACING, spacing).wait()
        return ImmediateResultTask()

    @commands.register(
        args=[
            ("trsl", ArgTypes.F32()),
            ("rot", ArgTypes.F32()),
        ],
        result=[],
    )
    def set_delta_max(self, trsl: float, rot: float) -> Task[()]:
        """Set max error tolerances for translation (mm) and rotation (rad)."""
        self._send_command(Commands.SET_DELTA_MAX_TRSL, trsl).wait()
        self._send_command(Commands.SET_DELTA_MAX_ROT, rot).wait()
        return ImmediateResultTask()

    @commands.register(
        args=[
            ("size_x", ArgTypes.F32()),
            ("size_y", ArgTypes.F32()),
        ],
        result=[],
    )
    def set_robot_size(self, size_x: float, size_y: float) -> Task[()]:
        """Set robot dimensions for recalibration (mm)."""
        self._send_command(Commands.SET_ROBOT_SIZE_X, size_x).wait()
        self._send_command(Commands.SET_ROBOT_SIZE_Y, size_y).wait()
        return ImmediateResultTask()

    @commands.register(
        args=[
            ("left", ArgTypes.F32()),
            ("right", ArgTypes.F32()),
        ],
        result=[],
    )
    def set_pwm(self, left: float, right: float) -> Task[()]:
        """Direct PWM control (for debugging/calibration only)."""
        self._send_command(Commands.SET_PWM, left, right).wait()
        return ImmediateResultTask()

    @commands.register(
        args=[("interval_ms", ArgTypes.I32())],
        result=[],
    )
    def set_telemetry(self, interval_ms: int) -> Task[()]:
        """Set telemetry send interval in milliseconds."""
        self._send_command(Commands.SET_TELEMETRY, interval_ms).wait()
        return ImmediateResultTask()

    @commands.register(
        args=[
            ("direction", ArgTypes.U8()),
            ("offset", ArgTypes.F32()),
            ("set_position", ArgTypes.U8()),
        ],
        result=[],
    )
    def recalibrate(self, direction: int, offset: float, set_position: int = 1) -> Task[()]:
        """Recalibrate against a wall.

        Args:
            direction: wall direction (0 or 1)
            offset: distance offset from wall (mm)
            set_position: whether to update position after recalibration (0 or 1)
        """
        self._send_command(Commands.RECALAGE, direction, offset, set_position)
        return ImmediateResultTask()

    @commands.register(
        args=[],
        result=[
            ("x", ArgTypes.F32()),
            ("y", ArgTypes.F32()),
            ("theta", ArgTypes.F32()),
        ],
    )
    def query_position(self) -> Task[Pose2D]:
        """Query the board for current position (x, y, theta)."""
        return self._send_query(Commands.GET_POSITION).transform(
            lambda x, y, heading: Pose2D(x, y, heading)
        )

    @commands.register(
        args=[],
        result=[
            ("kp", ArgTypes.F32()),
            ("ki", ArgTypes.F32()),
            ("kd", ArgTypes.F32()),
        ],
    )
    def query_pid_trsl(self) -> Task[tuple[float, float, float]]:
        """Query translation PID coefficients (kp, ki, kd)."""
        return self._send_query(Commands.GET_PID_TRSL)

    @commands.register(
        args=[],
        result=[
            ("kp", ArgTypes.F32()),
            ("ki", ArgTypes.F32()),
            ("kd", ArgTypes.F32()),
        ],
    )
    def query_pid_rot(self) -> Task[tuple[float, float, float]]:
        """Query rotation PID coefficients (kp, ki, kd)."""
        return self._send_query(Commands.GET_PID_ROT)

    @commands.register(
        args=[],
        result=[
            ("trsl_acc", ArgTypes.F32()),
            ("trsl_dec", ArgTypes.F32()),
            ("trsl_max", ArgTypes.F32()),
            ("rot_acc", ArgTypes.F32()),
            ("rot_dec", ArgTypes.F32()),
            ("rot_max", ArgTypes.F32()),
        ],
    )
    def query_speeds(self) -> Task[tuple[float, float, float, float, float, float]]:
        """Query speed limits (trsl_acc, trsl_dec, trsl_max, rot_acc, rot_dec, rot_max)."""
        return self._send_query(Commands.GET_SPEEDS)

    @commands.register(
        args=[],
        result=[
            ("spacing", ArgTypes.F32()),
            ("diam_left", ArgTypes.F32()),
            ("diam_right", ArgTypes.F32()),
        ],
    )
    def query_wheels(self) -> Task[tuple[float, float, float]]:
        """Query wheel config (spacing, diam_left, diam_right)."""
        return self._send_query(Commands.GET_WHEELS)

    @commands.register(
        args=[],
        result=[
            ("trsl", ArgTypes.F32()),
            ("rot", ArgTypes.F32()),
        ],
    )
    def query_delta_max(self) -> Task[tuple[float, float]]:
        """Query max error tolerances (trsl, rot)."""
        return self._send_query(Commands.GET_DELTA_MAX)

    @property
    def is_moving(self) -> bool:
        return self._moving

    # Internal

    def _send_command(self, command: Commands, *args) -> Task[()]:
        """Send a command and wait for ACK (unless the command doesn't expect one)."""
        packet = build_packet(command, *args)
        if command not in NO_ACK_COMMANDS:
            self._ack_event.clear()
        with self._lock:
            self._bus.write(packet)
        if command not in NO_ACK_COMMANDS:
            self._ack_event.wait(timeout=_ACK_TIMEOUT)
        return ImmediateResultTask() # TODO: Be async

    def _send_move(self, command: Commands, *args) -> Task[PilotMoveStatus]:
        """Send a movement command, wait for ACK, return a task that completes on MOVE_END."""
        task = DelayedTask[PilotMoveStatus]()
        self._move_task = task
        self._send_command(command, *args).wait()
        return task

    def _send_query(self, command: Commands) -> Task[tuple]:
        """Send a GET command, wait for the response, and return parsed values."""
        self._response_event.clear()
        self._response_data = ()
        packet = build_packet(command)
        with self._lock:
            self._bus.write(packet)
        if not self._response_event.wait(timeout=_RESPONSE_TIMEOUT):
            self._log.warning(f"Query {command.name} timed out")
            return ImmediateResultTask(())
        return ImmediateResultTask(self._response_data)

    def _reader_loop(self) -> None:
        """Background thread: read and dispatch incoming messages from the board."""
        while self._running:
            try:
                header = self._bus.read_available() # FIXME: Non blocking read cause high CPU usage
                if not header:
                    continue
                self._process_bytes(header)
            except TimeoutError:
                continue
            except Exception as e:
                if self._running:
                    self._log.error(f"Pilot reader error: {e}")

    def _process_bytes(self, data: bytes) -> None:
        """Accumulate incoming bytes and parse complete packets."""
        self._rx_buffer.extend(data)
        while len(self._rx_buffer) >= 2:
            length = self._rx_buffer[0]
            if length < 2:
                # Invalid length, skip byte
                del self._rx_buffer[0]
                continue
            if len(self._rx_buffer) < length:
                break  # Wait for more bytes
            cmd = self._rx_buffer[1]
            payload = bytes(self._rx_buffer[2:length])
            self._dispatch(cmd, payload)
            del self._rx_buffer[:length]

    def _dispatch(self, cmd: int, payload: bytes) -> None:
        """Handle a parsed incoming message."""
        #self._log.debug(f"Received message: cmd={cmd}, payload={payload.hex()}")
        if cmd == Commands.ACKNOWLEDGE:
            self._ack_event.set()
        elif cmd == Commands.MOVE_BEGIN:
            self._moving = True
        elif cmd == Commands.MOVE_END:
            self._moving = False
            if self._move_task is not None:
                self._move_task.complete(PilotMoveStatus.REACHED)
                self._move_task = None
        elif cmd == Commands.TELEMETRY_MESSAGE:
            # Format: bbffff (counter, cmdid, x, y, theta, speed)
            x, y, theta, speed = struct.unpack("=ffff", payload)
            # self._log.debug(f"Telemetry: x={x:.1f}, y={y:.1f}, theta={math.degrees(theta):.1f}°, speed={speed:.1f}mm/s")
            self._last_position.x = x
            self._last_position.y = y
            self._last_position.heading = theta
            self._last_speed = speed
            self._pose_or_velocity_update_event.trigger(self._last_position, self._last_velocity)
        elif cmd == Commands.GET_TRAVEL_THETA:
            # Format: f(travel_theta)
            (travel_theta,) = struct.unpack("=f", payload)
            # self._log.debug(f"Telemetry: travel_theta = {math.degrees(travel_theta)}°")
            self._last_velocity = Vect2D.from_polar(self._last_speed, travel_theta)
        elif cmd == Commands.ERROR:
            self._moving = False
            if self._move_task is not None:
                error_code = payload[0] if payload else 0
                if error_code == Errors.DESTINATION_UNREACHABLE:
                    self._move_task.complete(PilotMoveStatus.BLOCKED)
                else:
                    self._move_task.complete(PilotMoveStatus.ERROR)
                self._move_task = None
        elif cmd == Commands.DEBUG:
            self._log.debug(f"Board debug: {payload.hex():x}")
        elif cmd == Commands.DEBUG_MESSAGE and len(payload) >= 2:
            self._log.debug(f"Board debug msg (counter={payload[0]}, cmd={payload[1]})")
        elif cmd in RESPONSE_FORMATS:
            # GET command response: payload starts with bb (counter, cmd_id) then data
            fmt = RESPONSE_FORMATS[Commands(cmd)]
            expected = 2 + struct.calcsize(fmt)
            if len(payload) >= expected:
                values = struct.unpack(fmt, payload[2 : 2 + struct.calcsize(fmt)])
                self._response_data = values
                self._response_event.set()


class DifferentialSerialPilotDefinition(DriverDefinition):
    """Factory for SerialPilot from config args."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(DifferentialPilot.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("serial", ArgTypes.Component(Serial, self._peripherals))
        return defn

    def create(self, args: DriverInitArgs) -> DifferentialSerialPilot:
        return DifferentialSerialPilot(
            name = args.get_name(),
            logger = self._logger,
            bus = args.get("serial"),
        )


class HolonomicSerialPilot(DifferentialSerialPilot, HolonomicPilot):
    """Holonomic trajectory manager using GLOBAL_GOTO for simultaneous translation+rotation."""

    commands = DriverCommands([DifferentialSerialPilot.commands, HolonomicPilot.commands])

    def go_to_while_head_to(self, x: float, y: float, heading: float) -> Task[PilotMoveStatus]:
        return self._send_move(
            Commands.GLOBAL_GOTO,
            x,
            y,
            heading,
            0.0,
            1.0,
            0.0,
            1.0,  # rot and trsl both 0-100%
            0,  # rot_direction=auto
            0,  # avoid=False (avoidance handled at higher level)
        )

    def go_to_while_rotate(self, x: float, y: float, angle: float) -> Task[PilotMoveStatus]:
        target_theta = self._last_position[2] + angle
        return self._send_move(
            Commands.GLOBAL_GOTO,
            x,
            y,
            target_theta,
            0.0,
            1.0,
            0.0,
            1.0,
            1 if angle >= 0 else -1,
            0,
        )

    def go_to_while_look_at(
        self, x: float, y: float, look_x: float, look_y: float
    ) -> Task[PilotMoveStatus]:
        heading = math.atan2(look_y - y, look_x - x)
        return self._send_move(
            Commands.GLOBAL_GOTO,
            x,
            y,
            heading,
            0.0,
            1.0,
            0.0,
            1.0,
            0,
            0,
        )

    def follow_holonomic_path(
        self, waypoints: list[HolonomicPilotWaypoint]
    ) -> Task[PilotMoveStatus]:
        raise NotImplementedError("follow_holonomic_path not implemented yet")

    def calibrate_otos(self) -> Task[()]:
        """Override `Pilot.calibrate_otos` to forward the calibration
        request to the firmware via the serial command bus."""
        return self._send_command(Commands.OTOS_CAL)


class HolonomicSerialPilotDefinition(DriverDefinition):
    """Factory for HolonomicSerialPilot from config args."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(HolonomicSerialPilot.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("serial", ArgTypes.Component(Serial, self._peripherals))
        return defn

    def create(self, args: DriverInitArgs) -> HolonomicSerialPilot:
        return HolonomicSerialPilot(
            name = args.get_name(),
            logger = self._logger,
            bus = args.get("serial"),
        )


class DifferentialSerialPilotVirtual(DifferentialPilotVirtual):
    """Drop-in virtual twin for DifferentialSerialPilot.

    Constructor mirrors DifferentialSerialPilot exactly so a config swap is
    a one-line change. ``bus`` is kept for signature parity and is
    orthogonal to the simulation — the serial bus itself may be a real or
    virtual Serial, that choice is orthogonal too.
    """

    def __init__(self, name: str, logger: Logger, bus: Serial):
        super().__init__(name, logger)
        self._bus = bus


class DifferentialSerialPilotVirtualDefinition(DriverDefinition):
    """Factory for DifferentialSerialPilotVirtual — args mirror the real Definition."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(DifferentialPilot.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("serial", ArgTypes.Component(Serial, self._peripherals))
        return defn

    def create(self, args: DriverInitArgs) -> DifferentialSerialPilotVirtual:
        return DifferentialSerialPilotVirtual(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("serial"),
        )


class HolonomicSerialPilotVirtual(HolonomicPilotVirtual):
    """Drop-in virtual twin for HolonomicSerialPilot.

    Constructor mirrors HolonomicSerialPilot exactly; ``bus`` is kept for
    signature parity and is orthogonal to the simulation.
    """

    def __init__(self, name: str, logger: Logger, bus: Serial):
        super().__init__(name, logger)
        self._bus = bus


class HolonomicSerialPilotVirtualDefinition(DriverDefinition):
    """Factory for HolonomicSerialPilotVirtual — args mirror the real Definition."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__(HolonomicPilot.commands)
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("serial", ArgTypes.Component(Serial, self._peripherals))
        return defn

    def create(self, args: DriverInitArgs) -> HolonomicSerialPilotVirtual:
        return HolonomicSerialPilotVirtual(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("serial"),
        )
