"""AX-12A driver: Dynamixel 1.0 protocol over serial (USB2AX).

The AX-12A is a smart servo with position feedback, communicating via
half-duplex serial using the Dynamixel 1.0 packet protocol.

Layout:
- AX12Bus (InterfaceHolder): owns the Serial bus, serializes packets,
  handles the echo-drain and checksum validation quirks.
- AX12 (SmartServo): one instance per servo ID on the bus.
- AX12BusVirtual: drop-in replacement for AX12Bus with an in-memory
  servo state dict. Same constructor signature so configs can swap.
"""

import threading
import time

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.serial import Serial
from evo_lib.interfaces.smart_servo import SmartServo
from evo_lib.logger import Logger
from evo_lib.peripheral import InterfaceHolder, Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task

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
_POSITION_CENTER = 512  # 150° — mechanical midpoint of the 0..300° range
_ANGLE_MAX = 300.0  # degrees
_SPEED_MAX = 1023
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

# Max AX-12 packet size we ever emit: 2 header + id + len + inst + reg + up to
# 2 data bytes + checksum = 9. Round up for headroom on future register writes.
_TX_BUF_SIZE = 16


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
        bus: Serial,
        baudrate: int = _DEFAULT_BAUDRATE,
        retries: int = _DEFAULT_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ):
        super().__init__(name)
        self._log = logger
        self._bus = bus
        self._baudrate = baudrate
        self._retries = retries
        self._retry_delay = retry_delay
        self._lock = threading.Lock()
        self._servos: dict[int, "AX12"] = {}
        # Reusable TX buffer (hot path): avoids per-call bytearray allocation on
        # every write/read. Safe under the bus lock — only one packet is ever
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

    def write_register(self, servo_id: int, register: int, data: bytes) -> None:
        """Send a WRITE instruction. Broadcast (0xFE) gets no status reply."""
        with self._lock:
            self._retry(lambda: self._do_write(servo_id, register, data))

    def read_register(self, servo_id: int, register: int, count: int) -> bytes:
        """Send a READ instruction and return the payload bytes."""
        with self._lock:
            return self._retry(lambda: self._do_read(servo_id, register, count))

    def _retry(self, op):
        # On failure we flush the RX buffer before retrying: a half-received
        # status packet would desync the next framing attempt. We accept the
        # cost of dropping a valid-but-late reply (timing edge case).
        attempts = 0
        while True:
            try:
                return op()
            except OSError as err:
                self._bus.reset_input_buffer()
                if attempts >= self._retries:
                    raise
                attempts += 1
                self._log.debug(
                    f"AX12Bus '{self.name}' retry {attempts}/{self._retries}: {err}"
                )
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
        """Write then discard the local echo (half-duplex USB2AX).

        Reading exactly len(packet) bytes right after the write eats the
        guaranteed echo without racing the servo's reply.
        """
        self._bus.write(packet)
        _ = self._bus.read(len(packet))

    def _read_status(self, expected_id: int) -> bytes:
        """Read and validate a Dynamixel 1.0 status packet.

        Returns the parameter bytes (excluding error and checksum).
        """
        header = self._bus.read(2)
        if header[0] != _HEADER_B0 or header[1] != _HEADER_B1:
            raise OSError(f"Dynamixel: invalid header {bytes(header)!r}")
        id_len = self._bus.read(2)
        resp_id, resp_length = id_len[0], id_len[1]
        # Detect a crossed reply (servo X answers a request addressed to Y —
        # happens after a prior timeout leaves a stale status in the buffer).
        if resp_id != expected_id:
            raise OSError(
                f"Dynamixel: crossed reply (expected id {expected_id}, got {resp_id})"
            )
        # AX-12 status packet: error + 0..N params + checksum. Minimum 2 bytes
        # (error + checksum). Below that, payload[0] and payload[-1] collide
        # and we'd silently misread the error byte. Upper bound guards against
        # a faulty servo making us block on the serial timeout.
        if resp_length < 2 or resp_length > 8:
            raise OSError(f"Dynamixel: implausible status length {resp_length}")
        payload = self._bus.read(resp_length)
        cs = resp_id + resp_length
        for b in payload[:-1]:
            cs += b
        expected = (~cs) & 0xFF
        if payload[-1] != expected:
            raise OSError(
                f"Dynamixel: bad checksum (got {payload[-1]:#x}, expected {expected:#x})"
            )
        error = payload[0]
        if error != 0:
            raise OSError(f"Dynamixel error flags: 0x{error:02x}")
        return bytes(payload[1:-1])


