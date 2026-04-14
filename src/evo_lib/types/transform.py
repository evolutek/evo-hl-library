"""In-place 2D transformations.

``RigidTransform2D`` and friends expose a mutable API for hot paths where
allocating a new Vect2D per point is too expensive (lidar scan conversion,
point cloud batch processing). For one-shot computations on a Pose2D, use
``Pose2D.transform`` / ``Pose2D.compose`` instead.

See docs/glossary/types/geometry-performance.md for the performance
rationale.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from math import cos, pi, sin

from evo_lib.types.pose import Pose2D
from evo_lib.types.vect import Vect2D


class Transform2D(ABC):
    """Abstract base for in-place 2D transformations."""

    @abstractmethod
    def apply_to_point(self, point: Vect2D) -> None:
        """Mutate *point* in place."""

    @abstractmethod
    def apply_to_angle(self, angle: float) -> float:
        """Return the image of *angle* under this transformation."""

    @abstractmethod
    def copy(self) -> Transform2D:
        """Return an independent copy of this transformation."""

    def apply_to_pose(self, pose: Pose2D) -> None:
        """Mutate *pose* (both translation and heading) in place."""
        # Note: ``pose.position`` returns a *fresh* Vect2D, so we cannot
        # mutate it in place. We route through (x, y) directly.
        p = Vect2D(pose.x, pose.y)
        self.apply_to_point(p)
        new_theta = self.apply_to_angle(pose.theta)
        # Rebuild the pose so the cached cos/sin stay consistent with theta.
        Pose2D.__init__(pose, p.x, p.y, new_theta)


class MirrorTransform2D(Transform2D):
    """Axial symmetry (optionally followed by a translation).

    Leaves SE(2) (determinant = -1), so this is not a rigid transformation
    in the SE(n) sense. Useful for mirroring a strategy across a table
    axis when switching sides.
    """

    def __init__(self, offset: Vect2D, vertical: bool) -> None:
        self._vertical: bool = vertical
        self._offset: Vect2D = offset.copy()

    def apply_to_point(self, point: Vect2D) -> None:
        if self._vertical:
            point.y = -point.y
        else:
            point.x = -point.x
        point += self._offset

    def apply_to_angle(self, angle: float) -> float:
        # Vertical mirror (flip Y): angle -> -angle
        # Horizontal mirror (flip X): angle -> pi - angle
        return -angle if self._vertical else pi - angle

    def copy(self) -> MirrorTransform2D:
        return MirrorTransform2D(self._offset, self._vertical)


class RigidTransform2D(Transform2D):
    """Rotation + translation. Element of SE(2).

    Caches ``cos(angle)`` and ``sin(angle)`` on construction to avoid
    recomputing them on every ``apply_to_point``.
    """

    def __init__(self, offset: Vect2D, angle: float) -> None:
        self.offset: Vect2D = offset.copy()
        self.angle: float = angle
        self._c: float = cos(angle)
        self._s: float = sin(angle)

    @staticmethod
    def create_identity() -> RigidTransform2D:
        return RigidTransform2D(Vect2D(0, 0), 0)

    @staticmethod
    def create_rotate_then_translate(angle: float, offset: Vect2D) -> RigidTransform2D:
        return RigidTransform2D(offset, angle)

    @staticmethod
    def create_rotate_around(center: Vect2D, angle: float) -> RigidTransform2D:
        """Rotation of *angle* around *center*."""
        t = RigidTransform2D(-center, 0)
        t.transform(RigidTransform2D.create_rotate_then_translate(angle, center))
        return t

    @staticmethod
    def create_translate(offset: Vect2D) -> RigidTransform2D:
        return RigidTransform2D(offset, 0)

    def copy(self) -> RigidTransform2D:
        return RigidTransform2D(self.offset, self.angle)

    def apply_to_point(self, point: Vect2D) -> None:
        """Rotate then offset *point* in place."""
        x = point.x
        y = point.y
        point.x = x * self._c - y * self._s
        point.y = x * self._s + y * self._c
        point += self.offset

    def apply_to_angle(self, angle: float) -> float:
        return angle + self.angle

    def transform(self, other: RigidTransform2D) -> None:
        """Post-compose with *other*: self becomes ``other ∘ self``."""
        other.apply_to_point(self.offset)
        self.angle += other.angle
        self._c = cos(self.angle)
        self._s = sin(self.angle)

    def rotate(self, angle: float) -> None:
        self.angle += angle
        self._c = cos(self.angle)
        self._s = sin(self.angle)

    def translate(self, offset: Vect2D) -> None:
        self.offset += offset

    def __neg__(self) -> RigidTransform2D:
        """Inverse transform. Note: not the arithmetic negation."""
        a = -self.angle
        x = self.offset.x * self._c + self.offset.y * self._s
        y = -self.offset.x * self._s + self.offset.y * self._c
        return RigidTransform2D(Vect2D(-x, -y), a)


class AffineTransform2D(RigidTransform2D):
    """Scale + rotate + translate. Leaves SE(2) (not distance-preserving)."""

    def __init__(
        self,
        offset: Vect2D = Vect2D(0, 0),
        angle: float = 0,
        factor: Vect2D = Vect2D(1, 1),
    ) -> None:
        super().__init__(offset, angle)
        self.factor: Vect2D = factor.copy()

    def copy(self) -> AffineTransform2D:
        return AffineTransform2D(self.offset, self.angle, self.factor)

    def scale(self, factor: Vect2D) -> None:
        self.factor.x *= factor.x
        self.factor.y *= factor.y

    def apply_to_point(self, point: Vect2D) -> None:
        """Scale, rotate, then offset *point* in place."""
        point.x *= self.factor.x
        point.y *= self.factor.y
        super().apply_to_point(point)
