"""Tests for rigid and affine transformations."""

import math

import pytest

from evo_lib.types.transform import AffineTransform, RigidTransform
from evo_lib.types.vect import Vect2D


class TestRigidTransformConstruction:
    """Test RigidTransform instantiation and factory methods."""

    def test_basic_construction(self):
        """Test basic construction with offset and angle."""
        t = RigidTransform(Vect2D(1, 2), math.pi / 4)
        assert t.offset == Vect2D(1, 2)
        assert t.angle == math.pi / 4
        assert t._c == pytest.approx(math.cos(math.pi / 4))
        assert t._s == pytest.approx(math.sin(math.pi / 4))

    def test_identity(self):
        """Test identity transform creation."""
        t = RigidTransform.create_identity()
        assert t.offset == Vect2D(0, 0)
        assert t.angle == 0
        assert t._c == pytest.approx(1)
        assert t._s == pytest.approx(0)

    def test_rotate_then_translate(self):
        """Test rotation followed by translation."""
        angle = math.pi / 2
        offset = Vect2D(3, 4)
        t = RigidTransform.create_rotate_then_translate(angle, offset)
        assert t.angle == angle
        assert t.offset == offset

    def test_translate_only(self):
        """Test translation-only transform."""
        offset = Vect2D(5, -2)
        t = RigidTransform.create_translate(offset)
        assert t.offset == offset
        assert t.angle == 0

    def test_rotate_around(self):
        """Test rotation around a specific point."""
        center = Vect2D(2, 3)
        angle = math.pi / 3
        t = RigidTransform.create_rotate_arround(center, angle)

        # Point at center should remain at center after transformation
        point = Vect2D(2, 3)
        t.apply(point)
        assert point.x == pytest.approx(2)
        assert point.y == pytest.approx(3)

    def test_copy(self):
        """Test that copy creates an independent instance."""
        t1 = RigidTransform(Vect2D(1, 2), math.pi / 4)
        t2 = t1.copy()

        # Verify values are the same
        assert t2.offset == t1.offset
        assert t2.angle == pytest.approx(t1.angle)

        # Modify t1 and verify t2 is independent
        t1.offset.x = 10
        t1.angle = math.pi
        assert t2.offset.x == 1
        assert t2.angle == pytest.approx(math.pi / 4)


class TestRigidTransformApply:
    """Test point transformation via apply()."""

    def test_apply_no_transformation(self):
        """Test apply with identity transform."""
        t = RigidTransform.create_identity()
        point = Vect2D(3, 4)
        t.apply(point)
        assert point.x == pytest.approx(3)
        assert point.y == pytest.approx(4)

    def test_apply_translation_only(self):
        """Test apply with translation only."""
        t = RigidTransform.create_translate(Vect2D(2, -1))
        point = Vect2D(1, 3)
        t.apply(point)
        assert point.x == pytest.approx(3)
        assert point.y == pytest.approx(2)

    def test_apply_rotation_only(self):
        """Test apply with 90-degree rotation around origin."""
        t = RigidTransform(Vect2D(0, 0), math.pi / 2)
        point = Vect2D(1, 0)
        t.apply(point)
        # After 90-degree rotation: (1,0) -> (0,1)
        assert point.x == pytest.approx(0, abs=1e-10)
        assert point.y == pytest.approx(1)

    def test_apply_rotation_and_translation(self):
        """Test apply with both rotation and translation."""
        # Rotate 90 degrees then translate by (2, 3)
        t = RigidTransform(Vect2D(2, 3), math.pi / 2)
        point = Vect2D(1, 0)
        t.apply(point)
        # (1,0) rotated 90 degrees -> (0,1), then translated -> (2,4)
        assert point.x == pytest.approx(2)
        assert point.y == pytest.approx(4)

    def test_apply_negative_rotation(self):
        """Test apply with negative (clockwise) rotation."""
        t = RigidTransform(Vect2D(0, 0), -math.pi / 2)
        point = Vect2D(0, 1)
        t.apply(point)
        # After -90-degree rotation: (0,1) -> (1,0)
        assert point.x == pytest.approx(1)
        assert point.y == pytest.approx(0, abs=1e-10)


