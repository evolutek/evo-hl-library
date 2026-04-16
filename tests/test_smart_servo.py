"""Tests for AX-12A smart servo drivers."""

import pytest

from evo_lib.drivers.serial.virtual import SerialVirtual
from evo_lib.drivers.smart_servo.ax12 import AX12, AX12Bus, AX12BusVirtual, _checksum
from evo_lib.drivers.smart_servo.virtual import SmartServoVirtual
from evo_lib.logger import Logger


@pytest.fixture
def log():
    return Logger("test")


def _status_packet(servo_id: int, *params: int) -> bytes:
    """Build a Dynamixel 1.0 status packet (error=0) for inject_read()."""
    length = len(params) + 2
    cs = _checksum(servo_id, length, 0, *params)
    return bytes([0xFF, 0xFF, servo_id, length, 0, *params, cs])


def _write_packet(servo_id: int, register: int, data: bytes) -> bytes:
    """Rebuild the WRITE packet the driver sends, to assert on serial.written."""
    length = len(data) + 3
    params = [0x03, register, *data]
    cs = _checksum(servo_id, length, *params)
    return bytes([0xFF, 0xFF, servo_id, length, *params, cs])


def _read_packet(servo_id: int, register: int, count: int) -> bytes:
    """Rebuild the READ packet the driver sends, to assert on serial.written."""
    length = 4
    params = [0x02, register, count]
    cs = _checksum(servo_id, length, *params)
    return bytes([0xFF, 0xFF, servo_id, length, *params, cs])


class TestSmartServoVirtual:
    def test_angle_moves_position_and_clamps(self, log):
        # Covers: 300°/1023 scaling, position clamp at the upper bound,
        # and get_position readback in one shot.
        servo = SmartServoVirtual("ax0", log)
        servo.init()
        servo.move_to_angle(600.0).wait()  # overshoots 300° → clamps to 1023
        (pos,) = servo.get_position().wait()
        assert pos == 1023


class TestAX12BusFraming:
    """Exercise the real AX12Bus protocol layer against SerialVirtual.

    Default mode is echo=False, which matches the USB2AX dongle used on
    the robot: the dongle does not mirror TX onto RX. One dedicated test
    covers the echo=True path for USB2Dynamixel-style dongles.
    """

    def _make(self, log, **kwargs):
        serial = SerialVirtual("serial", log)
        serial.init()
        bus = AX12Bus("ax_bus", log, serial, **kwargs)
        bus.init()
        return serial, bus

    def test_write_register_frames_and_reads_status(self, log):
        serial, bus = self._make(log)
        serial.inject_read(_status_packet(2))
        bus.write_register(2, 24, bytes([1]))
        assert serial.written == [_write_packet(2, 24, bytes([1]))]

    def test_read_register_parses_status(self, log):
        serial, bus = self._make(log)
        serial.inject_read(_status_packet(2, 0x00, 0x02))
        assert bus.read_register(2, 36, 2) == b"\x00\x02"

    def test_bad_checksum_resyncs_and_raises(self, log):
        serial, bus = self._make(log, retries=0)
        bad = bytearray(_status_packet(2, 0x00, 0x02))
        bad[-1] ^= 0xFF
        serial.inject_read(bytes(bad) + b"\xde\xad\xbe\xef")
        with pytest.raises(OSError, match="checksum"):
            bus.read_register(2, 36, 2)
        assert serial.in_waiting == 0

    def test_broadcast_skips_status_read(self, log):
        serial, bus = self._make(log)
        bus.write_register(0xFE, 24, bytes([0]))
        assert serial.written == [_write_packet(0xFE, 24, bytes([0]))]

    def test_echo_mode_drains_local_echo(self, log):
        # USB2Dynamixel-style dongles mirror the TX packet onto RX before
        # the servo's reply. With echo=True, the bus must consume that
        # mirror instead of mistaking it for the status reply.
        serial, bus = self._make(log, echo=True)
        echo = _write_packet(2, 24, bytes([1]))
        serial.inject_read(echo + _status_packet(2))
        bus.write_register(2, 24, bytes([1]))
        assert serial.written == [echo]

    def test_init_sets_baudrate_on_underlying_serial(self, log):
        serial = SerialVirtual("serial", log)
        serial.init()
        bus = AX12Bus("ax_bus", log, serial, baudrate=500_000)
        bus.init()
        assert serial._baudrate == 500_000

    def test_servo_error_flags_raise(self, log):
        serial, bus = self._make(log, retries=0)
        # Status packet with error byte = 0x04 (overload).
        params = [0x04]
        length = len(params) + 1
        cs = _checksum(2, length, *params)
        packet = bytes([0xFF, 0xFF, 2, length, *params, cs])
        serial.inject_read(packet)
        with pytest.raises(OSError, match="0x04"):
            bus.read_register(2, 36, 2)

    def test_retry_recovers_after_transient_failure(self, log, monkeypatch):
        # Drive the retry path directly: the serial mock state after failure +
        # reset_input_buffer is hard to stage realistically in a single test.
        serial, bus = self._make(log, retries=1, retry_delay=0.0)
        calls = [0]

        def flaky(servo_id, register, count):
            calls[0] += 1
            if calls[0] == 1:
                raise OSError("transient")
            return b"\x00\x02"

        monkeypatch.setattr(bus, "_do_read", flaky)
        assert bus.read_register(2, 36, 2) == b"\x00\x02"
        assert calls[0] == 2


