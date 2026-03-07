"""Tests for RPLidar driver using fake implementation."""

import pytest

from evo_hl.rplidar.fake import RPLidarFake


@pytest.fixture
def lidar():
    drv = RPLidarFake()
    drv.init()
    yield drv
    drv.close()


class TestRPLidarFake:
    def test_initial_state(self, lidar):
        assert lidar.scanning is False
        assert lidar.get_cloud() == []
        assert lidar.get_shapes() == []

    def test_start_stop_scanning(self, lidar):
        lidar.start_scanning()
        assert lidar.scanning is True
        lidar.stop_scanning()
        assert lidar.scanning is False

    def test_inject_cloud(self, lidar):
        cloud = [(100.0, 200.0), (300.0, 400.0)]
        lidar.inject_cloud(cloud)
        assert lidar.get_cloud() == cloud

    def test_inject_shapes(self, lidar):
        shapes = [[(10.0, 20.0), (11.0, 21.0)], [(50.0, 60.0)]]
        lidar.inject_shapes(shapes)
        result = lidar.get_shapes()
        assert len(result) == 2
        assert result[0] == [(10.0, 20.0), (11.0, 21.0)]

    def test_get_cloud_returns_copy(self, lidar):
        cloud = [(1.0, 2.0)]
        lidar.inject_cloud(cloud)
        result = lidar.get_cloud()
        result.append((3.0, 4.0))
        assert lidar.get_cloud() == [(1.0, 2.0)]

    def test_close_clears(self, lidar):
        lidar.inject_cloud([(1.0, 2.0)])
        lidar.inject_shapes([[(3.0, 4.0)]])
        lidar.start_scanning()
        lidar.close()
        assert lidar.scanning is False
        assert lidar.get_cloud() == []
        assert lidar.get_shapes() == []

    def test_default_params(self, lidar):
        assert lidar.device == "/dev/ttyUSB0"
        assert lidar.max_distance == 1500.0
        assert lidar.min_shape_size == 3

    def test_custom_params(self):
        drv = RPLidarFake(device="/dev/ttyUSB1", max_distance=2000.0)
        assert drv.device == "/dev/ttyUSB1"
        assert drv.max_distance == 2000.0
