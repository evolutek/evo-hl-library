"""Tests for AX-12A smart servo drivers."""

import math

import pytest

from evo_lib.drivers.serial.virtual import SerialVirtual
from evo_lib.drivers.smart_servo.ax12 import (
    _MOVING,
    AX12,
    AngleLimitError,
    AX12Bus,
    AX12BusVirtual,
    DynamixelBusError,
    InputVoltageError,
    InstructionError,
    OverheatingError,
    OverloadError,
    PacketChecksumError,
    RangeError,
    StalledError,
    _checksum,
)
from evo_lib.interfaces.smart_servo import ServoAngleUnit, ServoSpeedUnit
from evo_lib.logger import Logger
from evo_lib.scheduler import Scheduler
from evo_lib.thread_pool import ThreadPoolExecutor


@pytest.fixture
def log():
    return Logger("test")


@pytest.fixture
def thread_pool(log):
    pool = ThreadPoolExecutor(log)
    yield pool
    pool.stop()


@pytest.fixture
def scheduler(log):
    return Scheduler(log)


def _status_packet(servo_id: int, *params: int) -> bytes:
    length = len(params) + 2
    cs = _checksum(servo_id, length, 0, *params)
    return bytes([0xFF, 0xFF, servo_id, length, 0, *params, cs])


def _write_packet(servo_id: int, register: int, data: bytes) -> bytes:
    length = len(data) + 3
    params = [0x03, register, *data]
    cs = _checksum(servo_id, length, *params)
    return bytes([0xFF, 0xFF, servo_id, length, *params, cs])


class TestAX12BusFraming:
    def _make(self, log, scheduler, thread_pool, **kwargs):
        serial = SerialVirtual("serial", log)
        serial.init()
        bus = AX12Bus("ax_bus", log, scheduler, thread_pool, serial, **kwargs)
        bus.init()
        return serial, bus

    def test_write_register_frames_and_reads_status(self, log, scheduler, thread_pool):
        serial, bus = self._make(log, scheduler, thread_pool)
        serial.inject_read(_status_packet(2))
        bus.write_register(2, 24, bytes([1])).wait(timeout=1.0)
        assert serial.written == [_write_packet(2, 24, bytes([1]))]

    def test_read_register_parses_status(self, log, scheduler, thread_pool):
        serial, bus = self._make(log, scheduler, thread_pool)
        serial.inject_read(_status_packet(2, 0x00, 0x02))
        (data,) = bus.read_register(2, 36, 2).wait(timeout=1.0)
        assert data == b"\x00\x02"

    def test_bad_checksum_resyncs_and_raises(self, log, scheduler, thread_pool):
        serial, bus = self._make(log, scheduler, thread_pool, retries=0)
        bad = bytearray(_status_packet(2, 0x00, 0x02))
        bad[-1] ^= 0xFF
        serial.inject_read(bytes(bad) + b"\xde\xad\xbe\xef")
        with pytest.raises(DynamixelBusError, match="checksum"):
            bus.read_register(2, 36, 2).wait(timeout=1.0)
        assert serial.in_waiting == 0

    def test_broadcast_skips_status_read(self, log, scheduler, thread_pool):
        serial, bus = self._make(log, scheduler, thread_pool)
        bus.write_register(0xFE, 24, bytes([0])).wait(timeout=1.0)
        assert serial.written == [_write_packet(0xFE, 24, bytes([0]))]

    def test_echo_mode_drains_local_echo(self, log, scheduler, thread_pool):
        serial, bus = self._make(log, scheduler, thread_pool, echo=True)
        echo = _write_packet(2, 24, bytes([1]))
        serial.inject_read(echo + _status_packet(2))
        bus.write_register(2, 24, bytes([1])).wait(timeout=1.0)
        assert serial.written == [echo]

    def test_init_sets_baudrate_on_underlying_serial(self, log, scheduler, thread_pool):
        serial = SerialVirtual("serial", log)
        serial.init()
        bus = AX12Bus("ax_bus", log, scheduler, thread_pool, serial, baudrate=500_000)
        bus.init()
        assert serial._baudrate == 500_000

    def _inject_error_status(self, serial, servo_id: int, error_byte: int) -> None:
        length = 2
        cs = _checksum(servo_id, length, error_byte)
        serial.inject_read(bytes([0xFF, 0xFF, servo_id, length, error_byte, cs]))

    @pytest.mark.parametrize(
        "error_byte,exc_type",
        [
            (0x01, InputVoltageError),
            (0x02, AngleLimitError),
            (0x04, OverheatingError),
            (0x08, RangeError),
            (0x10, PacketChecksumError),
            (0x20, OverloadError),
            (0x40, InstructionError),
        ],
    )
    def test_servo_error_flags_decode_to_typed_exceptions(
        self, log, scheduler, thread_pool, error_byte, exc_type
    ):
        serial, bus = self._make(log, scheduler, thread_pool, retries=0)
        self._inject_error_status(serial, 2, error_byte)
        with pytest.raises(exc_type) as excinfo:
            bus.read_register(2, 36, 2).wait(timeout=1.0)
        assert excinfo.value.error_byte == error_byte
        assert excinfo.value.servo_id == 2

    def test_servo_error_not_retried(self, log, scheduler, thread_pool, monkeypatch):
        serial, bus = self._make(log, scheduler, thread_pool, retries=3, retry_delay=0.0)
        calls = [0]

        def flaky(servo_id, register, count):
            calls[0] += 1
            raise AngleLimitError(servo_id, 0x02)

        monkeypatch.setattr(bus, "_do_read", flaky)
        with pytest.raises(AngleLimitError):
            bus.read_register(2, 36, 2).wait(timeout=1.0)
        assert calls[0] == 1

    def test_packet_checksum_error_is_retried(self, log, scheduler, thread_pool, monkeypatch):
        serial, bus = self._make(log, scheduler, thread_pool, retries=2, retry_delay=0.0)
        calls = [0]

        def flaky(servo_id, register, count):
            calls[0] += 1
            if calls[0] < 2:
                raise PacketChecksumError(servo_id, 0x10)
            return b"\x00\x02"

        monkeypatch.setattr(bus, "_do_read", flaky)
        (data,) = bus.read_register(2, 36, 2).wait(timeout=1.0)
        assert data == b"\x00\x02"
        assert calls[0] == 2

    def test_retry_recovers_after_transient_failure(self, log, scheduler, thread_pool, monkeypatch):
        serial, bus = self._make(log, scheduler, thread_pool, retries=1, retry_delay=0.0)
        calls = [0]

        def flaky(servo_id, register, count):
            calls[0] += 1
            if calls[0] == 1:
                raise OSError("transient")
            return b"\x00\x02"

        monkeypatch.setattr(bus, "_do_read", flaky)
        (data,) = bus.read_register(2, 36, 2).wait(timeout=1.0)
        assert data == b"\x00\x02"
        assert calls[0] == 2


