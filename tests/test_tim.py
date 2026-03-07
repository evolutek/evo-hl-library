"""Tests for SICK TIM driver using fake implementation."""

import pytest

from evo_hl.tim.fake import TimFake


@pytest.fixture
def tim():
    drv = TimFake(ip="192.168.1.1", port=2112, pos_x=0.0, pos_y=0.0, angle=0.0)
    drv.init()
    yield drv
    drv.close()


class TestTimFake:
    def test_initial_state(self, tim):
        assert tim.scanning is False
        assert tim.get_robots() == []

    def test_start_stop_scanning(self, tim):
        tim.start_scanning()
        assert tim.scanning is True
        tim.stop_scanning()
        assert tim.scanning is False

    def test_inject_robots(self, tim):
        robots = [(500.0, 1000.0), (1500.0, 2000.0)]
        tim.inject_robots(robots)
        assert tim.get_robots() == robots

    def test_get_robots_returns_copy(self, tim):
        tim.inject_robots([(100.0, 200.0)])
        result = tim.get_robots()
        result.append((300.0, 400.0))
        assert tim.get_robots() == [(100.0, 200.0)]

    def test_close_clears(self, tim):
        tim.inject_robots([(1.0, 2.0)])
        tim.start_scanning()
        tim.close()
        assert tim.scanning is False
        assert tim.get_robots() == []

    def test_params_stored(self, tim):
        assert tim.ip == "192.168.1.1"
        assert tim.port == 2112
        assert tim.pos_x == 0.0
        assert tim.beacon_radius == 100.0

    def test_custom_params(self):
        drv = TimFake(
            ip="10.0.0.1", port=3000,
            pos_x=100.0, pos_y=200.0, angle=45.0,
            min_shape_size=5, max_distance=80.0, beacon_radius=150.0,
        )
        assert drv.min_shape_size == 5
        assert drv.max_distance == 80.0
        assert drv.beacon_radius == 150.0
