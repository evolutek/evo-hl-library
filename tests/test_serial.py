"""Tests for serial bus virtual implementation."""

import threading

import pytest

from evo_lib.drivers.serial.virtual import SerialBusVirtual


class TestSerialBusVirtual:
    def test_write_records_data(self):
        bus = SerialBusVirtual()
        bus.open()
        bus.write(b"\x01\x02")
        bus.write(b"\x03")
        assert bus.written == [b"\x01\x02", b"\x03"]

    def test_read_consumes_injected_data(self):
        bus = SerialBusVirtual()
        bus.open()
        bus.inject_read(b"\xaa\xbb\xcc")
        result = bus.read(2)
        assert result == b"\xaa\xbb"
        assert bus.in_waiting == 1

    def test_read_available_returns_all(self):
        bus = SerialBusVirtual()
        bus.open()
        bus.inject_read(b"\x01\x02\x03")
        result = bus.read_available()
        assert result == b"\x01\x02\x03"
        assert bus.in_waiting == 0

    def test_read_available_empty(self):
        bus = SerialBusVirtual()
        bus.open()
        assert bus.read_available() == b""

    def test_read_timeout_raises(self):
        bus = SerialBusVirtual(timeout=0.05)
        bus.open()
        with pytest.raises(TimeoutError):
            bus.read(1)

    def test_read_blocks_until_data_injected(self):
        bus = SerialBusVirtual(timeout=2.0)
        bus.open()

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
        bus = SerialBusVirtual()
        with pytest.raises(RuntimeError):
            bus.write(b"\x00")

    def test_in_waiting(self):
        bus = SerialBusVirtual()
        bus.open()
        assert bus.in_waiting == 0
        bus.inject_read(b"\x01\x02")
        assert bus.in_waiting == 2
