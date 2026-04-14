"""Geometry types shared across omnissiah modules.

Pose2D and Pose3D represent rigid-body poses (position + orientation) on the
table or in 3D space. They are elements of SE(2) / SE(3): they compose, they
invert, they transform points — but they are **not** vectors. Addition,
scaling, and norm are intentionally not defined.

See docs/glossary/types/geometry-vocabulary.md for the underlying concepts
and docs/glossary/types/geometry-examples.md for worked examples.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod

from evo_lib.types.vect import Vect2D, Vect3D


class PoseBase(ABC):
    """Abstract base for pose types.

    These are elements of SE(n), not vectors. Addition, scaling, and norm
    are intentionally not defined — use ``compose``, ``inverse``, and
    ``transform`` instead.
    """

    __slots__ = ()

    @abstractmethod
    def copy(self) -> PoseBase:
        pass

    @property
    @abstractmethod
    def _comparison_key(self) -> tuple[float, ...]:
        """Values used for equality."""
        ...

    def __eq__(self, other: object) -> bool:
        if type(self) is not type(other):
            return NotImplemented
        return all(
            math.isclose(a, b)
            for a, b in zip(self._comparison_key, other._comparison_key)  # type: ignore[union-attr]
        )

    # Poses are logically mutable (transforms can alter heading in place).
    # Equality is approximate (``math.isclose``), which cannot be reconciled
    # with a stable hash. Make poses explicitly unhashable.
    __hash__ = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Pose2D
# ---------------------------------------------------------------------------


class Pose2D(PoseBase):
    """2D rigid-body pose (x, y, theta).

    Represents where something is and which direction it faces on the table.
    Internally caches ``cos(theta)`` and ``sin(theta)`` to avoid recomputing
    them on every ``transform`` call (see docs/glossary/types/geometry-performance.md).

    This class uses **composition** with Vect2D (via the ``position``
    accessor) rather than inheriting from it: a pose is not a vector, and
    inheriting vector arithmetic would silently produce geometrically wrong
    results (cf. ``pose_a + pose_b`` — use ``pose_a.compose(pose_b)``).
    """

    __slots__ = ("x", "y", "theta", "_c", "_s")

    def __init__(self, x: float = 0.0, y: float = 0.0, theta: float = 0.0) -> None:
        self.x = float(x)
        self.y = float(y)
        self.theta = float(theta)
        self._c = math.cos(self.theta)
        self._s = math.sin(self.theta)

    def copy(self) -> Pose2D:
        return Pose2D(self.x, self.y, self.theta)

    @property
    def _comparison_key(self) -> tuple[float, ...]:
        return (self.x, self.y, self.theta)

    @property
    def position(self) -> Vect2D:
        """The translation part as a new Vect2D (caller-owned copy)."""
        return Vect2D(self.x, self.y)

    # -- SE(2) operations ---------------------------------------------------

    def transform(self, point: Vect2D) -> Vect2D:
        """Transform *point* from this frame into the parent frame.

        Applies rotation then translation, using cached cos/sin:
            x' = self.x + point.x * c - point.y * s
            y' = self.y + point.x * s + point.y * c
        """
        return Vect2D(
            self.x + point.x * self._c - point.y * self._s,
            self.y + point.x * self._s + point.y * self._c,
        )

    def inverse(self) -> Pose2D:
        """The inverse transform (parent frame -> this frame).

        Note that ``Pose2D(-x, -y, -theta)`` is **not** the inverse: the
        translation must also be rotated by the inverse rotation.
        """
        # Reuse cached cos/sin: cos(-t)=cos(t), sin(-t)=-sin(t)
        inv = Pose2D.__new__(Pose2D)
        inv.theta = -self.theta
        inv._c = self._c
        inv._s = -self._s
        inv.x = -self.x * self._c - self.y * self._s
        inv.y = self.x * self._s - self.y * self._c
        return inv

    def compose(self, other: Pose2D) -> Pose2D:
        """Compose two transforms: self then other (other expressed in self's frame)."""
        px = self.x + other.x * self._c - other.y * self._s
        py = self.y + other.x * self._s + other.y * self._c
        return Pose2D(px, py, self.theta + other.theta)

    # -- Serialization ------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Pose3D
# ---------------------------------------------------------------------------


class Pose3D(PoseBase):
    """3D rigid-body pose (x, y, z + quaternion).

    Full 6-DOF pose for articulated arms or 3D sensors. Orientation is stored
    as a unit quaternion internally, avoiding gimbal lock. Constructor accepts
    Euler angles (roll, pitch, yaw) for convenience.

    For ground robots, prefer Pose2D (only yaw matters, cheaper).
    """

    __slots__ = ("x", "y", "z", "_qw", "_qx", "_qy", "_qz")

    def __init__(
        self,
        x: float = 0.0,
        y: float = 0.0,
        z: float = 0.0,
        roll: float = 0.0,
        pitch: float = 0.0,
        yaw: float = 0.0,
    ) -> None:
        self.x = float(x)
        self.y = float(y)
        self.z = float(z)
        qw, qx, qy, qz = Pose3D._euler_to_quat(roll, pitch, yaw)
        self._qw, self._qx, self._qy, self._qz = Pose3D._canonical_sign(qw, qx, qy, qz)

    def copy(self) -> Pose3D:
        return Pose3D.from_quaternion(
            self.x, self.y, self.z, self._qw, self._qx, self._qy, self._qz
        )

    @classmethod
    def from_quaternion(
        cls,
        x: float,
        y: float,
        z: float,
        qw: float,
        qx: float,
        qy: float,
        qz: float,
    ) -> Pose3D:
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
        """The translation part as a new Vect3D (caller-owned copy)."""
        return Vect3D(self.x, self.y, self.z)

    # -- SE(3) operations ---------------------------------------------------

    def transform(self, point: Vect3D) -> Vect3D:
        """Transform *point* from this frame into the parent frame.

        Quaternion sandwich product, expanded for efficiency:
            p' = self.position + q * p * q⁻¹
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

        tx, ty, tz = -self.x, -self.y, -self.z
        ttx = 2 * (iqy * tz - iqz * ty)
        tty = 2 * (iqz * tx - iqx * tz)
        ttz = 2 * (iqx * ty - iqy * tx)
        px = tx + iqw * ttx + (iqy * ttz - iqz * tty)
        py = ty + iqw * tty + (iqz * ttx - iqx * ttz)
        pz = tz + iqw * ttz + (iqx * tty - iqy * ttx)

        return Pose3D.from_quaternion(px, py, pz, iqw, iqx, iqy, iqz)

    def compose(self, other: Pose3D) -> Pose3D:
        """Compose two transforms: self then other (other expressed in self's frame)."""
        p = self.transform(other.position)

        # Quaternion multiplication: q1 * q2
        w1, x1, y1, z1 = self._qw, self._qx, self._qy, self._qz
        w2, x2, y2, z2 = other._qw, other._qx, other._qy, other._qz
        qw = w1 * w2 - x1 * x2 - y1 * y2 - z1 * z2
        qx = w1 * x2 + x1 * w2 + y1 * z2 - z1 * y2
        qy = w1 * y2 - x1 * z2 + y1 * w2 + z1 * x2
        qz = w1 * z2 + x1 * y2 - y1 * x2 + z1 * w2

        return Pose3D.from_quaternion(p.x, p.y, p.z, qw, qx, qy, qz)

    # -- Serialization ------------------------------------------------------

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
    def _canonical_sign(
        qw: float, qx: float, qy: float, qz: float
    ) -> tuple[float, float, float, float]:
        """Ensure canonical sign so q and -q (same rotation) have identical repr."""
        for c in (qw, qx, qy, qz):
            if c > 1e-15:
                return (qw, qx, qy, qz)
            if c < -1e-15:
                return (-qw, -qx, -qy, -qz)
        return (qw, qx, qy, qz)
