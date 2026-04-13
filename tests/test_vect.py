"""Tests for the vector type hierarchy."""

import math

import pytest

from evo_lib.types.vect import (
    Vect2D,
    Vect3D,
)


# ===========================================================================
# Vect2D
# ===========================================================================


class TestVect2DConstruction:
    def test_basic(self):
        v = Vect2D(3.0, 4.0)
        assert v.x == 3.0
        assert v.y == 4.0

    def test_int_coerced_to_float(self):
        v = Vect2D(1, 2)
        assert isinstance(v.x, float)


class TestVect2DArithmetic:
    def test_add(self):
        assert Vect2D(1, 2) + Vect2D(3, 4) == Vect2D(4, 6)

    def test_sub(self):
        assert Vect2D(5, 7) - Vect2D(2, 3) == Vect2D(3, 4)

    def test_mul_scalar(self):
        assert Vect2D(2, 3) * 2 == Vect2D(4, 6)

    def test_rmul_scalar(self):
        assert 3 * Vect2D(1, 2) == Vect2D(3, 6)

    def test_neg(self):
        assert -Vect2D(1, -2) == Vect2D(-1, 2)

    def test_add_different_type_returns_not_implemented(self):
        assert Vect2D(1, 2).__add__(Vect3D(1, 2, 3)) is NotImplemented


class TestVect2DGeometry:
    def test_norm(self):
        assert math.isclose(Vect2D(3, 4).norm(), 5.0)

    def test_sqr_norm(self):
        assert math.isclose(Vect2D(3, 4).sqr_norm(), 25.0)

    def test_sqr_norm_avoids_sqrt(self):
        """sqr_norm is useful for distance comparisons without sqrt."""
        a, b, c = Vect2D(0, 0), Vect2D(3, 4), Vect2D(10, 10)
        assert (b - a).sqr_norm() < (c - a).sqr_norm()

    def test_normalized(self):
        n = Vect2D(0, 5).normalized()
        assert math.isclose(n.x, 0.0)
        assert math.isclose(n.y, 1.0)

    def test_normalized_zero_raises(self):
        with pytest.raises(ZeroDivisionError):
            Vect2D(0, 0).normalized()

    def test_dot(self):
        assert math.isclose(Vect2D(1, 0).dot(Vect2D(0, 1)), 0.0)
        assert math.isclose(Vect2D(2, 3).dot(Vect2D(4, 5)), 23.0)

    def test_dot_type_mismatch_raises(self):
        with pytest.raises(TypeError):
            Vect2D(1, 2).dot(Vect3D(1, 2, 3))  # type: ignore[arg-type]


class TestVect2DRotate:
    def test_rotate_90(self):
        v = Vect2D(1, 0).rotate(math.pi / 2)
        assert math.isclose(v.x, 0, abs_tol=1e-9)
        assert math.isclose(v.y, 1)

    def test_rotate_180(self):
        v = Vect2D(1, 0).rotate(math.pi)
        assert math.isclose(v.x, -1)
        assert math.isclose(v.y, 0, abs_tol=1e-9)

    def test_rotate_preserves_norm(self):
        v = Vect2D(3, 4)
        assert math.isclose(v.rotate(1.23).norm(), v.norm())


class TestVect2DPolar:
    def test_from_polar(self):
        v = Vect2D.from_polar(5, 0)
        assert math.isclose(v.x, 5)
        assert math.isclose(v.y, 0, abs_tol=1e-9)

    def test_from_polar_90(self):
        v = Vect2D.from_polar(3, math.pi / 2)
        assert math.isclose(v.x, 0, abs_tol=1e-9)
        assert math.isclose(v.y, 3)

    def test_round_trip(self):
        v = Vect2D(3, 4)
        r, theta = v.to_polar()
        v2 = Vect2D.from_polar(r, theta)
        assert v == v2

    def test_angle(self):
        assert math.isclose(Vect2D(1, 0).angle(), 0)
        assert math.isclose(Vect2D(0, 1).angle(), math.pi / 2)


class TestVect2DOffsetToward:
    def test_offset_positive(self):
        """Positive distance moves target further from self."""
        origin = Vect2D(0, 0)
        target = Vect2D(100, 0)
        result = origin.offset_toward(target, 50)
        assert result == Vect2D(150, 0)

    def test_offset_negative(self):
        """Negative distance moves target closer to self."""
        origin = Vect2D(0, 0)
        target = Vect2D(100, 0)
        result = origin.offset_toward(target, -30)
        assert result == Vect2D(70, 0)

    def test_offset_diagonal(self):
        origin = Vect2D(0, 0)
        target = Vect2D(3, 4)  # distance = 5, direction = (0.6, 0.8)
        result = origin.offset_toward(target, -5)
        assert math.isclose(result.x, 0, abs_tol=1e-9)
        assert math.isclose(result.y, 0, abs_tol=1e-9)

    def test_offset_vertical_line(self):
        """Handles vertical lines (legacy had a special case for this)."""
        origin = Vect2D(50, 0)
        target = Vect2D(50, 100)
        result = origin.offset_toward(target, -20)
        assert math.isclose(result.x, 50)
        assert math.isclose(result.y, 80)

    def test_offset_same_point_raises(self):
        """Cannot compute direction when origin == target."""
        p = Vect2D(10, 20)
        with pytest.raises(ZeroDivisionError):
            p.offset_toward(p, 5)


