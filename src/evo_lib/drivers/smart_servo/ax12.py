"""AX-12A driver: Dynamixel 1.0 protocol over serial (USB2AX).

The AX-12A is a smart servo with position feedback, communicating via
half-duplex serial using the Dynamixel 1.0 packet protocol.

Layout:
- AX12Bus (InterfaceHolder): owns the Serial bus, serializes packets,
  handles the echo-drain and checksum validation quirks.
- AX12 (SmartServo): one instance per servo ID on the bus.
- AX12BusVirtual: drop-in replacement for AX12Bus with an in-memory
  servo state dict. Same constructor signature so configs can swap.

init() does no bus I/O — torque arming is in enable().
"""

import math
import threading
import time
from typing import Callable

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.serial import Serial
from evo_lib.interfaces.smart_servo import ServoAngleUnit, ServoSpeedUnit, SmartServo
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.thread_pool import ThreadPoolExecutor

# Dynamixel 1.0 instructions
_INST_READ = 0x02
_INST_WRITE = 0x03

# AX-12A factory baudrate (EEPROM default). USB2AX runs the bus at this speed
# unless explicitly reconfigured — mismatch = silent timeout, not an error.
_DEFAULT_BAUDRATE = 1_000_000

# AX-12A register addresses
_CW_ANGLE_LIMIT_L = 6
_CCW_ANGLE_LIMIT_L = 8
_TORQUE_ENABLE = 24
_GOAL_POSITION_L = 30
_MOVING_SPEED_L = 32
_PRESENT_POSITION_L = 36
_PRESENT_SPEED_L = 38
_PRESENT_LOAD_L = 40
_PRESENT_VOLTAGE = 42
_PRESENT_TEMPERATURE = 43

# AX-12A constants (datasheet: Dynamixel 1.0 / AX-12A control table)
_POSITION_MAX = 1023
_ANGLE_MAX = 300.0  # degrees
_SPEED_MAX = 1023
_SPEED_MAX_RPM = 114
_LOAD_MAX = 1023
_DIRECTION_BIT = 0x400  # bit 10 of moving_speed / present_speed / present_load: 1 = CW
_MAGNITUDE_MASK = 0x3FF  # bits 0-9 of present_speed / present_load
_BROADCAST_ID = 0xFE

_HEADER_B0 = 0xFF
_HEADER_B1 = 0xFF

# Legacy retry defaults (services/lib/actuators/ax12.py used 3 tries, 25 ms sleep).
# Kept at 3 to preserve robustness on noisy buses — AX-12 half-duplex under
# motor load can drop a packet every few hundred transactions.
_DEFAULT_RETRIES = 3
_DEFAULT_RETRY_DELAY = 0.025
_DEFAULT_MAX_REQUESTS_PER_SECOND = 50
# USB2AX (Xevelabs, the standard Evolutek dongle) does not echo TX on RX: it
# handles half-duplex direction internally in its ATmega firmware. Only the
# older USB2Dynamixel (FT232 + external tri-state) echoes. Default to no-echo
# because that matches the hardware actually used on the robot; set echo=True
# only if you plug a USB2Dynamixel in.
_DEFAULT_ECHO = False

# Max AX-12 packet size we ever emit: 2 header + id + len + inst + reg + up to
# 2 data bytes + checksum = 9. Round up for headroom on future register writes.
_TX_BUF_SIZE = 16


# --- Error hierarchy ---
# Dynamixel 1.0 status error byte (AX-12A e-manual). Inherits from OSError so
# existing `except OSError` call sites (retry loop, REPL, close handler) keep
# working without migration. Bus-side errors are retryable; servo-side refusals
# are not — the servo has already rejected the packet and would refuse the
# exact same retry, just burning bus time.


class DynamixelError(OSError):
    """Base for all AX-12 protocol errors."""


class DynamixelBusError(DynamixelError):
    """Transient bus fault (framing, timeout, crossed reply). Retryable."""


class DynamixelServoError(DynamixelError):
    """Servo reported an error byte in its status packet. Not retryable
    (except PacketChecksumError, handled specially in the retry loop)."""

    ERROR_BIT: int = 0

    def __init__(self, servo_id: int, error_byte: int, reason: str):
        self.servo_id = servo_id
        self.error_byte = error_byte
        super().__init__(f"AX12 id {servo_id}: {reason} (0x{error_byte:02x})")


