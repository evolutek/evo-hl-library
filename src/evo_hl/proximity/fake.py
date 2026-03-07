"""Proximity sensor — fake implementation for testing."""

from __future__ import annotations

from evo_hl.proximity.base import Proximity


class ProximityFake(Proximity):
    """In-memory proximity sensors for tests and simulation."""

    def __init__(self):
        self.detections: dict[int, bool] = {}

    def inject(self, sensor_id: int, detected: bool) -> None:
        """Inject a detection state for testing."""
        self.detections[sensor_id] = detected

    def read(self, sensor_id: int) -> bool:
        return self.detections.get(sensor_id, False)
