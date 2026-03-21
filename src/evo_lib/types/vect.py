"""2D and 3D vector types with orientation variants.

Provides four concrete types organized under two abstract bases:

VectBase types (Vect2D, Vect3D) are true vectors: addition, subtraction,
scaling, norm, and dot product all make mathematical sense.

OrientedBase types (Vect2DOriented, Vect3DOriented) represent a position plus
an orientation (an element of the SE(2) or SE(3) group). Vector arithmetic does
not apply to them, but they support coordinate-frame transforms.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod


# ---------------------------------------------------------------------------
# Abstract bases
# ---------------------------------------------------------------------------


class VectBase(ABC):
    """Abstract base for pure vector types."""

    __slots__ = ()

    @property
    @abstractmethod
    def _components(self) -> tuple[float, ...]:
        """All components as an ordered tuple."""
        ...

    # -- Arithmetic ---------------------------------------------------------

    def __add__(self, other: object) -> VectBase:
        if type(self) is not type(other):
            return NotImplemented
        return type(self)(*(a + b for a, b in zip(self._components, other._components)))  # type: ignore[arg-type]

    def __sub__(self, other: object) -> VectBase:
        if type(self) is not type(other):
            return NotImplemented
        return type(self)(*(a - b for a, b in zip(self._components, other._components)))  # type: ignore[arg-type]

    def __mul__(self, scalar: float) -> VectBase:
        return type(self)(*(c * scalar for c in self._components))

    def __rmul__(self, scalar: float) -> VectBase:
        return self.__mul__(scalar)

    def __neg__(self) -> VectBase:
        return type(self)(*(-c for c in self._components))

    # -- Geometry -----------------------------------------------------------

    def norm(self) -> float:
        """Euclidean norm."""
        return math.sqrt(self.sqr_norm())

    def sqr_norm(self) -> float:
        """Squared Euclidean norm (avoids sqrt, useful for distance comparisons)."""
        return sum(c * c for c in self._components)

    def normalized(self) -> VectBase:
        """Unit vector in the same direction. Raises ZeroDivisionError on zero vector."""
        n = self.norm()
        return type(self)(*(c / n for c in self._components))

    def dot(self, other: VectBase) -> float:
        """Dot product."""
        if type(self) is not type(other):
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


class OrientedBase(ABC):
    """Abstract base for oriented types (position + orientation).

    These are elements of SE(n), not vectors. Addition, scaling, and norm
    are intentionally not defined.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def _fields(self) -> tuple[tuple[str, float], ...]:
        """All fields as (name, value) pairs."""
        ...

    # -- Comparison ---------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return all(
            math.isclose(a, b) for (_, a), (_, b) in zip(self._fields, other._fields)  # type: ignore[union-attr]
        )

    def __hash__(self) -> int:
        return hash(tuple(round(v, 9) for _, v in self._fields))

    # -- Display ------------------------------------------------------------

    def __repr__(self) -> str:
        fields = ", ".join(f"{name}={val}" for name, val in self._fields)
        return f"{type(self).__name__}({fields})"


# ---------------------------------------------------------------------------
# Concrete vector types
# ---------------------------------------------------------------------------


class Vect2D(VectBase):
    """2D vector (x, y) in millimeters."""

    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        self.x = float(x)
        self.y = float(y)

    @property
    def _components(self) -> tuple[float, float]:
        return (self.x, self.y)

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

    @property
    def _components(self) -> tuple[float, float, float]:
        return (self.x, self.y, self.z)

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


# ---------------------------------------------------------------------------
# Concrete oriented types
# ---------------------------------------------------------------------------


