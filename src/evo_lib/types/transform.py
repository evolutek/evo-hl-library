from abc import ABC, abstractmethod
from math import cos, sin

from evo_lib.types.vect import Vect2D


class Transform(ABC):
    @abstractmethod
    def apply(self, point: Vect2D):
        pass

    @abstractmethod
    def copy(self) -> Transform:
        pass


class RigidTransform(Transform):
    def __init__(self,
        offset: Vect2D,
        angle: float
    ):
        self.offset = offset.copy()
        self.angle = angle
        self._c = cos(angle)
        self._s = sin(angle)

    @staticmethod
    def create_identity() -> RigidTransform:
        return RigidTransform(Vect2D(0, 0), 0)

    @staticmethod
    def create_rotate_then_translate(angle: float, offset: Vect2D) -> RigidTransform:
        return RigidTransform(offset, angle)

    @staticmethod
    def create_rotate_arround(center: Vect2D, angle: float) -> RigidTransform:
        t = RigidTransform(-center, 0)
        t.transform(RigidTransform.create_rotate_then_translate(angle, center))
        return t

    @staticmethod
    def create_translate(offset: Vect2D) -> RigidTransform:
        return RigidTransform(offset, 0)

    def copy(self) -> RigidTransform:
        return RigidTransform(
            self.offset,
            self.angle
        )

    # Rotate then offset the given point in place
    def apply(self, point: Vect2D) -> None:
        x = point.x
        y = point.y
        point.x = x * self._c - y * self._s
        point.y = x * self._s + y * self._c
        point += self.offset

    def transform(self, other: RigidTransform) -> None:
        other.apply(self.offset)
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
        return RigidTransform(Vect2D(-x, -y), a)


class AffineTransform(RigidTransform):
    def __init__(self,
        offset: Vect2D = Vect2D(0, 0),
        angle: float = 0,
        factor: Vect2D = Vect2D(1, 1)
    ):
        super().__init__(offset, angle)
        self.factor = factor.copy()

    def copy(self) -> AffineTransform:
        return AffineTransform(
            self.offset,
            self.angle,
            self.factor
        )

    def scale(self, factor: Vect2D):
        self.factor.x *= factor.x
        self.factor.y *= factor.y

    # Scale then rotate then offset the given point in place
    def apply(self, point: Vect2D) -> None:
        point.x *= self.factor.x
        point.y *= self.factor.y
        super().apply(point)