class AX12(SmartServo):
    """A single AX-12A servo on a Dynamixel bus.

    Bus-agnostic: works with any AX12Bus (real or virtual).
    """

    def __init__(self, name: str, logger: Logger, bus: AX12Bus, servo_id: int):
        super().__init__(name)
        self._log = logger
        self._bus = bus
        self._id = servo_id
        bus.register_servo(self)

    @property
    def servo_id(self) -> int:
        return self._id

    def init(self) -> Task[()]:
        self._bus.write_register(self._id, _TORQUE_ENABLE, bytes([1]))
        self._log.info(f"AX12 '{self.name}' (ID {self._id}) torque enabled")
        return ImmediateResultTask()

    def close(self) -> None:
        # TimeoutError is an OSError subclass in Py3, so one clause covers both.
        try:
            self._bus.write_register(self._id, _TORQUE_ENABLE, bytes([0]))
        except OSError as err:
            self._log.warning(
                f"AX12 '{self.name}' (ID {self._id}) close: torque-disable failed: {err}"
            )

    # --- Movement ---

    def move_to_angle(self, angle: float) -> Task[()]:
        angle = max(0.0, min(_ANGLE_MAX, angle))
        return self.move_to_position(round(angle / _ANGLE_MAX * _POSITION_MAX))

    def move_to_fraction(self, fraction: float) -> Task[()]:
        fraction = max(0.0, min(1.0, fraction))
        return self.move_to_position(round(fraction * _POSITION_MAX))

    def move_to_position(self, position: int) -> Task[()]:
        position = max(0, min(_POSITION_MAX, position))
        self._write_word(_GOAL_POSITION_L, position)
        return ImmediateResultTask()

    def reset(self) -> Task[()]:
        """Move to the mechanical center (150°)."""
        return self.move_to_position(_POSITION_CENTER)

    # --- Position feedback ---

    def _read_word(self, register: int) -> int:
        data = self._bus.read_register(self._id, register, 2)
        return data[0] | (data[1] << 8)

    def _write_word(self, register: int, value: int) -> None:
        self._bus.write_register(
            self._id, register, bytes([value & 0xFF, (value >> 8) & 0xFF])
        )

    def get_position(self) -> Task[int]:
        return ImmediateResultTask(self._read_word(_PRESENT_POSITION_L))

    def get_angle(self) -> Task[float]:
        return ImmediateResultTask(
            self._read_word(_PRESENT_POSITION_L) / _POSITION_MAX * _ANGLE_MAX
        )

    def get_fraction(self) -> Task[float]:
        return ImmediateResultTask(self._read_word(_PRESENT_POSITION_L) / _POSITION_MAX)

    # --- Speed ---

    def set_speed(self, speed: float) -> Task[()]:
        speed = max(0.0, min(1.0, speed))
        self._write_word(_MOVING_SPEED_L, round(speed * _SPEED_MAX))
        return ImmediateResultTask()

    def get_speed(self) -> Task[int]:
        """Present speed as a signed magnitude in [-1023, 1023].

        Per Dynamixel datasheet, bit 10 of present_speed is 1 = CW, 0 = CCW;
        bits 0-9 are the magnitude. Decoded here with CCW-positive convention
        (bit 10 set -> negative), matching the trigonometric direct sense used
        by Position/Pose. Callers who want a fraction divide by 1023.
        """
        return ImmediateResultTask(_decode_signed(self._read_word(_PRESENT_SPEED_L)))

    # --- Load (motor current) ---

    def get_load(self) -> Task[int]:
        """Present load as a signed magnitude in [-1023, 1023].

        Same encoding as present_speed (CCW-positive): positive = CCW torque,
        negative = CW torque. Useful for grip detection via |load| — stall
        magnitude rises on catch regardless of direction. Callers who want a
        fraction divide by 1023.
        """
        return ImmediateResultTask(_decode_signed(self._read_word(_PRESENT_LOAD_L)))

    # --- Diagnostics ---

    def get_voltage(self) -> Task[float]:
        """Present voltage in volts (register is tenths of a volt)."""
        data = self._bus.read_register(self._id, _PRESENT_VOLTAGE, 1)
        return ImmediateResultTask(data[0] / 10.0)

    def get_temperature(self) -> Task[int]:
        """Present temperature in °C (internal sensor, shutdown ~70°C)."""
        data = self._bus.read_register(self._id, _PRESENT_TEMPERATURE, 1)
        return ImmediateResultTask(data[0])

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
        bus: Serial,
        baudrate: int = _DEFAULT_BAUDRATE,
        retries: int = _DEFAULT_RETRIES,
        retry_delay: float = _DEFAULT_RETRY_DELAY,
    ):
        super().__init__(
            name, logger, bus, baudrate=baudrate, retries=retries, retry_delay=retry_delay
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

    def write_register(self, servo_id: int, register: int, data: bytes) -> None:
        regs = self._regs(servo_id)
        for offset, byte in enumerate(data):
            regs[register + offset] = byte

    def read_register(self, servo_id: int, register: int, count: int) -> bytes:
        regs = self._regs(servo_id)
        return bytes(regs.get(register + i, 0) for i in range(count))

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

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(Serial, self._peripherals))
        defn.add_optional("baudrate", ArgTypes.U32(), _DEFAULT_BAUDRATE)
        defn.add_optional("retries", ArgTypes.U32(), _DEFAULT_RETRIES)
        defn.add_optional("retry_delay", ArgTypes.F32(), _DEFAULT_RETRY_DELAY)
        return defn

    def create(self, args: DriverInitArgs) -> AX12Bus:
        return AX12Bus(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("bus"),
            baudrate=args.get("baudrate"),
            retries=args.get("retries"),
            retry_delay=args.get("retry_delay"),
        )