class Vect2DOriented(OrientedBase):
    """2D position with orientation (x, y, theta).

    Represents a rigid-body pose in the plane: where something is and which
    direction it faces. Use *transform* to convert points between reference
    frames.
    """

    __slots__ = ("x", "y", "theta")

    def __init__(self, x: float, y: float, theta: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.theta = float(theta)

    @property
    def _fields(self) -> tuple[tuple[str, float], ...]:
        return (("x", self.x), ("y", self.y), ("theta", self.theta))

    @property
    def position(self) -> Vect2D:
        """The translation part as a Vect2D."""
        return Vect2D(self.x, self.y)

    def transform(self, point: Vect2D) -> Vect2D:
        """Transform *point* from this frame into the parent frame.

        Applies rotation then translation:
            x' = self.x + point.x * cos(theta) - point.y * sin(theta)
            y' = self.y + point.x * sin(theta) + point.y * cos(theta)
        """
        return self.position + point.rotate(self.theta)

    def inverse(self) -> Vect2DOriented:
        """The inverse transform (parent frame -> this frame)."""
        p = Vect2D(-self.x, -self.y).rotate(-self.theta)
        return Vect2DOriented(p.x, p.y, -self.theta)

    def compose(self, other: Vect2DOriented) -> Vect2DOriented:
        """Compose two transforms: self then other (in the local frame of self)."""
        p = self.transform(other.position)
        return Vect2DOriented(p.x, p.y, self.theta + other.theta)

    @staticmethod
    def from_dict(d: dict) -> Vect2DOriented:
        """Build from a config dict (e.g. {"x": 0, "y": 85, "theta": 0})."""
        return Vect2DOriented(d["x"], d["y"], d.get("theta", 0.0))

    def to_dict(self) -> dict[str, float]:
        """Serialize to a dict."""
        return {"x": self.x, "y": self.y, "theta": self.theta}

    # -- Conversion ---------------------------------------------------------

    def to_3d_oriented(self, z: float = 0.0) -> Vect3DOriented:
        """Promote to 3D with the given Z and yaw = theta."""
        return Vect3DOriented(self.x, self.y, z, yaw=self.theta)


class Vect3DOriented(OrientedBase):
    """3D position with orientation (x, y, z, roll, pitch, yaw).

    Full 6-DOF pose for articulated arms or 3D sensors. For ground robots,
    use Vect2DOriented instead (only yaw matters).
    """

    __slots__ = ("x", "y", "z", "roll", "pitch", "yaw")

    def __init__(
        self,
        x: float,
        y: float,
        z: float,
        roll: float = 0.0,
        pitch: float = 0.0,
        yaw: float = 0.0,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        self.roll = float(roll)
        self.pitch = float(pitch)
        self.yaw = float(yaw)

    @property
    def _fields(self) -> tuple[tuple[str, float], ...]:
        return (
            ("x", self.x),
            ("y", self.y),
            ("z", self.z),
            ("roll", self.roll),
            ("pitch", self.pitch),
            ("yaw", self.yaw),
        )

    @property
    def position(self) -> Vect3D:
        """The translation part as a Vect3D."""
        return Vect3D(self.x, self.y, self.z)

    def _rotation_matrix(self) -> tuple[float, ...]:
        """ZYX rotation matrix as 9 floats in row-major order.

        R = Rx(roll) @ Ry(pitch) @ Rz(yaw)
        """
        cy, sy = math.cos(self.yaw), math.sin(self.yaw)
        cp, sp = math.cos(self.pitch), math.sin(self.pitch)
        cr, sr = math.cos(self.roll), math.sin(self.roll)
        return (
            cp * cy,               -cp * sy,               sp,
            sr * sp * cy + cr * sy, -sr * sp * sy + cr * cy, -sr * cp,
            -cr * sp * cy + sr * sy, cr * sp * sy + sr * cy,  cr * cp,
        )

    @staticmethod
    def _euler_from_matrix(r: tuple[float, ...]) -> tuple[float, float, float]:
        """Extract (roll, pitch, yaw) from a ZYX rotation matrix (row-major)."""
        pitch = math.asin(max(-1.0, min(1.0, r[2])))
        if abs(math.cos(pitch)) > 1e-10:
            roll = math.atan2(-r[5], r[8])
            yaw = math.atan2(-r[1], r[0])
        else:
            # Gimbal lock: pitch = +/-pi/2, assign all rotation to yaw
            roll = 0.0
            yaw = math.atan2(r[3], r[4])
        return roll, pitch, yaw

    def transform(self, point: Vect3D) -> Vect3D:
        """Transform *point* from this frame into the parent frame.

        Applies the ZYX rotation then translation.
        """
        r = self._rotation_matrix()
        px, py, pz = point.x, point.y, point.z
        return Vect3D(
            self.x + r[0] * px + r[1] * py + r[2] * pz,
            self.y + r[3] * px + r[4] * py + r[5] * pz,
            self.z + r[6] * px + r[7] * py + r[8] * pz,
        )

    def inverse(self) -> Vect3DOriented:
        """The inverse transform (parent frame -> this frame)."""
        r = self._rotation_matrix()
        # Transpose (R^T = R^-1 for orthogonal matrices)
        rt = (r[0], r[3], r[6], r[1], r[4], r[7], r[2], r[5], r[8])
        # Inverse translation: R^T @ (-t)
        tx, ty, tz = -self.x, -self.y, -self.z
        px = rt[0] * tx + rt[1] * ty + rt[2] * tz
        py = rt[3] * tx + rt[4] * ty + rt[5] * tz
        pz = rt[6] * tx + rt[7] * ty + rt[8] * tz
        roll, pitch, yaw = Vect3DOriented._euler_from_matrix(rt)
        return Vect3DOriented(px, py, pz, roll, pitch, yaw)

    def compose(self, other: Vect3DOriented) -> Vect3DOriented:
        """Compose two transforms: self then other (in the local frame of self)."""
        p = self.transform(other.position)
        r1 = self._rotation_matrix()
        r2 = other._rotation_matrix()
        # Matrix multiply R1 @ R2
        r = tuple(
            sum(r1[i * 3 + k] * r2[k * 3 + j] for k in range(3))
            for i in range(3) for j in range(3)
        )
        roll, pitch, yaw = Vect3DOriented._euler_from_matrix(r)
        return Vect3DOriented(p.x, p.y, p.z, roll, pitch, yaw)

    @staticmethod
    def from_dict(d: dict) -> Vect3DOriented:
        """Build from a config dict."""
        return Vect3DOriented(
            d["x"], d["y"], d["z"],
            d.get("roll", 0.0), d.get("pitch", 0.0), d.get("yaw", 0.0),
        )

    def to_dict(self) -> dict[str, float]:
        """Serialize to a dict."""
        return {
            "x": self.x, "y": self.y, "z": self.z,
            "roll": self.roll, "pitch": self.pitch, "yaw": self.yaw,
        }

    # -- Conversion ---------------------------------------------------------

    def to_2d_oriented(self) -> Vect2DOriented:
        """Project onto 2D (Z, roll, pitch are discarded, yaw becomes theta)."""
        return Vect2DOriented(self.x, self.y, self.yaw)
