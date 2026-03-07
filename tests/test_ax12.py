"""Tests for AX12 driver using fake implementation."""

import pytest

from evo_hl.ax12.fake import AX12Fake


@pytest.fixture
def ax():
    drv = AX12Fake(device="/dev/ttyACM0")
    drv.init()
    yield drv
    drv.close()


class TestAX12Fake:
    def test_init_empty(self, ax):
        assert len(ax.servos) == 0

    def test_move_auto_registers(self, ax):
        assert ax.move(2, 200)
        assert 2 in ax.servos
        assert ax.servos[2]["position"] == 200

    def test_move_multiple_servos(self, ax):
        ax.move(2, 100)
        ax.move(3, 500)
        assert ax.get_position(2) == 100
        assert ax.get_position(3) == 500

    def test_move_out_of_range(self, ax):
        assert not ax.move(1, 1024)
        assert not ax.move(1, -1)

    def test_move_boundaries(self, ax):
        assert ax.move(1, 0)
        assert ax.move(1, 1023)

    def test_get_position_default(self, ax):
        # First access returns center (512)
        assert ax.get_position(5) == 512

    def test_set_speed(self, ax):
        assert ax.set_speed(2, 200)
        assert ax.servos[2]["speed"] == 200

    def test_free(self, ax):
        ax.move(2, 100)
        assert ax.free(2)
        assert not ax.servos[2]["torque"]

    def test_close_clears(self, ax):
        ax.move(2, 100)
        ax.close()
        assert len(ax.servos) == 0