class InputVoltageError(DynamixelServoError):
    ERROR_BIT = 0x01

    def __init__(self, servo_id: int, error_byte: int):
        super().__init__(servo_id, error_byte, "input voltage out of range")


class AngleLimitError(DynamixelServoError):
    ERROR_BIT = 0x02

    def __init__(self, servo_id: int, error_byte: int):
        super().__init__(servo_id, error_byte, "goal position outside angle limits")


class OverheatingError(DynamixelServoError):
    ERROR_BIT = 0x04

    def __init__(self, servo_id: int, error_byte: int):
        super().__init__(servo_id, error_byte, "overheating")


class RangeError(DynamixelServoError):
    ERROR_BIT = 0x08

    def __init__(self, servo_id: int, error_byte: int):
        super().__init__(servo_id, error_byte, "instruction parameter out of range")


class PacketChecksumError(DynamixelServoError):
    """Servo received a corrupted instruction packet. TX-side noise, retryable."""

    ERROR_BIT = 0x10

    def __init__(self, servo_id: int, error_byte: int):
        super().__init__(servo_id, error_byte, "servo received bad checksum (TX noise)")


class OverloadError(DynamixelServoError):
    ERROR_BIT = 0x20

    def __init__(self, servo_id: int, error_byte: int):
        super().__init__(servo_id, error_byte, "overload (motor stalled)")


class InstructionError(DynamixelServoError):
    ERROR_BIT = 0x40

    def __init__(self, servo_id: int, error_byte: int):
        super().__init__(servo_id, error_byte, "unknown instruction")


# Order matters only for diagnostics when multiple bits are set: we surface
# the lowest-numbered bit that matched. The error_byte attribute preserves
# the full mask so callers can inspect all flags.
_ERROR_BITS: tuple[type[DynamixelServoError], ...] = (
    InputVoltageError,
    AngleLimitError,
    OverheatingError,
    RangeError,
    PacketChecksumError,
    OverloadError,
    InstructionError,
)


def _decode_servo_error(servo_id: int, error_byte: int) -> DynamixelServoError:
    for cls in _ERROR_BITS:
        if error_byte & cls.ERROR_BIT:
            return cls(servo_id, error_byte)
    # Reserved bit 7 or an unknown combination — still servo-side, so not
    # retried. Keep the raw byte visible in the message for diagnostics.
    return DynamixelServoError(servo_id, error_byte, "unknown servo error")


def _checksum(servo_id: int, length: int, *data: int) -> int:
    """Compute Dynamixel 1.0 checksum (helper for tests / status reconstruction)."""
    return (~(servo_id + length + sum(data))) & 0xFF


def _decode_signed(word: int) -> int:
    """Decode an AX-12 direction-bit word (speed/load) into a signed magnitude."""
    magnitude = word & _MAGNITUDE_MASK
    return -magnitude if (word & _DIRECTION_BIT) else magnitude


