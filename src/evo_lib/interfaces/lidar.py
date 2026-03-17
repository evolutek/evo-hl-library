"""Abstract interface for 2D scanning lidars."""

from __future__ import annotations

from abc import abstractmethod
from typing import Callable

from evo_lib.component import Component


class Lidar2D(Component):
    """A 2D rotating lidar (e.g. RPLidar A2, SICK TIM).

    Produces periodic scan data as a list of (angle_deg, distance_mm) points.
    """

    @abstractmethod
    def start(self) -> None:
        """Start continuous scanning."""

    @abstractmethod
    def stop(self) -> None:
        """Stop scanning."""

    @abstractmethod
    def on_scan(self, callback: Callable[[list[tuple[float, float]]], None]) -> None:
        """Register a callback invoked on each complete scan.

        The callback receives a list of (angle_deg, distance_mm) points.
        """