class TestRigidTransformComposition:
    """Test composing transformations."""

    def test_transform_composition(self):
        """Test applying one transform to another."""
        t1 = RigidTransform(Vect2D(1, 0), 0)  # translate by (1,0)
        t2 = RigidTransform(Vect2D(2, 0), 0)  # translate by (2,0)

        t1.transform(t2)

        # Offset should be combined: (1,0) + (2,0) = (3,0)
        assert t1.offset.x == pytest.approx(3)
        assert t1.offset.y == pytest.approx(0)

    def test_transform_with_rotation(self):
        """Test composition with rotation."""
        t1 = RigidTransform(Vect2D(1, 0), 0)
        t2 = RigidTransform(Vect2D(0, 0), math.pi / 2)

        initial_angle = t1.angle
        t1.transform(t2)

        # Angle should be sum of angles
        assert t1.angle == pytest.approx(initial_angle + math.pi / 2)


class TestRigidTransformModification:
    """Test modifying existing transforms."""

    def test_rotate(self):
        """Test adding rotation to transform."""
        t = RigidTransform(Vect2D(1, 2), 0)
        t.rotate(math.pi / 4)

        assert t.angle == pytest.approx(math.pi / 4)
        assert t._c == pytest.approx(math.cos(math.pi / 4))
        assert t._s == pytest.approx(math.sin(math.pi / 4))

    def test_translate(self):
        """Test adding translation to transform."""
        t = RigidTransform(Vect2D(1, 2), 0)
        t.translate(Vect2D(3, -1))

        assert t.offset.x == pytest.approx(4)
        assert t.offset.y == pytest.approx(1)

    def test_rotate_accumulates(self):
        """Test that rotate accumulates."""
        t = RigidTransform(Vect2D(0, 0), math.pi / 4)
        t.rotate(math.pi / 4)

        assert t.angle == pytest.approx(math.pi / 2)


class TestRigidTransformInversion:
    """Test negation (inversion) of transforms."""

    def test_negate_translation_only(self):
        """Test negation of pure translation."""
        t = RigidTransform(Vect2D(3, 4), 0)
        neg_t = -t

        assert neg_t.offset.x == pytest.approx(-3)
        assert neg_t.offset.y == pytest.approx(-4)
        assert neg_t.angle == pytest.approx(0)

    def test_negate_rotation_only(self):
        """Test negation of pure rotation."""
        t = RigidTransform(Vect2D(0, 0), math.pi / 3)
        neg_t = -t

        assert neg_t.angle == pytest.approx(-math.pi / 3)
        assert neg_t.offset.x == pytest.approx(0)
        assert neg_t.offset.y == pytest.approx(0)

    def test_negate_combined(self):
        """Test negation of combined rotation and translation."""
        t = RigidTransform(Vect2D(2, 0), math.pi / 2)
        neg_t = -t

        # Negated angle
        assert neg_t.angle == pytest.approx(-math.pi / 2)

        point = Vect2D(1, 0)
        t.apply(point)
        neg_t.apply(point)

        assert point.x == pytest.approx(1)
        assert point.y == pytest.approx(0)

    def test_double_negation_identity(self):
        """Test that double negation returns to original."""
        t = RigidTransform(Vect2D(3, 4), math.pi / 6)
        double_neg = -(-t)

        assert double_neg.offset.x == pytest.approx(t.offset.x)
        assert double_neg.offset.y == pytest.approx(t.offset.y)
        assert double_neg.angle == pytest.approx(t.angle)

    def test_inverse_cancels_transform(self):
        """Test that inverse transform cancels original."""
        t = RigidTransform(Vect2D(2, 3), math.pi / 4)
        neg_t = -t

        # Point after transform then inverse should return to original
        point = Vect2D(1, 1)
        original = point.copy()
        t.apply(point)
        neg_t.apply(point)

        assert point.x == pytest.approx(original.x)
        assert point.y == pytest.approx(original.y)