class AX12Bus(InterfaceHolder):
    """Manages the Dynamixel AX-12 bus (USB2AX).

    Wraps a Serial interface with Dynamixel 1.0 framing:
    write, drain echo, read status, verify checksum.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        thread_pool: ThreadPoolExecutor,
        bus: Serial,
        baudrate: int = _DEFAULT_BAUDRATE,
        retries: int = _DEFAULT_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
        max_requests_per_second: int = _DEFAULT_MAX_REQUESTS_PER_SECOND,
        echo: bool = _DEFAULT_ECHO,
    ):
        super().__init__(name)
        self._log = logger
        self._thread_pool = thread_pool
        self._bus = bus
        self._baudrate = baudrate
        self._retries = retries
        self._retry_delay = retry_delay
        self._max_requests_per_second = max_requests_per_second
        self._echo = echo
        self._lock = threading.Lock()
        self._servos: dict[int, "AX12"] = {}
        # Reusable TX buffer (hot path): avoids per-call bytearray allocation on
        # every write/read. Safe under the bus lock, only one packet is ever
        # being built at a time. Matters on RPi 3 B+ where GC pressure adds up.
        self._tx_buf = bytearray(_TX_BUF_SIZE)

    def init(self) -> Task[()]:
        # Force the underlying Serial to AX-12 baudrate regardless of its own
        # default — otherwise we get silent timeouts on real hardware.
        self._bus.set_baudrate(self._baudrate)
        self._log.info(f"AX12Bus '{self.name}' initialized at {self._baudrate} baud")
        return ImmediateResultTask()

    def close(self) -> None:
        self._servos.clear()
        self._log.info(f"AX12Bus '{self.name}' closed")

    def get_subcomponents(self) -> list[Peripheral]:
        return list(self._servos.values())

    def register_servo(self, servo: "AX12") -> None:
        """Record a servo so it shows up in get_subcomponents()."""
        if servo.servo_id in self._servos:
            self._log.warning(
                f"AX12Bus '{self.name}': duplicate servo id {servo.servo_id} "
                f"('{self._servos[servo.servo_id].name}' overwritten by '{servo.name}')"
            )
        self._servos[servo.servo_id] = servo

    def write_register(self, servo_id: int, register: int, data: bytes) -> Task[()]:
        """Send a WRITE instruction. Broadcast (0xFE) gets no status reply."""
        with self._lock:
            return self._request(lambda: self._do_write(servo_id, register, data))

    def read_register(self, servo_id: int, register: int, count: int) -> Task[bytes]:
        """Send a READ instruction and return the payload bytes."""
        with self._lock:
            return self._request(lambda: self._do_read(servo_id, register, count))

    def _request[T](self, op: Callable[[], T]) -> Task[T]:
        """Send a WRITE instruction. Broadcast (0xFE) gets no status reply."""
        return self._thread_pool.exec(op)

    def _request_sync[T](self, op: Callable[[], T]) -> T:
        # On failure we flush the RX buffer before retrying: a half-received
        # status packet would desync the next framing attempt. We accept the
        # cost of dropping a valid-but-late reply (timing edge case).
        #
        # Servo-side refusals (DynamixelServoError) are NOT retried: the servo
        # has already processed the packet and rejected it; retrying sends the
        # exact same bytes and gets the exact same refusal. The one exception
        # is PacketChecksumError: the servo reports that the instruction it
        # received had a bad checksum, which is one-shot TX noise and safe to
        # rejouer.
        attempts = 0
        while True:
            try:
                return op()
            except DynamixelServoError as err:
                if not isinstance(err, PacketChecksumError):
                    raise
                self._bus.reset_input_buffer()
                if attempts >= self._retries:
                    raise
                attempts += 1
                self._log.debug(f"AX12Bus '{self.name}' retry {attempts}/{self._retries}: {err}")
                time.sleep(self._retry_delay)
            except OSError as err:
                self._bus.reset_input_buffer()
                if attempts >= self._retries:
                    raise
                attempts += 1
                self._log.debug(f"AX12Bus '{self.name}' retry {attempts}/{self._retries}: {err}")
                time.sleep(self._retry_delay)

    def _do_write(self, servo_id: int, register: int, data: bytes) -> None:
        n = len(data)
        length = n + 3  # instruction + register + data + checksum
        buf = self._tx_buf
        buf[0] = _HEADER_B0
        buf[1] = _HEADER_B1
        buf[2] = servo_id
        buf[3] = length
        buf[4] = _INST_WRITE
        buf[5] = register
        buf[6 : 6 + n] = data
        cs = servo_id + length + _INST_WRITE + register
        for b in data:
            cs += b
        buf[6 + n] = (~cs) & 0xFF
        size = 7 + n
        packet = bytes(buf[:size])
        self._send_and_drop_echo(packet)
        if servo_id != _BROADCAST_ID:
            self._read_status(servo_id)

    def _do_read(self, servo_id: int, register: int, count: int) -> bytes:
        length = 4  # instruction + register + count + checksum
        buf = self._tx_buf
        buf[0] = _HEADER_B0
        buf[1] = _HEADER_B1
        buf[2] = servo_id
        buf[3] = length
        buf[4] = _INST_READ
        buf[5] = register
        buf[6] = count
        cs = servo_id + length + _INST_READ + register + count
        buf[7] = (~cs) & 0xFF
        packet = bytes(buf[:8])
        self._send_and_drop_echo(packet)
        return self._read_status(servo_id)

    def _send_and_drop_echo(self, packet: bytes) -> None:
        """Write then, if the dongle echoes, discard the local echo.

        USB2AX (Xevelabs, default) does not echo: we skip the drain read
        entirely, which is what the legacy libdxl.so-based stack has been
        doing in production for years. USB2Dynamixel-style dongles that
        mirror TX onto RX require echo=True in the constructor.
        """
        self._bus.write(packet)
        if self._echo:
            _ = self._bus.read(len(packet))

    def _read_status(self, expected_id: int) -> bytes:
        """Read and validate a Dynamixel 1.0 status packet.

        Returns the parameter bytes (excluding error and checksum).
        """
        header = self._bus.read(2)
        if header[0] != _HEADER_B0 or header[1] != _HEADER_B1:
            raise DynamixelBusError(f"invalid header {bytes(header)!r}")
        id_len = self._bus.read(2)
        resp_id, resp_length = id_len[0], id_len[1]
        # Detect a crossed reply (servo X answers a request addressed to Y —
        # happens after a prior timeout leaves a stale status in the buffer).
        if resp_id != expected_id:
            raise DynamixelBusError(f"crossed reply (expected id {expected_id}, got {resp_id})")
        # AX-12 status packet: error + 0..N params + checksum. Minimum 2 bytes
        # (error + checksum). Below that, payload[0] and payload[-1] collide
        # and we'd silently misread the error byte. Upper bound guards against
        # a faulty servo making us block on the serial timeout.
        if resp_length < 2 or resp_length > 8:
            raise DynamixelBusError(f"implausible status length {resp_length}")
        payload = self._bus.read(resp_length)
        cs = resp_id + resp_length
        for b in payload[:-1]:
            cs += b
        expected = (~cs) & 0xFF
        if payload[-1] != expected:
            raise DynamixelBusError(f"bad checksum (got {payload[-1]:#x}, expected {expected:#x})")
        error = payload[0]
        if error != 0:
            raise _decode_servo_error(resp_id, error)
        return bytes(payload[1:-1])


class AX12(SmartServo):
    """A single AX-12A servo on a Dynamixel bus.

    Bus-agnostic: works with any AX12Bus (real or virtual).
    """

    commands = DriverCommands(parents=[SmartServo.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        thread_pool: ThreadPoolExecutor,
        bus: AX12Bus,
        servo_id: int,
        goal_reached_tolerance: int = 10,
    ):
        super().__init__(name)
        self._log = logger
        self._thread_pool = thread_pool
        self._bus = bus
        self._id = servo_id
        self._goal_reached_tolerance = goal_reached_tolerance
        bus.register_servo(self)

    @property
    def servo_id(self) -> int:
        return self._id

    def init(self) -> Task[()]:
        # No bus I/O: torque is armed later via enable().
        return ImmediateResultTask()

    @commands.register(args=[], result=[])
    def enable(self) -> Task[()]:
        """Power torque so the servo can hold or move to a position.

        AX-12A boots with Torque Enable = 0 (datasheet). Call after the
        12V motor rail is up.
        """
        self._log.info(f"AX12 '{self.name}' (ID {self._id}) torque enabled")
        return self._bus.write_register(self._id, _TORQUE_ENABLE, bytes([1]))

    def close(self) -> None:
        # TimeoutError is an OSError subclass in Py3, so one clause covers both.
        try:
            self._bus.write_register(self._id, _TORQUE_ENABLE, bytes([0])).wait()
        except OSError as err:
            self._log.warning(
                f"AX12 '{self.name}' (ID {self._id}) close: torque-disable failed: {err}"
            )

    # --- Movement ---

    def _wait_move_to_sync(
        self, raw_position: int, wait_multiplier: float, timeout: float | None
    ) -> None:
        if wait_multiplier == 0:
            return

        current_position = self.get_position(ServoAngleUnit.NATIVE).wait()[0]
        wait_position = current_position + (raw_position - current_position) * wait_multiplier
        move_direction = 1 if wait_position > current_position else -1

        start_time = time.time()
        while True:
            if timeout is not None and time.time() - start_time > timeout:
                raise TimeoutError("Move timed out")
            current_position = self.get_position(ServoAngleUnit.NATIVE).wait()[0]
            remaining_distance = wait_position - current_position
            if abs(remaining_distance) < self._goal_reached_tolerance:
                break  # If we're close enough, return
            if remaining_distance * move_direction < 0:
                break  # If we go beyond the target, return

    def move_to(
        self,
        position: float,
        unit: ServoAngleUnit,
        wait_multiplier: float = 1.0,
        timeout: float | None = None,
    ) -> Task[()]:
        if unit == ServoAngleUnit.DEGREES:
            raw_position = max(0.0, min(_ANGLE_MAX, position))
        elif unit == ServoAngleUnit.FRACTION:
            raw_position = max(0.0, min(1.0, position))
        elif unit == ServoAngleUnit.RADIANS:
            raw_position = max(0.0, min(_ANGLE_MAX, position * 180.0 / math.pi))
        elif unit == ServoAngleUnit.NATIVE:
            raw_position = position
        else:
            raise ValueError(f"Invalid unit: {unit}")

        raw_position = max(0, min(_POSITION_MAX, int(raw_position)))
        self._write_word(_GOAL_POSITION_L, raw_position)

        if wait_multiplier == 0:
            return ImmediateResultTask()

        return self._thread_pool.exec(
            lambda: self._wait_move_to_sync(raw_position, wait_multiplier, timeout)
        )

    # --- Position feedback ---

    def _read_word(self, register: int) -> int:
        (data,) = self._bus.read_register(self._id, register, 2).wait()
        return data[0] | (data[1] << 8)

    def _write_word(self, register: int, value: int) -> None:
        self._bus.write_register(
            self._id, register, bytes([value & 0xFF, (value >> 8) & 0xFF])
        ).wait()

    def get_position(self, unit: ServoAngleUnit) -> Task[int]:
        return ImmediateResultTask(self._read_word(_PRESENT_POSITION_L))

    # --- Speed ---

    def set_speed(self, speed: float, unit: ServoSpeedUnit) -> Task[()]:
        if unit == ServoSpeedUnit.NATIVE:
            pass  # speed is already in native units (0..1023)
        elif unit == ServoSpeedUnit.RPM:
            speed = speed / _SPEED_MAX_RPM * _SPEED_MAX
        elif unit == ServoSpeedUnit.DEGREES_PER_SECOND:
            speed = speed * 60 / 360 * _SPEED_MAX / _SPEED_MAX_RPM
        elif unit == ServoSpeedUnit.RADIANS_PER_SECOND:
            speed = speed * 60 / (math.pi * 2) * _SPEED_MAX / _SPEED_MAX_RPM
        speed = max(0, min(_SPEED_MAX, int(speed)))
        self._write_word(_MOVING_SPEED_L, speed)
        return ImmediateResultTask()

    def get_speed(self, unit: ServoSpeedUnit) -> Task[float]:
        """Present speed as a signed magnitude in [-1023, 1023].

        Per Dynamixel datasheet, bit 10 of present_speed is 1 = CW, 0 = CCW;
        bits 0-9 are the magnitude. Decoded here with CCW-positive convention
        (bit 10 set -> negative), matching the trigonometric direct sense used
        by Position/Pose. Callers who want a fraction divide by 1023.
        """
        raw = _decode_signed(self._read_word(_PRESENT_SPEED_L))
        if unit == ServoSpeedUnit.NATIVE:
            return ImmediateResultTask(raw)
        rpm = raw * _SPEED_MAX_RPM / _SPEED_MAX
        if unit == ServoSpeedUnit.RPM:
            pass  # already in RPM units
        elif unit == ServoSpeedUnit.RADIANS_PER_SECOND:
            rpm *= 2.0 * math.pi / 60
        elif unit == ServoSpeedUnit.DEGREES_PER_SECOND:
            rpm *= 360.0 / 60
        return ImmediateResultTask(rpm)

    # --- Load (motor current) ---

    def get_load(self) -> Task[float]:
        """Present load as a signed magnitude in [-1023, 1023].

        Same encoding as present_speed (CCW-positive): positive = CCW torque,
        negative = CW torque. Useful for grip detection via |load| — stall
        magnitude rises on catch regardless of direction. Callers who want a
        fraction divide by 1023.
        """
        return ImmediateResultTask(_decode_signed(self._read_word(_PRESENT_LOAD_L)))

    # --- Diagnostics ---

    @commands.register(
        args=[],
        result=[("voltage", ArgTypes.F32(help="Present bus voltage (V)"))],
    )
    def get_voltage(self) -> Task[float]:
        """Present voltage in volts (register is tenths of a volt)."""
        (data,) = self._bus.read_register(self._id, _PRESENT_VOLTAGE, 1).wait()
        return ImmediateResultTask(data[0] / 10.0)

    @commands.register(
        args=[],
        result=[("temperature", ArgTypes.U8(help="Present motor temperature (°C)"))],
    )
    def get_temperature(self) -> Task[int]:
        """Present temperature in °C (internal sensor, shutdown ~70°C)."""
        return self._bus.read_register(self._id, _PRESENT_TEMPERATURE, 1).transform(
            lambda d: (d[0],)
        )

    @commands.register(args=[], result=[])
    def reset(self) -> Task[()]:
        """Move to the mechanical center (150°)."""
        # TODO: implement reset for AX-12A (power cycle via an optionnal GPIO given at initialization)
        raise NotImplementedError("reset is currently not supported by AX-12A")

    # --- Angle limits (EEPROM, persistent across power cycles) ---

    @commands.register(
        args=[],
        result=[("cw_limit", ArgTypes.U16(help="CW (lower) goal-position bound in native units"))],
    )
    def get_cw_angle_limit(self) -> Task[int]:
        """Read the CW angle limit from EEPROM.

        Goal positions below this value are rejected by the servo firmware
        with an Angle Limit Error (status error bit 1). A value of 0 on
        both limits puts the servo in wheel (continuous) mode.
        """
        return ImmediateResultTask(self._read_word(_CW_ANGLE_LIMIT_L))

    @commands.register(
        args=[],
        result=[
            ("ccw_limit", ArgTypes.U16(help="CCW (upper) goal-position bound in native units"))
        ],
    )
    def get_ccw_angle_limit(self) -> Task[int]:
        """Read the CCW angle limit from EEPROM."""
        return ImmediateResultTask(self._read_word(_CCW_ANGLE_LIMIT_L))

    # --- Operating modes ---

    def mode_joint(self) -> Task[()]:
        """Set angle-limited mode (0..1023), the default factory mode."""
        self._write_word(_CW_ANGLE_LIMIT_L, 0)
        self._write_word(_CCW_ANGLE_LIMIT_L, _POSITION_MAX)
        return ImmediateResultTask()

    def mode_wheel(self) -> Task[()]:
        """Set continuous-rotation mode (both angle limits = 0).

        In this mode, `set_speed` / `turn` drive the servo like a motor.
        Position commands are ignored.
        """
        self._write_word(_CW_ANGLE_LIMIT_L, 0)
        self._write_word(_CCW_ANGLE_LIMIT_L, 0)
        return ImmediateResultTask()

    def turn(self, clockwise: bool, speed: float) -> Task[()]:
        """Rotate continuously in wheel mode.

        `clockwise=True` sets the direction bit (bit 10 of moving_speed).
        """
        speed = max(0.0, min(1.0, speed))
        raw = round(speed * _SPEED_MAX)
        if clockwise:
            raw |= _DIRECTION_BIT
        self._write_word(_MOVING_SPEED_L, raw)
        return ImmediateResultTask()

    def free(self) -> Task[()]:
        self._bus.write_register(self._id, _TORQUE_ENABLE, bytes([0]))
        return ImmediateResultTask()


class AX12BusVirtual(AX12Bus):
    """Virtual twin of AX12Bus: same constructor signature, in-memory sim.

    By design, the Serial dependency stays wired even in the virtual twin so
    that a config swap (real <-> virtual) touches only the AX12 driver line.
    The Serial itself may be real or virtual — orthogonal concern. Protocol
    framing is bypassed: we simulate the register file directly.
    """

    def __init__(
        self,
        name: str,
        logger: Logger,
        thread_pool: ThreadPoolExecutor,
        bus: Serial,
        baudrate: int = _DEFAULT_BAUDRATE,
        retries: int = _DEFAULT_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
        echo: bool = _DEFAULT_ECHO,
    ):
        super().__init__(
            name,
            logger,
            thread_pool=thread_pool,
            bus=bus,
            baudrate=baudrate,
            retries=retries,
            retry_delay=retry_delay,
            echo=echo,
        )
        # servo_id -> {register_addr: byte}
        self._registers: dict[int, dict[int, int]] = {}

    def init(self) -> Task[()]:
        # Skip the parent's set_baudrate: the underlying Serial is unused
        # here, may not even be init()'d. Simulation stays pure in-memory.
        self._log.info(f"AX12BusVirtual '{self.name}' initialized")
        return ImmediateResultTask()

    def _regs(self, servo_id: int) -> dict[int, int]:
        return self._registers.setdefault(servo_id, {})

    def write_register(self, servo_id: int, register: int, data: bytes) -> Task[()]:
        regs = self._regs(servo_id)
        for offset, byte in enumerate(data):
            regs[register + offset] = byte
        return ImmediateResultTask()

    def read_register(self, servo_id: int, register: int, count: int) -> Task[bytes]:
        regs = self._regs(servo_id)
        return ImmediateResultTask(bytes(regs.get(register + i, 0) for i in range(count)))

    def _inject_word(self, servo_id: int, register: int, value: int) -> None:
        regs = self._regs(servo_id)
        regs[register] = value & 0xFF
        regs[register + 1] = (value >> 8) & 0xFF

    def inject_position(self, servo_id: int, position: int) -> None:
        """Set the simulated present position for a servo."""
        self._inject_word(servo_id, _PRESENT_POSITION_L, position)

    def inject_speed(self, servo_id: int, speed: int) -> None:
        """Set the simulated present speed (0..1023, bit 10 = direction)."""
        self._inject_word(servo_id, _PRESENT_SPEED_L, speed)

    def inject_load(self, servo_id: int, load: int) -> None:
        """Set the simulated present load (0..1023, bit 10 = direction)."""
        self._inject_word(servo_id, _PRESENT_LOAD_L, load)

    def inject_voltage(self, servo_id: int, tenths_of_volt: int) -> None:
        """Set the simulated voltage register (raw tenths-of-volt, e.g. 120 = 12 V)."""
        self._regs(servo_id)[_PRESENT_VOLTAGE] = tenths_of_volt & 0xFF

    def inject_temperature(self, servo_id: int, celsius: int) -> None:
        """Set the simulated temperature (°C)."""
        self._regs(servo_id)[_PRESENT_TEMPERATURE] = celsius & 0xFF


class AX12BusDefinition(DriverDefinition):
    """Factory for AX12Bus from config args."""

    def __init__(
        self, logger: Logger, peripherals: Registry[Peripheral], thread_pool: ThreadPoolExecutor
    ):
        # The bus itself has no user-facing commands; individual AX12 servos
        # are the command targets via their own AX12Definition.
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals
        self._thread_pool = thread_pool

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(Serial, self._peripherals))
        defn.add_optional("baudrate", ArgTypes.U32(), _DEFAULT_BAUDRATE)
        defn.add_optional("retries", ArgTypes.U32(), _DEFAULT_RETRIES)
        defn.add_optional("retry_delay", ArgTypes.F32(), _DEFAULT_RETRY_DELAY)
        defn.add_optional("echo", ArgTypes.Bool(), _DEFAULT_ECHO)
        return defn

    def create(self, args: DriverInitArgs) -> AX12Bus:
        return AX12Bus(
            name=args.get_name(),
            logger=self._logger,
            thread_pool=self._thread_pool,
            bus=args.get("bus"),
            baudrate=args.get("baudrate"),
            retries=args.get("retries"),
            retry_delay=args.get("retry_delay"),
            echo=args.get("echo"),
        )


class AX12BusVirtualDefinition(AX12BusDefinition):
    """Factory for AX12BusVirtual from config args.

    Accepts a Serial dependency for signature parity with AX12BusDefinition:
    the swap real <-> virtual must not touch any other config line.
    """

    def __init__(
        self, logger: Logger, peripherals: Registry[Peripheral], thread_pool: ThreadPoolExecutor
    ):
        super().__init__(logger, peripherals, thread_pool)

    def create(self, args: DriverInitArgs) -> AX12BusVirtual:
        return AX12BusVirtual(
            name=args.get_name(),
            logger=self._logger,
            thread_pool=self._thread_pool,
            bus=args.get("bus"),
            baudrate=args.get("baudrate"),
            retries=args.get("retries"),
            retry_delay=args.get("retry_delay"),
            echo=args.get("echo"),
        )


class AX12Definition(DriverDefinition):
    """Factory for a single AX12 servo from config args."""

    def __init__(
        self, logger: Logger, peripherals: Registry[Peripheral], thread_pool: ThreadPoolExecutor
    ):
        super().__init__(AX12.commands)
        self._logger = logger
        self._peripherals = peripherals
        self._thread_pool = thread_pool

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(AX12Bus, self._peripherals))
        defn.add_required("id", ArgTypes.U8())
        return defn

    def create(self, args: DriverInitArgs) -> AX12:
        servo_id = args.get("id")
        if servo_id == _BROADCAST_ID:
            raise ValueError(
                f"AX12 '{args.get_name()}': servo id 0x{_BROADCAST_ID:02x} is "
                "reserved for broadcast, not a real servo"
            )
        return AX12(
            name=args.get_name(),
            logger=self._logger,
            thread_pool=self._thread_pool,
            bus=args.get("bus"),
            servo_id=servo_id,
        )
