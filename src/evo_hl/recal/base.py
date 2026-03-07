"""Abstract base class for recalibration distance sensors."""

from __future__ import annotations

from abc import ABC, abstractmethod
# Default voltage-to-distance conversion parameters
DEFAULT_MIN_VOLTAGE = 0.6
DEFAULT_MAX_VOLTAGE = 3.0
DEFAULT_MIN_DISTANCE_MM = 100.0
DEFAULT_MAX_DISTANCE_MM = 1250.0
class Recal(ABC):
    """Reads distance from analog recalibration sensors.

    Converts ADC voltage to distance (mm) with optional piecewise
    linear calibration.
    """

    def __init__(
        self,
        min_voltage: float = DEFAULT_MIN_VOLTAGE,
        max_voltage: float = DEFAULT_MAX_VOLTAGE,
        min_distance: float = DEFAULT_MIN_DISTANCE_MM,
        max_distance: float = DEFAULT_MAX_DISTANCE_MM,
    ):
        self.min_voltage = min_voltage
        self.max_voltage = max_voltage
        self.min_distance = min_distance
        self.max_distance = max_distance

    @abstractmethod
    def read_distance(self, channel: int, samples: int = 1) -> float:
        """Read distance in mm from an ADC channel, averaged over samples."""

    def voltage_to_distance(self, voltage: float) -> float:
        """Convert voltage to distance using linear interpolation."""
        voltage = max(self.min_voltage, min(voltage, self.max_voltage))
        alpha = (voltage - self.min_voltage) / (self.max_voltage - self.min_voltage)
        return (self.max_distance - self.min_distance) * alpha + self.min_distance
