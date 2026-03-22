"""2D and 3D vector types with pose variants.

Provides four concrete types organized under two abstract bases:

VectBase types (Vect2D, Vect3D) are true vectors: addition, subtraction,
scaling, norm, and dot product all make mathematical sense.

PoseBase types (Pose2D, Pose3D) represent a position plus an orientation.
Vector arithmetic does not apply to them, but they support coordinate-frame
transforms. Pose3D uses quaternions internally for gimbal-lock-free rotation.
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


class PoseBase(ABC):
    """Abstract base for pose types (position + orientation).

    These are elements of SE(n), not vectors. Addition, scaling, and norm
    are intentionally not defined.
    """

    __slots__ = ()

    @property
    @abstractmethod
    def _comparison_key(self) -> tuple[float, ...]:
        """Values used for equality and hashing."""
        ...

    # -- Comparison ---------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return all(
            math.isclose(a, b) for a, b in zip(self._comparison_key, other._comparison_key)  # type: ignore[union-attr]
        )

    def __hash__(self) -> int:
        return hash(tuple(round(v, 9) for v in self._comparison_key))


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
# Concrete pose types
# ---------------------------------------------------------------------------


class Pose2D(PoseBase):
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
    def _comparison_key(self) -> tuple[float, ...]:
        return (self.x, self.y, self.theta)

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

    def inverse(self) -> Pose2D:
        """The inverse transform (parent frame -> this frame)."""
        p = Vect2D(-self.x, -self.y).rotate(-self.theta)
        return Pose2D(p.x, p.y, -self.theta)

    def compose(self, other: Pose2D) -> Pose2D:
        """Compose two transforms: self then other (in the local frame of self)."""
        p = self.transform(other.position)
        return Pose2D(p.x, p.y, self.theta + other.theta)

    @staticmethod
    def from_dict(d: dict) -> Pose2D:
        """Build from a config dict (e.g. {"x": 0, "y": 85, "theta": 0})."""
        return Pose2D(d["x"], d["y"], d.get("theta", 0.0))

    def to_dict(self) -> dict[str, float]:
        """Serialize to a dict."""
        return {"x": self.x, "y": self.y, "theta": self.theta}

    # -- Conversion ---------------------------------------------------------

    def to_3d(self, z: float = 0.0) -> Pose3D:
        """Promote to 3D with the given Z and yaw = theta."""
        return Pose3D(self.x, self.y, z, yaw=self.theta)

    # -- Display ------------------------------------------------------------

    def __repr__(self) -> str:
        return f"Pose2D(x={self.x}, y={self.y}, theta={self.theta})"


class Pose3D(PoseBase):
    """3D position with orientation (x, y, z, quaternion).

    Full 6-DOF pose for articulated arms or 3D sensors. Orientation is stored
    as a unit quaternion internally, avoiding gimbal lock. Constructor accepts
    Euler angles (roll, pitch, yaw) for convenience.

    For ground robots, use Pose2D instead (only yaw matters).
    """

    __slots__ = ("x", "y", "z", "_qw", "_qx", "_qy", "_qz")

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
        qw, qx, qy, qz = Pose3D._euler_to_quat(roll, pitch, yaw)
        self._qw, self._qx, self._qy, self._qz = Pose3D._canonical_sign(qw, qx, qy, qz)

    @classmethod
    def from_quaternion(cls, x: float, y: float, z: float,
                        qw: float, qx: float, qy: float, qz: float) -> Pose3D:
        """Construct directly from a unit quaternion (no Euler conversion)."""
        obj = object.__new__(cls)
        obj.x = float(x)
        obj.y = float(y)
        obj.z = float(z)
        obj._qw, obj._qx, obj._qy, obj._qz = Pose3D._canonical_sign(qw, qx, qy, qz)
        return obj

    # -- Quaternion access --------------------------------------------------

    @property
    def qw(self) -> float:
        return self._qw

    @property
    def qx(self) -> float:
        return self._qx

    @property
    def qy(self) -> float:
        return self._qy

    @property
    def qz(self) -> float:
        return self._qz

    @property
    def quaternion(self) -> tuple[float, float, float, float]:
        """(w, x, y, z) quaternion components."""
        return (self._qw, self._qx, self._qy, self._qz)

    # -- Euler access (computed from quaternion) ----------------------------

    @property
    def roll(self) -> float:
        sinr = 2 * (self._qw * self._qx + self._qy * self._qz)
        cosr = 1 - 2 * (self._qx * self._qx + self._qy * self._qy)
        return math.atan2(sinr, cosr)

    @property
    def pitch(self) -> float:
        sinp = 2 * (self._qw * self._qy - self._qz * self._qx)
        return math.asin(max(-1.0, min(1.0, sinp)))

    @property
    def yaw(self) -> float:
        siny = 2 * (self._qw * self._qz + self._qx * self._qy)
        cosy = 1 - 2 * (self._qy * self._qy + self._qz * self._qz)
        return math.atan2(siny, cosy)

    # -- PoseBase interface -------------------------------------------------

    @property
    def _comparison_key(self) -> tuple[float, ...]:
        return (self.x, self.y, self.z, self._qw, self._qx, self._qy, self._qz)

    @property
    def position(self) -> Vect3D:
        """The translation part as a Vect3D."""
        return Vect3D(self.x, self.y, self.z)

    def transform(self, point: Vect3D) -> Vect3D:
        """Transform *point* from this frame into the parent frame.

        Uses the quaternion cross-product formula:
        p' = p + 2w * (q_xyz x p) + 2 * (q_xyz x (q_xyz x p))
        """
        px, py, pz = point.x, point.y, point.z
        qw, qx, qy, qz = self._qw, self._qx, self._qy, self._qz

        # t = 2 * cross(q.xyz, p)
        tx = 2 * (qy * pz - qz * py)
        ty = 2 * (qz * px - qx * pz)
        tz = 2 * (qx * py - qy * px)

        # p' = p + qw * t + cross(q.xyz, t)
        return Vect3D(
            self.x + px + qw * tx + (qy * tz - qz * ty),
            self.y + py + qw * ty + (qz * tx - qx * tz),
            self.z + pz + qw * tz + (qx * ty - qy * tx),
        )

    def inverse(self) -> Pose3D:
        """The inverse transform (parent frame -> this frame)."""
        # Inverse rotation = conjugate for unit quaternions
        iqw, iqx, iqy, iqz = self._qw, -self._qx, -self._qy, -self._qz

        # Rotate -t by the inverse quaternion
        tx, ty, tz = -self.x, -self.y, -self.z
        ttx = 2 * (iqy * tz - iqz * ty)
        tty = 2 * (iqz * tx - iqx * tz)
        ttz = 2 * (iqx * ty - iqy * tx)
        px = tx + iqw * ttx + (iqy * ttz - iqz * tty)
        py = ty + iqw * tty + (iqz * ttx - iqx * ttz)
        pz = tz + iqw * ttz + (iqx * tty - iqy * ttx)

        return Pose3D.from_quaternion(px, py, pz, iqw, iqx, iqy, iqz)

    def compose(self, other: Pose3D) -> Pose3D:
        """Compose two transforms: self then other (in the local frame of self)."""
        p = self.transform(other.position)

        # Quaternion multiplication: q1 * q2
        w1, x1, y1, z1 = self._qw, self._qx, self._qy, self._qz
        w2, x2, y2, z2 = other._qw, other._qx, other._qy, other._qz
        qw = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        qx = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        qy = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        qz = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2

        return Pose3D.from_quaternion(p.x, p.y, p.z, qw, qx, qy, qz)

    @staticmethod
    def from_dict(d: dict) -> Pose3D:
        """Build from a config dict (Euler angles)."""
        return Pose3D(
            d["x"], d["y"], d["z"],
            d.get("roll", 0.0), d.get("pitch", 0.0), d.get("yaw", 0.0),
        )

    def to_dict(self) -> dict[str, float]:
        """Serialize to a dict (Euler angles for human readability)."""
        return {
            "x": self.x, "y": self.y, "z": self.z,
            "roll": self.roll, "pitch": self.pitch, "yaw": self.yaw,
        }

    # -- Conversion ---------------------------------------------------------

    def to_2d(self) -> Pose2D:
        """Project onto 2D (Z, roll, pitch are discarded, yaw becomes theta)."""
        return Pose2D(self.x, self.y, self.yaw)

    # -- Display ------------------------------------------------------------

    def __repr__(self) -> str:
        r, p, y = self.roll, self.pitch, self.yaw
        return f"Pose3D(x={self.x}, y={self.y}, z={self.z}, roll={r}, pitch={p}, yaw={y})"

    # -- Internal -----------------------------------------------------------

    @staticmethod
    def _euler_to_quat(roll: float, pitch: float, yaw: float) -> tuple[float, float, float, float]:
        """Convert ZYX Euler angles to unit quaternion (w, x, y, z)."""
        cr, sr = math.cos(roll / 2), math.sin(roll / 2)
        cp, sp = math.cos(pitch / 2), math.sin(pitch / 2)
        cy, sy = math.cos(yaw / 2), math.sin(yaw / 2)
        return (
            cr * cp * cy + sr * sp * sy,
            sr * cp * cy - cr * sp * sy,
            cr * sp * cy + sr * cp * sy,
            cr * cp * sy - sr * sp * cy,
        )

    @staticmethod
    def _canonical_sign(qw: float, qx: float, qy: float, qz: float) -> tuple[float, float, float, float]:
        """Ensure canonical sign so q and -q (same rotation) have identical repr."""
        for c in (qw, qx, qy, qz):
            if c > 1e-15:
                return (qw, qx, qy, qz)
            if c < -1e-15:
                return (-qw, -qx, -qy, -qz)
        return (qw, qx, qy, qz)
