"""Tests for SICK TIM driver using fake implementation."""

import math

import pytest

from evo_lib.drivers.tim.fake import SickTIMFake
from evo_lib.interfaces.lidar import Lidar2DMeasure


def _make_measure(angle: float = 0.0, distance: float = 1000.0) -> Lidar2DMeasure:
    """Helper to create a single measure."""
    return Lidar2DMeasure(angle=angle, distance=distance, timestamp=0.0, quality=255.0)


@pytest.fixture
def tim():
    drv = SickTIMFake(name="tim_test", host="127.0.0.1", port=2112)
    drv.init()
    yield drv
    drv.close()


class TestSickTIMFake:
    def test_initial_state(self, tim: SickTIMFake):
        assert tim.scanning is False
        assert list(tim.iter()) == []

    def test_name(self, tim: SickTIMFake):
        assert tim.name == "tim_test"

    def test_start_stop(self, tim: SickTIMFake):
        tim.start().wait()
        assert tim.scanning is True
        tim.stop().wait()
        assert tim.scanning is False

    def test_inject_scan_and_iter(self, tim: SickTIMFake):
        m1 = _make_measure(angle=0.0, distance=500.0)
        m2 = _make_measure(angle=math.radians(1.0), distance=600.0)
        tim.inject_scan([m1, m2])

        results = list(tim.iter())
        assert len(results) == 2
        assert results[0].distance == 500.0
        assert results[1].distance == 600.0

    def test_on_scan_event(self, tim: SickTIMFake):
        received = []
        tim.on_scan().register(lambda measures: received.append(measures))

        scan = [_make_measure(distance=1234.0)]
        tim.inject_scan(scan)

        assert len(received) == 1
        assert received[0][0].distance == 1234.0

    def test_close_clears_scans(self, tim: SickTIMFake):
        tim.inject_scan([_make_measure()])
        tim.start().wait()
        tim.close()
        assert tim.scanning is False
        assert list(tim.iter()) == []

    def test_multiple_scans(self, tim: SickTIMFake):
        tim.inject_scan([_make_measure(distance=100.0)])
        tim.inject_scan([_make_measure(distance=200.0)])

        results = list(tim.iter())
        assert len(results) == 2
        assert results[0].distance == 100.0
        assert results[1].distance == 200.0

    def test_measure_fields(self, tim: SickTIMFake):
        m = _make_measure(angle=1.5, distance=3000.0)
        tim.inject_scan([m])
        result = list(tim.iter())[0]
        assert result.angle == 1.5
        assert result.distance == 3000.0
        assert result.quality == 255.0