class TestAX12WithVirtualBus:
    """AX12 against the AX12BusVirtual twin — end-to-end without serial."""

    def _bus(self, log):
        bus = AX12BusVirtual("ax_bus", log, SerialVirtual("serial", log))
        bus.init()
        return bus

    def test_move_writes_goal_and_inject_position_readback(self, log):
        # Covers the write-word / read-word roundtrip through the virtual bus
        # and the inject_position sim hook. `reset()` is a thin wrapper over
        # move_to_position — redundant to test separately.
        bus = self._bus(log)
        servo = AX12("doigt", log, bus, servo_id=3)

        servo.move_to_position(512).wait()
        assert bus.read_register(3, 30, 2) == b"\x00\x02"

        bus.inject_position(3, 800)
        (pos,) = servo.get_position().wait()
        assert pos == 800

    def test_registered_in_subcomponents(self, log):
        bus = self._bus(log)
        s2 = AX12("doigt1", log, bus, servo_id=2)
        s3 = AX12("doigt2", log, bus, servo_id=3)
        assert set(bus.get_subcomponents()) == {s2, s3}

    def test_duplicate_servo_id_warns(self, log, capsys):
        bus = self._bus(log)
        AX12("first", log, bus, servo_id=5)
        AX12("second", log, bus, servo_id=5)
        assert "duplicate servo id 5" in capsys.readouterr().err

    def test_load_signed_magnitude_from_direction_bit(self, log):
        # CCW (bit 10) flips sign; magnitude = bits 0-9 raw. Same decoding
        # would apply to get_speed — covering one side is enough.
        bus = self._bus(log)
        servo = AX12("s", log, bus, servo_id=1)
        bus.inject_load(1, 0x400 | 511)
        (load,) = servo.get_load().wait()
        assert load == -511

    def test_voltage_decodes_tenths_of_volt(self, log):
        bus = self._bus(log)
        servo = AX12("s", log, bus, servo_id=1)
        bus.inject_voltage(1, 120)
        (v,) = servo.get_voltage().wait()
        assert v == pytest.approx(12.0)

    def test_temperature_raw_celsius(self, log):
        bus = self._bus(log)
        servo = AX12("s", log, bus, servo_id=1)
        bus.inject_temperature(1, 42)
        (t,) = servo.get_temperature().wait()
        assert t == 42

    def test_mode_switch_updates_angle_limits(self, log):
        # wheel: CW=0, CCW=0 (continuous). joint: CW=0, CCW=1023 (full range).
        bus = self._bus(log)
        servo = AX12("s", log, bus, servo_id=1)
        servo.mode_wheel().wait()
        assert bus.read_register(1, 6, 2) == b"\x00\x00"
        assert bus.read_register(1, 8, 2) == b"\x00\x00"
        servo.mode_joint().wait()
        assert bus.read_register(1, 8, 2) == bytes([1023 & 0xFF, 1023 >> 8])

    def test_turn_sets_direction_bit(self, log):
        bus = self._bus(log)
        servo = AX12("s", log, bus, servo_id=1)
        servo.turn(clockwise=True, speed=0.5).wait()
        raw = bus.read_register(1, 32, 2)
        value = raw[0] | (raw[1] << 8)
        assert value & 0x400
        assert (value & 0x3FF) == round(0.5 * 1023)
