"""Recalibration sensor — fake implementation for testing."""

from __future__ import annotations

import logging

from evo_hl.recal.base import Recal

log = logging.getLogger(__name__)


class RecalFake(Recal):
    """In-memory recal sensor for tests and simulation."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.distances: dict[int, float] = {}

    def inject_distance(self, channel: int, distance: float) -> None:
        """Inject a distance value for testing."""
        self.distances[channel] = distance

    def read_distance(self, channel: int, samples: int = 1) -> float:
        return self.distances.get(channel, self.min_distance)
