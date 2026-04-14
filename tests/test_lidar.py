"""Tests for Lidar2D drivers."""

import math

from evo_lib.drivers.lidar.virtual import Lidar2DVirtual
from evo_lib.interfaces.lidar import Lidar2DMeasure
from evo_lib.logger import Logger


class TestLidar2DVirtual:
    def _make_measures(self, count: int = 3) -> list[Lidar2DMeasure]:
        return [
            Lidar2DMeasure(
                angle=math.radians(i * 10),
                distance=float(100 + i * 50),
                timestamp=0.0,
                quality=200.0,
            )
            for i in range(count)
        ]

    def test_start_stop(self):
        lidar = Lidar2DVirtual("lidar", Logger("test"))
        lidar.init()
        assert not lidar._running
        lidar.start().wait()
        assert lidar._running
        lidar.stop().wait()
        assert not lidar._running

    def test_inject_and_iter(self):
        lidar = Lidar2DVirtual("lidar", Logger("test"))
        lidar.init()
        lidar.start().wait()
        measures = self._make_measures(3)
        lidar.inject_scan(measures)

        result = list(lidar.iter())
        assert len(result) == 3
        assert result[0].distance == 100.0
        assert result[2].distance == 200.0

    def test_on_scan_event_fires(self):
        lidar = Lidar2DVirtual("lidar", Logger("test"))
        lidar.init()
        received = []
        lidar.on_scan().register(lambda batch: received.append(batch))

        measures = self._make_measures(2)
        lidar.inject_scan(measures)

        assert len(received) == 1
        assert len(received[0]) == 2
