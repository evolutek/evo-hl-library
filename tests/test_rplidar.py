"""Tests for RPLidar driver using fake implementation."""

import math

import pytest

from evo_lib.drivers.rplidar.fake import RPLidarFake
from evo_lib.interfaces.lidar import Lidar2DMeasure


@pytest.fixture
def lidar():
    drv = RPLidarFake(name="test-lidar")
    drv.init()
    yield drv
    drv.close()


def _make_measure(angle_deg: float = 0.0, distance: float = 100.0, quality: float = 50.0):
    return Lidar2DMeasure(
        angle=math.radians(angle_deg),
        distance=distance,
        timestamp=0.0,
        quality=quality,
    )


class TestRPLidarFake:
    def test_initial_state(self, lidar):
        assert lidar.scanning is False
        assert list(lidar.iter()) == []

    def test_start_stop(self, lidar):
        lidar.start().wait()
        assert lidar.scanning is True
        lidar.stop().wait()
        assert lidar.scanning is False

    def test_inject_measures(self, lidar):
        measures = [_make_measure(0.0, 100.0), _make_measure(90.0, 200.0)]
        lidar.inject_measures(measures)
        result = list(lidar.iter())
        assert len(result) == 2
        assert result[0].distance == 100.0
        assert result[1].distance == 200.0

    def test_angles_in_radians(self, lidar):
        measures = [_make_measure(180.0, 500.0)]
        lidar.inject_measures(measures)
        result = list(lidar.iter())
        assert abs(result[0].angle - math.pi) < 1e-9

    def test_iter_returns_copies(self, lidar):
        measures = [_make_measure(0.0, 100.0)]
        lidar.inject_measures(measures)
        result1 = list(lidar.iter())
        result2 = list(lidar.iter())
        assert len(result1) == 1
        assert len(result2) == 1

    def test_on_scan_event(self, lidar):
        received = []
        lidar.on_scan().register(lambda scan: received.append(scan))
        scan = [_make_measure(45.0, 300.0)]
        lidar.inject_scan(scan)
        assert len(received) == 1
        assert received[0][0].distance == 300.0

    def test_close_clears(self, lidar):
        lidar.inject_measures([_make_measure()])
        lidar.start().wait()
        lidar.close()
        assert lidar.scanning is False
        assert list(lidar.iter()) == []

    def test_name(self, lidar):
        assert lidar.name == "test-lidar"
