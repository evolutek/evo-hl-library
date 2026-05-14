from abc import ABC, abstractmethod
from math import cos, pi, sin
from typing import Any

from evo_lib.argtypes import ArgTypes
from evo_lib.types.pose import Pose2D
from evo_lib.types.vect import Vect2D


class Transform2D(ABC):
    class ArgType(ArgTypes.Object["Transform2D"]):
        def __init__(self):
            # TODO: Use subargs here (on the "type" field)
            super().__init__(
                "Transform2D",
                [
                    ("type", ArgTypes.String(choices=["identity", "mirror", "rigid"])),
                    ("offset", Vect2D.ArgType()),
                    # ("mirror_x", ArgTypes.Bool()),
                    # ("mirror_y", ArgTypes.Bool()),
                    ("angle", ArgTypes.F32()),
                ],
            )

        def convert(self, v: dict[str, Any]) -> Transform2D:
            if v["type"] == "identity":
                return IdentityTransform2D()
            elif v["type"] == "mirror":
                return MirrorTransform2D(v["offset"], v["mirror_x"], v["mirror_y"])
            elif v["type"] == "rigid":
                return RigidTransform2D(v["offset"], v["angle"])
            else:
                raise ValueError(f"Unknown transform type: {v['type']}")

    @abstractmethod
    def apply_to_point(self, point: Vect2D) -> None:
        pass

    @abstractmethod
    def apply_to_angle(self, angle: float) -> float:
        pass

    def apply_to_pose(self, pose: Pose2D) -> None:
        p = pose.position
        self.apply_to_point(p)
        pose.x = p.x
        pose.y = p.y
        pose.heading = self.apply_to_angle(pose.heading)

    @abstractmethod
    def inversed(self) -> Transform2D:
        pass

    @abstractmethod
    def copy(self) -> Transform2D:
        pass


class IdentityTransform2D(Transform2D):
    def apply_to_point(self, point: Vect2D) -> None:
        pass

    def apply_to_angle(self, angle: float) -> float:
        return angle

    def copy(self) -> IdentityTransform2D:
        return IdentityTransform2D()

    def inversed(self) -> IdentityTransform2D:
        return IdentityTransform2D()

    def __str__(self) -> str:
        return "IdentityTransform2D()"


class MirrorTransform2D(Transform2D):
    class ArgType(ArgTypes.Object["MirrorTransform2D"]):
        def __init__(self):
            super().__init__(
                "MirrorTransform2D",
                [
                    ("offset", Vect2D.ArgType()),
                    ("mirror_x", ArgTypes.Bool()),
                    ("mirror_y", ArgTypes.Bool()),
                ],
            )

        def convert(self, v: dict[str, Any]) -> MirrorTransform2D:
            return MirrorTransform2D(v["offset"], v["mirror_x"], v["mirror_y"])

    def __init__(self, offset: Vect2D, mirror_x: bool, mirror_y: bool):
        self._mirror_x: bool = mirror_x
        self._mirror_y: bool = mirror_y
        self._offset = offset.copy()

    def inversed(self) -> Transform2D:
        return MirrorTransform2D(-self._offset, not self._mirror_x, not self._mirror_y)

    def apply_to_point(self, point: Vect2D):
        if self._mirror_x:
            point.x = -point.x
        if self._mirror_y:
            point.y = -point.y
        point += self._offset

    def apply_to_angle(self, angle: float) -> float:
        if self._mirror_x:
            angle = pi - angle
        if self._mirror_y:
            angle = -angle
        return angle

    def copy(self) -> Transform2D:
        return MirrorTransform2D(self._offset, self._mirror_x, self._mirror_y)

    def __str__(self) -> str:
        return f"MirrorTransform2D(offset={self._offset}, mirror_x={self._mirror_x}, mirror_y={self._mirror_y})"


class RigidTransform2D(Transform2D):
    class ArgType(ArgTypes.Object["RigidTransform2D"]):
        def __init__(self):
            super().__init__(
                "RigidTransform2D",
                [
                    ("offset", Vect2D.ArgType()),
                    ("angle", ArgTypes.F32()),
                ],
            )

        def convert(self, v: dict[str, Any]) -> RigidTransform2D:
            return RigidTransform2D(v["offset"], v["angle"])

    def __init__(self,
        offset: Vect2D,
        angle: float
    ):
        self.offset = offset.copy()
        self.angle = angle
        self._c = cos(angle)
        self._s = sin(angle)

    @staticmethod
    def create_identity() -> RigidTransform2D:
        return RigidTransform2D(Vect2D(0, 0), 0)

    @staticmethod
    def create_rotate_then_translate(angle: float, offset: Vect2D) -> RigidTransform2D:
        return RigidTransform2D(offset, angle)

    @staticmethod
    def create_rotate_arround(center: Vect2D, angle: float) -> RigidTransform2D:
        t = RigidTransform2D(-center, 0)
        t.transform(RigidTransform2D.create_rotate_then_translate(angle, center))
        return t

    @staticmethod
    def create_translate(offset: Vect2D) -> RigidTransform2D:
        return RigidTransform2D(offset, 0)

    def copy(self) -> RigidTransform2D:
        return RigidTransform2D(
            self.offset,
            self.angle
        )

    # Rotate then offset the given point in place
    def apply_to_point(self, point: Vect2D) -> None:
        x = point.x
        y = point.y
        point.x = x * self._c - y * self._s
        point.y = x * self._s + y * self._c
        point += self.offset

    def apply_to_angle(self, angle: float) -> float:
        return angle + self.angle

    def transform(self, other: RigidTransform2D) -> None:
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

    def inversed(self) -> RigidTransform2D:
        a = -self.angle
        x = self.offset.x * self._c + self.offset.y * self._s
        y = -self.offset.x * self._s + self.offset.y * self._c
        return RigidTransform2D(Vect2D(-x, -y), a)

    def __neg__(self):
        return self.inversed()

    def __str__(self) -> str:
        return f"RigidTransform2D(offset={self.offset}, angle={self.angle})"


class AffineTransform2D(RigidTransform2D):
    def __init__(self,
        offset: Vect2D = Vect2D(0, 0),
        angle: float = 0,
        factor: Vect2D = Vect2D(1, 1)
    ):
        super().__init__(offset, angle)
        self.factor = factor.copy()

    def copy(self) -> AffineTransform2D:
        return AffineTransform2D(
            self.offset,
            self.angle,
            self.factor
        )

    def scale(self, factor: Vect2D):
        self.factor.x *= factor.x
        self.factor.y *= factor.y

    # Scale then rotate then offset the given point in place
    def apply_to_point(self, point: Vect2D) -> None:
        point.x *= self.factor.x
        point.y *= self.factor.y
        super().apply_to_point(point)

    def __str__(self) -> str:
        return f"AffineTransform2D(offset={self.offset}, angle={self.angle}, factor={self.factor})"
