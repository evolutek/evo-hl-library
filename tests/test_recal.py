"""Tests for recalibration sensor driver using fake implementation."""

import pytest

from evo_hl.recal.base import Recal
from evo_hl.recal.fake import RecalFake


@pytest.fixture
def recal():
    return RecalFake()


class TestRecalFake:
    def test_default_distance(self, recal):
        # Default is min_distance when no injection
        assert recal.read_distance(0) == recal.min_distance

    def test_inject_distance(self, recal):
        recal.inject_distance(0, 500.0)
        assert recal.read_distance(0) == 500.0

    def test_independent_channels(self, recal):
        recal.inject_distance(0, 100.0)
        recal.inject_distance(1, 900.0)
        assert recal.read_distance(0) == 100.0
        assert recal.read_distance(1) == 900.0


class TestVoltageToDistance:
    def test_min_voltage(self):
        r = RecalFake(min_voltage=0.6, max_voltage=3.0, min_distance=100.0, max_distance=1250.0)
        assert r.voltage_to_distance(0.6) == pytest.approx(100.0)

    def test_max_voltage(self):
        r = RecalFake(min_voltage=0.6, max_voltage=3.0, min_distance=100.0, max_distance=1250.0)
        assert r.voltage_to_distance(3.0) == pytest.approx(1250.0)

    def test_mid_voltage(self):
        r = RecalFake(min_voltage=0.0, max_voltage=2.0, min_distance=0.0, max_distance=1000.0)
        assert r.voltage_to_distance(1.0) == pytest.approx(500.0)

    def test_clamp_below(self):
        r = RecalFake(min_voltage=1.0, max_voltage=3.0, min_distance=100.0, max_distance=500.0)
        assert r.voltage_to_distance(0.0) == pytest.approx(100.0)

    def test_clamp_above(self):
        r = RecalFake(min_voltage=1.0, max_voltage=3.0, min_distance=100.0, max_distance=500.0)
        assert r.voltage_to_distance(5.0) == pytest.approx(500.0)