class TestAffineTransformConstruction:
    """Test AffineTransform instantiation."""

    def test_basic_construction(self):
        """Test basic construction with defaults."""
        t = AffineTransform()
        assert t.offset == Vect2D(0, 0)
        assert t.angle == 0
        assert t.factor == Vect2D(1, 1)

    def test_construction_with_parameters(self):
        """Test construction with all parameters."""
        offset = Vect2D(1, 2)
        angle = math.pi / 3
        scale = Vect2D(2, 3)
        t = AffineTransform(offset, angle, scale)

        assert t.offset == offset
        assert t.angle == pytest.approx(angle)
        assert t.factor == scale

    def test_copy(self):
        """Test that copy creates an independent instance."""
        t1 = AffineTransform(Vect2D(1, 2), math.pi / 4, Vect2D(2, 3))
        t2 = t1.copy()

        assert t2.offset == t1.offset
        assert t2.angle == pytest.approx(t1.angle)
        assert t2.factor == t1.factor

        # Modify t1 and verify t2 is independent
        t1.factor.x = 10
        assert t2.factor.x == 2


class TestAffineTransformScale:
    """Test scaling functionality."""

    def test_scale_single(self):
        """Test applying a single scale."""
        t = AffineTransform(Vect2D(0, 0), 0, Vect2D(1, 1))
        t.scale(Vect2D(2, 3))

        assert t.factor.x == pytest.approx(2)
        assert t.factor.y == pytest.approx(3)

    def test_scale_accumulates(self):
        """Test that scale accumulates."""
        t = AffineTransform(Vect2D(0, 0), 0, Vect2D(2, 2))
        t.scale(Vect2D(3, 4))

        assert t.factor.x == pytest.approx(6)
        assert t.factor.y == pytest.approx(8)

    def test_scale_asymmetric(self):
        """Test asymmetric scaling."""
        t = AffineTransform(Vect2D(0, 0), 0, Vect2D(1, 1))
        t.scale(Vect2D(2, 0.5))

        assert t.factor.x == pytest.approx(2)
        assert t.factor.y == pytest.approx(0.5)


class TestAffineTransformApply:
    """Test point transformation with affine transforms."""

    def test_apply_no_transformation(self):
        """Test apply with identity affine transform."""
        t = AffineTransform()
        point = Vect2D(3, 4)
        t.apply(point)
        assert point.x == pytest.approx(3)
        assert point.y == pytest.approx(4)

    def test_apply_scale_only(self):
        """Test apply with scaling only."""
        t = AffineTransform(Vect2D(0, 0), 0, Vect2D(2, 3))
        point = Vect2D(1, 1)
        t.apply(point)
        assert point.x == pytest.approx(2)
        assert point.y == pytest.approx(3)

    def test_apply_scale_then_rotate(self):
        """Test scale then rotation then translation."""
        # Scale by 2, rotate 90 degrees, translate by (1, 1)
        t = AffineTransform(Vect2D(1, 1), math.pi / 2, Vect2D(2, 1))
        point = Vect2D(1, 0)
        t.apply(point)

        # (1,0) scaled by (2,1) -> (2,0)
        # (2,0) rotated 90 degrees -> (0,2)
        # (0,2) translated by (1,1) -> (1,3)
        assert point.x == pytest.approx(1)
        assert point.y == pytest.approx(3)

    def test_apply_non_uniform_scale_then_rotate(self):
        """Test non-uniform scale with rotation."""
        t = AffineTransform(Vect2D(0, 0), math.pi / 2, Vect2D(2, 3))
        point = Vect2D(1, 1)
        t.apply(point)

        # (1,1) scaled by (2,3) -> (2,3)
        # (2,3) rotated 90 degrees -> (-3,2)
        assert point.x == pytest.approx(-3)
        assert point.y == pytest.approx(2)

    def test_apply_scale_zero(self):
        """Test scaling with zero factor (degenerate case)."""
        t = AffineTransform(Vect2D(0, 0), 0, Vect2D(0, 0))
        point = Vect2D(5, 10)
        t.apply(point)

        assert point.x == pytest.approx(0)
        assert point.y == pytest.approx(0)


class TestAffineTransformInheritance:
    """Test that AffineTransform correctly inherits from RigidTransform."""

    def test_rotate_method(self):
        """Test that rotate method from RigidTransform works."""
        t = AffineTransform(Vect2D(0, 0), 0, Vect2D(1, 1))
        t.rotate(math.pi / 4)

        assert t.angle == pytest.approx(math.pi / 4)

    def test_translate_method(self):
        """Test that translate method from RigidTransform works."""
        t = AffineTransform(Vect2D(1, 1), 0, Vect2D(1, 1))
        t.translate(Vect2D(2, 3))

        assert t.offset.x == pytest.approx(3)
        assert t.offset.y == pytest.approx(4)
