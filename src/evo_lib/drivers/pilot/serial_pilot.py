"""Pilot driver: DifferentialPilot over carte-asserv serial binary protocol.

Implements the legacy trajectory manager protocol: binary packets over UART,
with asynchronous ACKNOWLEDGE/MOVE_BEGIN/MOVE_END events from the board.
"""

import logging
import math
import struct
import threading

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverDefinition, DriverInitArgs, DriverInitArgsDefinition
from evo_lib.drivers.pilot.protocol import (
    INIT_PACKET,
    NO_ACK_COMMANDS,
    RESPONSE_FORMATS,
    Commands,
    Errors,
    build_packet,
)
from evo_lib.interfaces.pilot import (
    DifferentialPilot,
    DifferentialPilotWaypoint,
    HolonomicPilot,
    HolonomicPilotWaypoint,
    PilotMoveStatus,
)
from evo_lib.interfaces.serial import Serial
from evo_lib.logger import Logger
from evo_lib.task import DelayedTask, ImmediateResultTask, Task

_ACK_TIMEOUT = 1.0
_RESPONSE_TIMEOUT = 1.0


class SerialPilot(DifferentialPilot):
    """Trajectory manager communicating with carte-asserv via serial binary protocol."""

    def __init__(
        self,
        name: str,
        bus: Serial,
        logger: logging.Logger | None = None,
    ):
        super().__init__(name)
        self._bus = bus
        self._log = logger or logging.getLogger(__name__)
        self._lock = threading.Lock()
        self._ack_event = threading.Event()
        self._move_task: DelayedTask[PilotMoveStatus] | None = None
        self._reader_thread: threading.Thread | None = None
        self._running = False
        self._position = (0.0, 0.0, 0.0)  # x, y, theta
        self._moving = False
        self._rx_buffer = bytearray()
        self._response_event = threading.Event()
        self._response_data: tuple = ()

    def init(self) -> None:
        self._running = True
        self._reader_thread = threading.Thread(
            target=self._reader_loop, daemon=True, name=f"pilot-reader-{self.name}"
        )
        self._reader_thread.start()
        # Send init packet
        with self._lock:
            self._bus.write(INIT_PACKET)
        self._log.info("SerialPilot '%s' initialized", self.name)

    def close(self) -> None:
        self._running = False
        if self._reader_thread is not None:
            self._reader_thread.join(timeout=2.0)
            self._reader_thread = None
        self._log.info("SerialPilot '%s' closed", self.name)

    # --- Movement commands ---

    def go_to(self, x: float, y: float) -> Task[PilotMoveStatus]:
        return self._send_move(Commands.GOTO_XY, x, y)

    def go_to_then_head_to(self, x: float, y: float, heading: float) -> Task[PilotMoveStatus]:
        # TODO: chain go_to + head_to sequentially after MOVE_END
        return self._send_move(Commands.GOTO_XY, x, y)

    def go_to_then_rotate(self, x: float, y: float, angle: float) -> Task[PilotMoveStatus]:
        # TODO: chain go_to + rotate sequentially after MOVE_END
        return self._send_move(Commands.GOTO_XY, x, y)

    def go_to_then_look_at(
        self, x: float, y: float, look_x: float, look_y: float
    ) -> Task[PilotMoveStatus]:
        # TODO: chain go_to + look_at sequentially after MOVE_END
        return self._send_move(Commands.GOTO_XY, x, y)

    def forward(self, distance: float) -> Task[PilotMoveStatus]:
        direction = 1 if distance >= 0 else -1
        return self._send_move(Commands.MOVE_TRSL, abs(distance), 0.0, 0.0, 0.0, direction)

    def head_to(self, heading: float) -> Task[PilotMoveStatus]:
        return self._send_move(Commands.GOTO_THETA, heading)

    def look_at(self, x: float, y: float) -> Task[PilotMoveStatus]:
        dx = x - self._position[0]
        dy = y - self._position[1]
        heading = math.atan2(dy, dx)
        return self._send_move(Commands.GOTO_THETA, heading)

    def rotate(self, angle: float) -> Task[PilotMoveStatus]:
        direction = 1 if angle >= 0 else -1
        return self._send_move(Commands.MOVE_ROT, abs(angle), 0.0, 0.0, 0.0, direction)

    def follow_path(self, waypoints: list[DifferentialPilotWaypoint]) -> Task[PilotMoveStatus]:
        # TODO: send intermediate waypoints to the board (CURVE command or sequential GOTO_XY)
        if not waypoints:
            return ImmediateResultTask(PilotMoveStatus.REACHED)
        wp = waypoints[-1]
        return self.go_to(wp.x, wp.y)

    def stop(self) -> Task[None]:
        self._send_command(Commands.STOP_ASAP, 0.0, 0.0)
        if self._move_task is not None:
            self._move_task.complete(PilotMoveStatus.CANCELLED)
            self._move_task = None
        return ImmediateResultTask(None)

    def free(self) -> Task[None]:
        self._send_command(Commands.FREE)
        return ImmediateResultTask(None)

    def unfree(self) -> Task[None]:
        """Re-enable motors after a free() call."""
        self._send_command(Commands.UNFREE)
        return ImmediateResultTask(None)

    # --- Configuration (SerialPilot-specific) ---

    def set_position(self, x: float, y: float, theta: float) -> None:
        """Set the robot's absolute position on the board."""
        self._send_command(Commands.SET_X, x)
        self._send_command(Commands.SET_Y, y)
        self._send_command(Commands.SET_THETA, theta)
        self._position = (x, y, theta)

    def set_pid_trsl(self, p: float, i: float, d: float) -> None:
        self._send_command(Commands.SET_PID_TRSL, p, i, d)

    def set_pid_rot(self, p: float, i: float, d: float) -> None:
        self._send_command(Commands.SET_PID_ROT, p, i, d)

    def set_speeds(
        self,
        trsl_acc: float,
        trsl_dec: float,
        trsl_max: float,
        rot_acc: float,
        rot_dec: float,
        rot_max: float,
    ) -> None:
        self._send_command(Commands.SET_TRSL_ACC, trsl_acc)
        self._send_command(Commands.SET_TRSL_DEC, trsl_dec)
        self._send_command(Commands.SET_TRSL_MAXSPEED, trsl_max)
        self._send_command(Commands.SET_ROT_ACC, rot_acc)
        self._send_command(Commands.SET_ROT_DEC, rot_dec)
        self._send_command(Commands.SET_ROT_MAXSPEED, rot_max)

    def set_wheels(self, diam_left: float, diam_right: float, spacing: float) -> None:
        self._send_command(Commands.SET_WHEELS_DIAM, diam_left, diam_right)
        self._send_command(Commands.SET_WHEELS_SPACING, spacing)

    def set_delta_max(self, trsl: float, rot: float) -> None:
        """Set max error tolerances for translation (mm) and rotation (rad)."""
        self._send_command(Commands.SET_DELTA_MAX_TRSL, trsl)
        self._send_command(Commands.SET_DELTA_MAX_ROT, rot)

    def set_robot_size(self, size_x: float, size_y: float) -> None:
        """Set robot dimensions for recalibration (mm)."""
        self._send_command(Commands.SET_ROBOT_SIZE_X, size_x)
        self._send_command(Commands.SET_ROBOT_SIZE_Y, size_y)

    def set_pwm(self, left: float, right: float) -> None:
        """Direct PWM control (for debugging/calibration only)."""
        self._send_command(Commands.SET_PWM, left, right)

    def set_telemetry(self, interval_ms: int) -> None:
        """Set telemetry send interval in milliseconds."""
        self._send_command(Commands.SET_TELEMETRY, interval_ms)

    def recalibrate(self, direction: int, offset: float, set_position: int = 1) -> None:
        """Recalibrate against a wall.

        Args:
            direction: wall direction (0 or 1)
            offset: distance offset from wall (mm)
            set_position: whether to update position after recalibration (0 or 1)
        """
        self._send_command(Commands.RECALAGE, direction, offset, set_position)

    def get_position(self) -> tuple[float, float, float]:
        """Return the last known position from telemetry (x, y, theta)."""
        return self._position

    def query_position(self) -> tuple[float, float, float]:
        """Query the board for current position (x, y, theta)."""
        return self._send_query(Commands.GET_POSITION)

    def query_pid_trsl(self) -> tuple[float, float, float]:
        """Query translation PID coefficients (kp, ki, kd)."""
        return self._send_query(Commands.GET_PID_TRSL)

    def query_pid_rot(self) -> tuple[float, float, float]:
        """Query rotation PID coefficients (kp, ki, kd)."""
        return self._send_query(Commands.GET_PID_ROT)

    def query_speeds(self) -> tuple[float, float, float, float, float, float]:
        """Query speed limits (trsl_acc, trsl_dec, trsl_max, rot_acc, rot_dec, rot_max)."""
        return self._send_query(Commands.GET_SPEEDS)

    def query_wheels(self) -> tuple[float, float, float]:
        """Query wheel config (spacing, diam_left, diam_right)."""
        return self._send_query(Commands.GET_WHEELS)

    def query_delta_max(self) -> tuple[float, float]:
        """Query max error tolerances (trsl, rot)."""
        return self._send_query(Commands.GET_DELTA_MAX)

    @property
    def is_moving(self) -> bool:
        return self._moving

    # --- Internal ---

    def _send_command(self, command: Commands, *args) -> None:
        """Send a command and wait for ACK (unless the command doesn't expect one)."""
        packet = build_packet(command, *args)
        if command not in NO_ACK_COMMANDS:
            self._ack_event.clear()
        with self._lock:
            self._bus.write(packet)
        if command not in NO_ACK_COMMANDS:
            self._ack_event.wait(timeout=_ACK_TIMEOUT)

    def _send_move(self, command: Commands, *args) -> Task[PilotMoveStatus]:
        """Send a movement command, wait for ACK, return a task that completes on MOVE_END."""
        task = DelayedTask[PilotMoveStatus]()
        self._move_task = task
        self._send_command(command, *args)
        return task

    def _send_query(self, command: Commands) -> tuple:
        """Send a GET command, wait for the response, and return parsed values."""
        self._response_event.clear()
        self._response_data = ()
        packet = build_packet(command)
        with self._lock:
            self._bus.write(packet)
        if not self._response_event.wait(timeout=_RESPONSE_TIMEOUT):
            self._log.warning("Query %s timed out", command.name)
            return ()
        return self._response_data

    def _reader_loop(self) -> None:
        """Background thread: read and dispatch incoming messages from the board."""
        while self._running:
            try:
                header = self._bus.read_available()
                if not header:
                    continue
                self._process_bytes(header)
            except TimeoutError:
                continue
            except Exception as e:
                if self._running:
                    self._log.error("Pilot reader error: %s", e)

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
        if cmd == Commands.ACKNOWLEDGE:
            self._ack_event.set()
        elif cmd == Commands.MOVE_BEGIN:
            self._moving = True
        elif cmd == Commands.MOVE_END:
            self._moving = False
            if self._move_task is not None:
                self._move_task.complete(PilotMoveStatus.REACHED)
                self._move_task = None
        elif cmd == Commands.TELEMETRY_MESSAGE and len(payload) >= 18:
            # Format: bbffff (counter, cmdid, x, y, theta, speed)
            _, _, x, y, theta, _ = struct.unpack("=bbffff", payload[:18])
            self._position = (x, y, theta)
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
            self._log.debug("Board debug: %s", payload.hex())
        elif cmd == Commands.DEBUG_MESSAGE and len(payload) >= 2:
            self._log.debug("Board debug msg (counter=%d, cmd=%d)", payload[0], payload[1])
        elif cmd in RESPONSE_FORMATS:
            # GET command response: payload starts with bb (counter, cmd_id) then data
            fmt = RESPONSE_FORMATS[Commands(cmd)]
            expected = 2 + struct.calcsize(fmt)
            if len(payload) >= expected:
                values = struct.unpack(fmt, payload[2 : 2 + struct.calcsize(fmt)])
                self._response_data = values
                self._response_event.set()