class TestVect2DMean:
    def test_two_points(self):
        assert Vect2D.mean([Vect2D(0, 0), Vect2D(10, 20)]) == Vect2D(5, 10)

    def test_single_point(self):
        assert Vect2D.mean([Vect2D(7, 3)]) == Vect2D(7, 3)

    def test_three_points(self):
        centroid = Vect2D.mean([Vect2D(0, 0), Vect2D(3, 0), Vect2D(0, 6)])
        assert math.isclose(centroid.x, 1.0)
        assert math.isclose(centroid.y, 2.0)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            Vect2D.mean([])


class TestVect2DToDict:
    def test_basic(self):
        assert Vect2D(3, 4).to_dict() == {"x": 3.0, "y": 4.0}

    def test_round_trip_with_from_polar(self):
        v = Vect2D.from_polar(5, math.pi / 4)
        d = v.to_dict()
        assert "x" in d and "y" in d


class TestVect2DConversion:
    def test_to_3d(self):
        v = Vect2D(1, 2).to_3d(5)
        assert v == Vect3D(1, 2, 5)

    def test_to_3d_default_z(self):
        v = Vect2D(1, 2).to_3d()
        assert v == Vect3D(1, 2, 0)


class TestVect2DEquality:
    def test_equal(self):
        assert Vect2D(1, 2) == Vect2D(1, 2)

    def test_close_values(self):
        assert Vect2D(1, 2) == Vect2D(1, 2 + 1e-12)

    def test_not_equal(self):
        assert Vect2D(1, 2) != Vect2D(1, 3)

    def test_not_equal_to_other_type(self):
        assert Vect2D(1, 2) != (1, 2)

    def test_hashable(self):
        s = {Vect2D(1, 2), Vect2D(1, 2)}
        assert len(s) == 1


class TestVect2DRepr:
    def test_repr(self):
        assert repr(Vect2D(1, 2)) == "Vect2D(x=1.0, y=2.0)"


# ===========================================================================
# Vect3D
# ===========================================================================


class TestVect3DConstruction:
    def test_basic(self):
        v = Vect3D(1, 2, 3)
        assert v.x == 1.0
        assert v.y == 2.0
        assert v.z == 3.0


class TestVect3DArithmetic:
    def test_add(self):
        assert Vect3D(1, 2, 3) + Vect3D(4, 5, 6) == Vect3D(5, 7, 9)

    def test_sub(self):
        assert Vect3D(4, 5, 6) - Vect3D(1, 2, 3) == Vect3D(3, 3, 3)

    def test_mul_scalar(self):
        assert Vect3D(1, 2, 3) * 2 == Vect3D(2, 4, 6)


class TestVect3DGeometry:
    def test_norm(self):
        assert math.isclose(Vect3D(1, 2, 2).norm(), 3.0)

    def test_sqr_norm(self):
        assert math.isclose(Vect3D(1, 2, 2).sqr_norm(), 9.0)

    def test_cross(self):
        i = Vect3D(1, 0, 0)
        j = Vect3D(0, 1, 0)
        k = i.cross(j)
        assert k == Vect3D(0, 0, 1)

    def test_cross_anticommutative(self):
        a = Vect3D(1, 2, 3)
        b = Vect3D(4, 5, 6)
        assert a.cross(b) == -b.cross(a)

    def test_dot(self):
        assert math.isclose(Vect3D(1, 0, 0).dot(Vect3D(0, 1, 0)), 0.0)


class TestVect3DMean:
    def test_two_points(self):
        assert Vect3D.mean([Vect3D(0, 0, 0), Vect3D(10, 20, 30)]) == Vect3D(5, 10, 15)

    def test_empty_raises(self):
        with pytest.raises(ValueError, match="empty"):
            Vect3D.mean([])


class TestVect3DToDict:
    def test_basic(self):
        assert Vect3D(1, 2, 3).to_dict() == {"x": 1.0, "y": 2.0, "z": 3.0}


class TestVect3DConversion:
    def test_to_2d(self):
        assert Vect3D(1, 2, 3).to_2d() == Vect2D(1, 2)


class TestVect3DRepr:
    def test_repr(self):
        assert repr(Vect3D(1, 2, 3)) == "Vect3D(x=1.0, y=2.0, z=3.0)"
