"""Recalibration sensor — reads distance via an ADC driver."""

from __future__ import annotations

import logging
from time import sleep

from evo_hl.ads1115.base import ADS1115
from evo_hl.recal.base import Recal

log = logging.getLogger(__name__)


class RecalSensor(Recal):
    """Recal sensor that reads from an ADS1115 ADC channel."""

    def __init__(self, adc: ADS1115, **kwargs):
        super().__init__(**kwargs)
        self._adc = adc
        self._calibration: list[tuple[float, float]] = []

    def calibrate(self, points: list[tuple[float, float]]) -> None:
        """Set piecewise linear calibration points [(raw_dist, true_dist), ...]."""
        self._calibration = sorted(points, key=lambda p: p[0])

    def read_distance(self, channel: int, samples: int = 1) -> float:
        total = 0.0
        for i in range(samples):
            voltage = self._adc.read_voltage(channel)
            total += self.voltage_to_distance(voltage)
            if i < samples - 1:
                sleep(0.05)
        raw_dist = total / samples

        if len(self._calibration) < 2:
            return raw_dist

        return self._apply_calibration(raw_dist)

    def _apply_calibration(self, raw: float) -> float:
        """Apply piecewise linear calibration."""
        pts = self._calibration
        if raw <= pts[0][0]:
            x1, y1 = pts[0]
            x2, y2 = pts[1]
        elif raw >= pts[-1][0]:
            x1, y1 = pts[-2]
            x2, y2 = pts[-1]
        else:
            x1, y1 = pts[0]
            x2, y2 = pts[1]
            for i in range(len(pts) - 1):
                if pts[i][0] <= raw <= pts[i + 1][0]:
                    x1, y1 = pts[i]
                    x2, y2 = pts[i + 1]
                    break
        if x2 == x1:
            return y1
        return ((raw - x1) / (x2 - x1)) * (y2 - y1) + y1
