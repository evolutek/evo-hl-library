"""Geometry types shared across omnissiah modules.

Position and Pose represent 2D coordinates on the table.
Utility functions provide distance computation and angle normalization.
"""

import math
from dataclasses import dataclass


@dataclass
class Position:
    """A 2D point on the table (millimeters)."""

    x: float
    y: float


@dataclass
class Pose:
    """A 2D point with orientation (millimeters, radians)."""

    x: float
    y: float
    theta: float


def distance(a: Position, b: Position) -> float:
    """Euclidean distance between two positions."""
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2)


def normalize_angle(angle: float) -> float:
    """Normalize an angle to the [-pi, pi] range."""
    return math.atan2(math.sin(angle), math.cos(angle))
