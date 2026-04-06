"""Tests for serial virtual implementation."""

import threading

import pytest

from evo_lib.drivers.serial.virtual import SerialVirtual


class TestSerialVirtual:
    def test_write_records_data(self):
        bus = SerialVirtual()
        bus.init()
        bus.write(b"\x01\x02")
        bus.write(b"\x03")
        assert bus.written == [b"\x01\x02", b"\x03"]

    def test_read_consumes_injected_data(self):
        bus = SerialVirtual()
        bus.init()
        bus.inject_read(b"\xaa\xbb\xcc")
        result = bus.read(2)
        assert result == b"\xaa\xbb"
        assert bus.in_waiting == 1

    def test_read_available_returns_all(self):
        bus = SerialVirtual()
        bus.init()
        bus.inject_read(b"\x01\x02\x03")
        result = bus.read_available()
        assert result == b"\x01\x02\x03"
        assert bus.in_waiting == 0

    def test_read_available_empty(self):
        bus = SerialVirtual()
        bus.init()
        assert bus.read_available() == b""

    def test_read_timeout_raises(self):
        bus = SerialVirtual(timeout=0.05)
        bus.init()
        with pytest.raises(TimeoutError):
            bus.read(1)

    def test_read_blocks_until_data_injected(self):
        bus = SerialVirtual(timeout=2.0)
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
        bus = SerialVirtual()
        with pytest.raises(RuntimeError):
            bus.write(b"\x00")

    def test_in_waiting(self):
        bus = SerialVirtual()
        bus.init()
        assert bus.in_waiting == 0
        bus.inject_read(b"\x01\x02")
        assert bus.in_waiting == 2
