"""2D and 3D vector types with pose variants.

Provides four concrete types organized under two abstract bases:

VectBase types (Vect2D, Vect3D) are true vectors: addition, subtraction,
scaling, norm, and dot product all make mathematical sense.

PoseBase types (Pose2D, Pose3D) represent a position plus an orientation.
Vector arithmetic does not apply to them, but they support coordinate-frame
transforms. Pose3D uses quaternions internally for gimbal-lock-free rotation.
"""

import math
from abc import ABC, abstractmethod
from typing import Self

# ---------------------------------------------------------------------------
# Abstract bases
# ---------------------------------------------------------------------------


class VectBase(ABC):
    """Abstract base for pure vector types."""

    __slots__ = ()

    # Components getter
    @property
    @abstractmethod
    def _components(self) -> tuple[float, ...]:
        """All components as an ordered tuple."""
        pass

    # Components setter
    @_components.setter
    def _components(self, components: tuple[float, ...]) -> None:
        pass

    @abstractmethod
    def copy(self) -> VectBase:
        pass

    # -- Arithmetic ---------------------------------------------------------

    def __add__(self, other: object) -> Self:
        if not isinstance(other, type(self)):
            return NotImplemented
        return type(self)(*(a + b for a, b in zip(self._components, other._components)))  # type: ignore[arg-type]

    def __sub__(self, other: object) -> Self:
        if not isinstance(other, type(self)):
            return NotImplemented
        return type(self)(*(a - b for a, b in zip(self._components, other._components)))  # type: ignore[arg-type]

    def __mul__(self, scalar: float) -> Self:
        return type(self)(*(c * scalar for c in self._components))

    def __rmul__(self, scalar: float) -> Self:
        return self.__mul__(scalar)

    def __neg__(self) -> Self:
        return type(self)(*(-c for c in self._components))

    # -- In place arithmetic ---------------------------------------------------------

    def __iadd__(self, other: object) -> Self:
        if not isinstance(other, type(self)):
            return NotImplemented
        self._components = tuple(a + b for a, b in zip(self._components, other._components))  # type: ignore[arg-type]
        return self

    def __isub__(self, other: object) -> Self:
        if not isinstance(other, type(self)):
            return NotImplemented
        self._components = tuple(a - b for a, b in zip(self._components, other._components))  # type: ignore[arg-type]
        return self

    def __imul__(self, scalar: float) -> Self:
        self._components = tuple(c * scalar for c in self._components)
        return self

    # -- Geometry -----------------------------------------------------------

    def norm(self) -> float:
        """Euclidean norm."""
        return math.sqrt(self.sqr_norm())

    def sqr_norm(self) -> float:
        """Squared Euclidean norm (avoids sqrt, useful for distance comparisons)."""
        return sum(c * c for c in self._components)

    def normalized(self) -> Self:
        """Unit vector in the same direction. Raises ZeroDivisionError on zero vector."""
        n = self.norm()
        return type(self)(*(c / n for c in self._components))

    def dot(self, other: VectBase) -> float:
        """Dot product."""
        if not isinstance(other, type(self)):
            raise TypeError(f"Cannot dot {type(self).__name__} with {type(other).__name__}")
        return sum(a * b for a, b in zip(self._components, other._components))

    # -- Comparison ---------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return all(math.isclose(a, b) for a, b in zip(self._components, other._components))  # type: ignore[union-attr]

    def __hash__(self) -> int:
        return hash(tuple(round(c, 9) for c in self._components))

    # -- Display ------------------------------------------------------------

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}={val}" for name, val in zip(self.__slots__, self._components))
        return f"{type(self).__name__}({fields})"


# ---------------------------------------------------------------------------
# Concrete vector types
# ---------------------------------------------------------------------------


class Vect2D(VectBase):
    """2D vector (x, y) in millimeters."""

    __slots__ = ("x", "y")

    def __init__(self, x: float | int, y: float | int) -> None:
        self.x = float(x)
        self.y = float(y)

    def copy(self) -> Vect2D:
        return Vect2D(self.x, self.y)

    @property
    def _components(self) -> tuple[float, float]:
        return (self.x, self.y)

    @_components.setter
    def _components(self, components: tuple[float, float]) -> None:
        self.x, self.y = components

    # -- 2D-specific --------------------------------------------------------

    def rotate(self, theta: float) -> Vect2D:
        """Rotate around the origin by *theta* radians."""
        c, s = math.cos(theta), math.sin(theta)
        return Vect2D(self.x * c - self.y * s, self.x * s + self.y * c)

    def angle(self) -> float:
        """Angle of the vector from the positive X axis, in radians."""
        return math.atan2(self.y, self.x)

    @staticmethod
    def from_polar(r: float, theta: float) -> Vect2D:
        """Build from polar coordinates (distance, angle)."""
        return Vect2D(r * math.cos(theta), r * math.sin(theta))

    def to_polar(self) -> tuple[float, float]:
        """Return (r, theta) polar representation."""
        return (self.norm(), self.angle())

    def offset_toward(self, target: Vect2D, distance: float) -> Vect2D:
        """Point at *distance* from *target* along the self->target line.

        Positive distance moves further from self, negative moves closer.
        """
        direction = (target - self).normalized()
        return target + direction * distance

    @staticmethod
    def mean(points: list[Vect2D]) -> Vect2D:
        """Centroid of a list of points."""
        n = len(points)
        if n == 0:
            raise ValueError("Cannot compute mean of empty list")
        return Vect2D(
            sum(p.x for p in points) / n,
            sum(p.y for p in points) / n,
        )

    def to_dict(self) -> dict[str, float]:
        """Serialize to a dict."""
        return {"x": self.x, "y": self.y}

    # -- Conversion ---------------------------------------------------------

    def to_3d(self, z: float = 0.0) -> Vect3D:
        """Promote to 3D with the given Z component."""
        return Vect3D(self.x, self.y, z)


class Vect3D(VectBase):
    """3D vector (x, y, z) in millimeters."""

    __slots__ = ("x", "y", "z")

    def __init__(self, x: float, y: float, z: float) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)

    def copy(self) -> Vect3D:
        return Vect3D(self.x, self.y, self.z)

    @property
    def _components(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

    @_components.setter
    def _components(self, components: tuple[float, float]) -> None:
        self.x, self.y, self.z = components

    # -- 3D-specific --------------------------------------------------------

    def cross(self, other: Vect3D) -> Vect3D:
        """Cross product."""
        if not isinstance(other, Vect3D):
            raise TypeError(f"Cannot cross Vect3D with {type(other).__name__}")
        return Vect3D(
            self.y * other.z - self.z * other.y,
            self.z * other.x - self.x * other.z,
            self.x * other.y - self.y * other.x,
        )

    @staticmethod
    def mean(points: list[Vect3D]) -> Vect3D:
        """Centroid of a list of points."""
        n = len(points)
        if n == 0:
            raise ValueError("Cannot compute mean of empty list")
        return Vect3D(
            sum(p.x for p in points) / n,
            sum(p.y for p in points) / n,
            sum(p.z for p in points) / n,
        )

    def to_dict(self) -> dict[str, float]:
        """Serialize to a dict."""
        return {"x": self.x, "y": self.y, "z": self.z}

    # -- Conversion ---------------------------------------------------------

    def to_2d(self) -> Vect2D:
        """Project onto the XY plane (Z is discarded)."""
        return Vect2D(self.x, self.y)
