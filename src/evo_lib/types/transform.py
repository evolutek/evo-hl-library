from abc import ABC, abstractmethod
from math import cos, sin

from evo_lib.types.pose import Pose2D
from evo_lib.types.vect import Vect2D


class Transform2D(ABC):
    @abstractmethod
    def apply_to_point(self, point: Vect2D) -> None:
        pass

    @abstractmethod
    def apply_to_angle(self, angle: float) -> float:
        pass

    def apply_to_pose(self, pose: Pose2D) -> None:
        self.apply_to_point(pose.position)
        pose.heading = self.apply_to_angle(pose.heading)

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


class MirrorTransform2D(ABC):
    def __init__(self, offset: Vect2D, vertical: bool):
        self._vertical: bool = vertical
        self._offset = offset.copy()

    def apply(self, point: Vect2D):
        if self._vertical:
            point.y *= -1
        else:
            point.x *= -1
        point += self._offset

    def copy(self) -> Transform2D:
        return MirrorTransform2D(self._offset, self._vertical)


class RigidTransform2D(Transform2D):
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

    def __neg__(self):
        a = -self.angle
        x = self.offset.x * self._c + self.offset.y * self._s
        y = -self.offset.x * self._s + self.offset.y * self._c
        return RigidTransform2D(Vect2D(-x, -y), a)


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