class AX12BusVirtualDefinition(DriverDefinition):
    """Factory for AX12BusVirtual from config args.

    Accepts a Serial dependency for signature parity with AX12BusDefinition:
    the swap real <-> virtual must not touch any other config line.
    """

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("bus", ArgTypes.Component(Serial, self._peripherals))
        defn.add_optional("baudrate", ArgTypes.U32(), _DEFAULT_BAUDRATE)
        defn.add_optional("retries", ArgTypes.U32(), _DEFAULT_RETRIES)
        defn.add_optional("retry_delay", ArgTypes.F32(), _DEFAULT_RETRY_DELAY)
        return defn

    def create(self, args: DriverInitArgs) -> AX12BusVirtual:
        return AX12BusVirtual(
            name=args.get_name(),
            logger=self._logger,
            bus=args.get("bus"),
            baudrate=args.get("baudrate"),
            retries=args.get("retries"),
            retry_delay=args.get("retry_delay"),
        )


class AX12Definition(DriverDefinition):
    """Factory for a single AX12 servo from config args."""

    def __init__(self, logger: Logger, peripherals: Registry[Peripheral]):
        super().__init__()
        self._logger = logger
        self._peripherals = peripherals

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
            bus=args.get("bus"),
            servo_id=servo_id,
        )
