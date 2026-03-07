"""Tests for MCP23017 driver using fake implementation."""

import pytest

from evo_hl.mcp23017.fake import MCP23017Fake


@pytest.fixture
def gpio():
    drv = MCP23017Fake(address=0x20)
    drv.init()
    yield drv
    drv.close()


class TestMCP23017Fake:
    def test_setup_output(self, gpio):
        gpio.setup_pin(0, output=True, default=True)
        assert gpio.read(0) is True

    def test_setup_input(self, gpio):
        gpio.setup_pin(5, output=False)
        assert gpio.read(5) is False

    def test_write_output(self, gpio):
        gpio.setup_pin(3, output=True)
        gpio.write(3, True)
        assert gpio.read(3) is True

    def test_write_input_raises(self, gpio):
        gpio.setup_pin(7, output=False)
        with pytest.raises(ValueError, match="input"):
            gpio.write(7, True)

    def test_inject_input(self, gpio):
        gpio.setup_pin(10, output=False)
        gpio.inject_input(10, True)
        assert gpio.read(10) is True

    def test_read_unconfigured_raises(self, gpio):
        with pytest.raises(ValueError, match="not configured"):
            gpio.read(0)

    def test_bad_pin(self, gpio):
        with pytest.raises(ValueError):
            gpio.setup_pin(16, output=True)

    def test_close_clears(self, gpio):
        gpio.setup_pin(0, output=True)
        gpio.close()
        assert len(gpio.pins) == 0