class TestAX12WithVirtualBus:
    def _bus(self, log, thread_pool):
        bus = AX12BusVirtual(
            "ax_bus", log, Scheduler(log), thread_pool, SerialVirtual("serial", log)
        )
        bus.init()
        return bus

    def test_signature_parity_real_vs_virtual(self, log, scheduler, thread_pool):
        # Real <-> virtual swap must stay a one-line config change.
        serial = SerialVirtual("serial", log)
        serial.init()
        real = AX12Bus("real", log, scheduler, thread_pool, serial)
        virtual = AX12BusVirtual("virtual", log, scheduler, thread_pool, serial)
        assert real._baudrate == virtual._baudrate
        assert real._retries == virtual._retries

    @pytest.mark.parametrize(
        "unit,position,expected_raw",
        [
            (ServoAngleUnit.NATIVE, 512, 512),
            (ServoAngleUnit.DEGREES, 150.0, 512),
            (ServoAngleUnit.RADIANS, math.pi, 614),
            (ServoAngleUnit.FRACTION, 0.5, 512),
        ],
    )
    def test_move_to_writes_goal_position(
        self, log, thread_pool, unit, position, expected_raw
    ):
        bus = self._bus(log, thread_pool)
        servo = AX12("doigt", log, thread_pool, bus, servo_id=3)
        servo.move_to(position, unit, wait_multiplier=0).wait(timeout=1.0)
        (data,) = bus.read_register(3, 30, 2).wait(timeout=1.0)
        raw = data[0] | (data[1] << 8)
        assert raw == expected_raw

    def test_inject_position_round_trips_through_get_position(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=3)
        bus.inject_position(3, 800)
        (pos,) = servo.get_position(ServoAngleUnit.NATIVE).wait(timeout=1.0)
        assert pos == 800

    def test_sync_move_returns_when_position_reaches_target(self, log, thread_pool):
        # Pre-injected present_position == goal → poll loop terminates instantly.
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=3, goal_reached_tolerance=10)
        bus.inject_position(3, 500)
        task = servo.move_to(500, ServoAngleUnit.NATIVE, wait_multiplier=1.0)
        task.wait(timeout=1.0)
        assert task.is_done()

    def test_sync_move_skipped_when_wait_multiplier_zero(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=3)
        task = servo.move_to(500, ServoAngleUnit.NATIVE, wait_multiplier=0)
        assert task.is_done()

    def test_wait_raises_stalled_when_servo_reports_not_moving(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=3, poll_frequency=200)
        bus.inject_position(3, 100)
        bus.write_register(3, _MOVING, bytes([0])).wait(timeout=1.0)
        task = servo.move_to(500, ServoAngleUnit.NATIVE, wait_multiplier=1.0)
        with pytest.raises(StalledError):
            task.wait(timeout=1.0)

    def test_close_event_aborts_wait(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=3, poll_frequency=10)
        bus.inject_position(3, 100)
        bus.write_register(3, _MOVING, bytes([1])).wait(timeout=1.0)
        task = servo.move_to(500, ServoAngleUnit.NATIVE, wait_multiplier=1.0)
        bus.close()
        task.wait(timeout=1.0)
        assert task.is_done()

    def test_registered_in_subcomponents(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        s2 = AX12("doigt1", log, thread_pool, bus, servo_id=2)
        s3 = AX12("doigt2", log, thread_pool, bus, servo_id=3)
        assert set(bus.get_subcomponents()) == {s2, s3}

    def test_duplicate_servo_id_warns(self, log, thread_pool, capsys):
        bus = self._bus(log, thread_pool)
        AX12("first", log, thread_pool, bus, servo_id=5)
        AX12("second", log, thread_pool, bus, servo_id=5)
        assert "duplicate servo id 5" in capsys.readouterr().err

    def test_load_signed_magnitude_from_direction_bit(self, log, thread_pool):
        # Bit 10 = sign; same encoding as get_speed — covering one is enough.
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=1)
        bus.inject_load(1, 0x400 | 511)
        (load,) = servo.get_load().wait(timeout=1.0)
        assert load == -511

    @pytest.mark.parametrize(
        "unit,raw,expected",
        [
            (ServoSpeedUnit.NATIVE, 60, 60),
            (ServoSpeedUnit.RPM, 60, 60 * 114 / 1023),
            (ServoSpeedUnit.DEGREES_PER_SECOND, 60, 60 * 114 / 1023 * 360 / 60),
            (ServoSpeedUnit.RADIANS_PER_SECOND, 60, 60 * 114 / 1023 * 2 * math.pi / 60),
        ],
    )
    def test_get_speed_unit_conversions(self, log, thread_pool, unit, raw, expected):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=1)
        bus.inject_speed(1, raw)
        (speed,) = servo.get_speed(unit).wait(timeout=1.0)
        assert speed == pytest.approx(expected)

    def test_voltage_decodes_tenths_of_volt(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=1)
        bus.inject_voltage(1, 120)
        (v,) = servo.get_voltage().wait(timeout=1.0)
        assert v == pytest.approx(12.0)

    def test_temperature_raw_celsius(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=1)
        bus.inject_temperature(1, 42)
        (t,) = servo.get_temperature().wait(timeout=1.0)
        assert t == 42

    def test_mode_switch_updates_angle_limits(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=1)
        servo.mode_wheel().wait(timeout=1.0)
        (cw,) = bus.read_register(1, 6, 2).wait(timeout=1.0)
        (ccw,) = bus.read_register(1, 8, 2).wait(timeout=1.0)
        assert cw == b"\x00\x00" and ccw == b"\x00\x00"
        servo.mode_joint().wait(timeout=1.0)
        (ccw,) = bus.read_register(1, 8, 2).wait(timeout=1.0)
        assert ccw == bytes([1023 & 0xFF, 1023 >> 8])

    def test_init_does_no_bus_io(self, log, thread_pool, monkeypatch):
        # 12V rail may be down at boot — init() must stay silent on the bus.
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=42)

        def boom(servo_id, register, data):
            raise AssertionError("init() must not write to the bus")

        monkeypatch.setattr(bus, "write_register", boom)
        servo.init().wait(timeout=1.0)

    def test_enable_writes_torque_register(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=7)
        servo.enable().wait(timeout=1.0)
        (data,) = bus.read_register(7, 24, 1).wait(timeout=1.0)
        assert data == b"\x01"

    def test_turn_sets_direction_bit(self, log, thread_pool):
        bus = self._bus(log, thread_pool)
        servo = AX12("s", log, thread_pool, bus, servo_id=1)
        servo.turn(clockwise=True, speed=0.5).wait(timeout=1.0)
        (data,) = bus.read_register(1, 32, 2).wait(timeout=1.0)
        value = data[0] | (data[1] << 8)
        assert value & 0x400
        assert (value & 0x3FF) == round(0.5 * 1023)