class SerialPilotDefinition(DriverDefinition):
    """Factory for SerialPilot from config args."""

    def __init__(self, bus: Serial, logger: Logger):
        self._bus = bus
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        return defn

    def create(self, args: DriverInitArgs) -> SerialPilot:
        name = args.get("name")
        return SerialPilot(
            name=name,
            bus=self._bus,
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )


class HolonomicSerialPilot(SerialPilot, HolonomicPilot):
    """Holonomic trajectory manager using GLOBAL_GOTO for simultaneous translation+rotation."""

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
        target_theta = self._position[2] + angle
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
        # TODO: chain sequential GLOBAL_GOTO for each waypoint
        if not waypoints:
            return ImmediateResultTask(PilotMoveStatus.REACHED)
        wp = waypoints[-1]
        return self.go_to_while_head_to(wp.x, wp.y, wp.heading)

    def calibrate_otos(self) -> None:
        """Calibrate the optical tracking sensor (OTOS)."""
        self._send_command(Commands.OTOS_CAL)


class HolonomicSerialPilotDefinition(DriverDefinition):
    """Factory for HolonomicSerialPilot from config args."""

    def __init__(self, bus: Serial, logger: Logger):
        self._bus = bus
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("name", ArgTypes.String())
        return defn

    def create(self, args: DriverInitArgs) -> HolonomicSerialPilot:
        name = args.get("name")
        return HolonomicSerialPilot(
            name=name,
            bus=self._bus,
            logger=self._logger.get_sublogger(name).get_stdlib_logger(),
        )
