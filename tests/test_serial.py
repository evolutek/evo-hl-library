"""Tests for serial virtual implementation."""

import threading

import pytest

from evo_lib.drivers.serial.rpi import RpiSerialVirtual
from evo_lib.drivers.serial.virtual import SerialVirtual
from evo_lib.logger import Logger


@pytest.fixture
def bus():
    drv = SerialVirtual(name="test", logger=Logger("test"))
    drv.init()
    yield drv
    drv.close()


@pytest.fixture
def short_timeout_bus():
    drv = SerialVirtual(name="test", logger=Logger("test"), timeout=0.05)
    drv.init()
    yield drv
    drv.close()


class TestSerialVirtual:
    def test_write_records_data(self, bus):
        bus.write(b"\x01\x02")
        bus.write(b"\x03")
        assert bus.written == [b"\x01\x02", b"\x03"]

    def test_read_consumes_injected_data(self, bus):
        bus.inject_read(b"\xaa\xbb\xcc")
        result = bus.read(2)
        assert result == b"\xaa\xbb"
        assert bus.in_waiting == 1

    def test_read_available_returns_all(self, bus):
        bus.inject_read(b"\x01\x02\x03")
        result = bus.read_available()
        assert result == b"\x01\x02\x03"
        assert bus.in_waiting == 0

    def test_read_available_empty(self, bus):
        assert bus.read_available() == b""

    def test_read_timeout_raises(self, short_timeout_bus):
        with pytest.raises(TimeoutError):
            short_timeout_bus.read(1)

    def test_read_blocks_until_data_injected(self):
        bus = SerialVirtual(name="test", logger=Logger("test"), timeout=2.0)
        bus.init()

        result = []

        def reader():
            result.append(bus.read(3))

        t = threading.Thread(target=reader)
        t.start()
        bus.inject_read(b"\x01\x02\x03")
        t.join(timeout=2.0)

        assert not t.is_alive()
        assert result == [b"\x01\x02\x03"]

    def test_not_opened_raises(self):
        drv = SerialVirtual(name="test", logger=Logger("test"))
        with pytest.raises(RuntimeError):
            drv.write(b"\x00")

    def test_in_waiting(self, bus):
        assert bus.in_waiting == 0
        bus.inject_read(b"\x01\x02")
        assert bus.in_waiting == 2

    def test_reset_input_buffer_discards_pending(self, bus):
        bus.inject_read(b"\xde\xad\xbe\xef")
        assert bus.in_waiting == 4
        bus.reset_input_buffer()
        assert bus.in_waiting == 0
        assert bus.read_available() == b""

    def test_reset_input_buffer_forces_reader_to_rewait(self):
        # A concurrent reader must not be woken up by a stale event
        # set before reset_input_buffer() was called.
        bus = SerialVirtual(name="test", logger=Logger("test"), timeout=0.2)
        bus.init()
        bus.inject_read(b"\x01")  # sets _read_event
        bus.reset_input_buffer()  # must also clear _read_event

        error: list[BaseException] = []

        def reader():
            try:
                bus.read(1)
            except BaseException as e:
                error.append(e)

        t = threading.Thread(target=reader)
        t.start()
        t.join(timeout=1.0)
        bus.close()

        assert not t.is_alive()
        assert len(error) == 1
        assert isinstance(error[0], TimeoutError)

    def test_set_baudrate_records_value(self, bus):
        bus.set_baudrate(1_000_000)
        assert bus._baudrate == 1_000_000


class TestRpiSerialVirtual:
    def test_roundtrip_via_delegate(self):
        # Constructor must accept the same args as RpiSerial, and the
        # inject_read / written helpers must be delegated from SerialVirtual.
        drv = RpiSerialVirtual(
            name="test", logger=Logger("test"), port="/dev/null", baudrate=115200
        )
        drv.init()
        drv.write(b"\xa0")
        drv.inject_read(b"\x55")
        assert drv.read(1) == b"\x55"
        assert drv.written == [b"\xa0"]
        drv.close()

    def test_set_baudrate_propagates_to_inner(self):
        drv = RpiSerialVirtual(
            name="test", logger=Logger("test"), port="/dev/null", baudrate=115200
        )
        drv.init()
        drv.set_baudrate(500_000)
        assert drv._baudrate == 500_000
        assert drv._inner._baudrate == 500_000
        drv.close()
