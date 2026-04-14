"""Tests for rigid and affine transformations."""

import math

import pytest

from evo_lib.types.pose import Pose2D
from evo_lib.types.transform import (
    AffineTransform2D,
    MirrorTransform2D,
    RigidTransform2D,
)
from evo_lib.types.vect import Vect2D


class TestRigidTransformConstruction:
    """Test RigidTransform2D instantiation and factory methods."""

    def test_basic_construction(self):
        """Test basic construction with offset and angle."""
        t = RigidTransform2D(Vect2D(1, 2), math.pi / 4)
        assert t.offset == Vect2D(1, 2)
        assert t.angle == math.pi / 4
        assert t._c == pytest.approx(math.cos(math.pi / 4))
        assert t._s == pytest.approx(math.sin(math.pi / 4))

    def test_identity(self):
        """Test identity transform creation."""
        t = RigidTransform2D.create_identity()
        assert t.offset == Vect2D(0, 0)
        assert t.angle == 0
        assert t._c == pytest.approx(1)
        assert t._s == pytest.approx(0)

    def test_rotate_then_translate(self):
        """Test rotation followed by translation."""
        angle = math.pi / 2
        offset = Vect2D(3, 4)
        t = RigidTransform2D.create_rotate_then_translate(angle, offset)
        assert t.angle == angle
        assert t.offset == offset

    def test_translate_only(self):
        """Test translation-only transform."""
        offset = Vect2D(5, -2)
        t = RigidTransform2D.create_translate(offset)
        assert t.offset == offset
        assert t.angle == 0

    def test_rotate_around(self):
        """Test rotation around a specific point."""
        center = Vect2D(2, 3)
        angle = math.pi / 3
        t = RigidTransform2D.create_rotate_around(center, angle)

        # Point at center should remain at center after transformation
        point = Vect2D(2, 3)
        t.apply_to_point(point)
        assert point.x == pytest.approx(2)
        assert point.y == pytest.approx(3)

    def test_copy(self):
        """Test that copy creates an independent instance."""
        t1 = RigidTransform2D(Vect2D(1, 2), math.pi / 4)
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
        t = RigidTransform2D.create_identity()
        point = Vect2D(3, 4)
        t.apply_to_point(point)
        assert point.x == pytest.approx(3)
        assert point.y == pytest.approx(4)

    def test_apply_translation_only(self):
        """Test apply with translation only."""
        t = RigidTransform2D.create_translate(Vect2D(2, -1))
        point = Vect2D(1, 3)
        t.apply_to_point(point)
        assert point.x == pytest.approx(3)
        assert point.y == pytest.approx(2)

    def test_apply_rotation_only(self):
        """Test apply with 90-degree rotation around origin."""
        t = RigidTransform2D(Vect2D(0, 0), math.pi / 2)
        point = Vect2D(1, 0)
        t.apply_to_point(point)
        # After 90-degree rotation: (1,0) -> (0,1)
        assert point.x == pytest.approx(0, abs=1e-10)
        assert point.y == pytest.approx(1)

    def test_apply_rotation_and_translation(self):
        """Test apply with both rotation and translation."""
        # Rotate 90 degrees then translate by (2, 3)
        t = RigidTransform2D(Vect2D(2, 3), math.pi / 2)
        point = Vect2D(1, 0)
        t.apply_to_point(point)
        # (1,0) rotated 90 degrees -> (0,1), then translated -> (2,4)
        assert point.x == pytest.approx(2)
        assert point.y == pytest.approx(4)

    def test_apply_negative_rotation(self):
        """Test apply with negative (clockwise) rotation."""
        t = RigidTransform2D(Vect2D(0, 0), -math.pi / 2)
        point = Vect2D(0, 1)
        t.apply_to_point(point)
        # After -90-degree rotation: (0,1) -> (1,0)
        assert point.x == pytest.approx(1)
        assert point.y == pytest.approx(0, abs=1e-10)


class TestRigidTransformComposition:
    """Test composing transformations."""

    def test_transform_composition(self):
        """Test applying one transform to another."""
        t1 = RigidTransform2D(Vect2D(1, 0), 0)  # translate by (1,0)
        t2 = RigidTransform2D(Vect2D(2, 0), 0)  # translate by (2,0)

        t1.transform(t2)

        # Offset should be combined: (1,0) + (2,0) = (3,0)
        assert t1.offset.x == pytest.approx(3)
        assert t1.offset.y == pytest.approx(0)

    def test_transform_with_rotation(self):
        """Test composition with rotation."""
        t1 = RigidTransform2D(Vect2D(1, 0), 0)
        t2 = RigidTransform2D(Vect2D(0, 0), math.pi / 2)

        initial_angle = t1.angle
        t1.transform(t2)

        # Angle should be sum of angles
        assert t1.angle == pytest.approx(initial_angle + math.pi / 2)


class TestRigidTransformModification:
    """Test modifying existing transforms."""

    def test_rotate(self):
        """Test adding rotation to transform."""
        t = RigidTransform2D(Vect2D(1, 2), 0)
        t.rotate(math.pi / 4)

        assert t.angle == pytest.approx(math.pi / 4)
        assert t._c == pytest.approx(math.cos(math.pi / 4))
        assert t._s == pytest.approx(math.sin(math.pi / 4))

    def test_translate(self):
        """Test adding translation to transform."""
        t = RigidTransform2D(Vect2D(1, 2), 0)
        t.translate(Vect2D(3, -1))

        assert t.offset.x == pytest.approx(4)
        assert t.offset.y == pytest.approx(1)

    def test_rotate_accumulates(self):
        """Test that rotate accumulates."""
        t = RigidTransform2D(Vect2D(0, 0), math.pi / 4)
        t.rotate(math.pi / 4)

        assert t.angle == pytest.approx(math.pi / 2)


class TestRigidTransformInversion:
    """Test negation (inversion) of transforms."""

    def test_negate_translation_only(self):
        """Test negation of pure translation."""
        t = RigidTransform2D(Vect2D(3, 4), 0)
        neg_t = -t

        assert neg_t.offset.x == pytest.approx(-3)
        assert neg_t.offset.y == pytest.approx(-4)
        assert neg_t.angle == pytest.approx(0)

    def test_negate_rotation_only(self):
        """Test negation of pure rotation."""
        t = RigidTransform2D(Vect2D(0, 0), math.pi / 3)
        neg_t = -t

        assert neg_t.angle == pytest.approx(-math.pi / 3)
        assert neg_t.offset.x == pytest.approx(0)
        assert neg_t.offset.y == pytest.approx(0)

    def test_negate_combined(self):
        """Test negation of combined rotation and translation."""
        t = RigidTransform2D(Vect2D(2, 0), math.pi / 2)
        neg_t = -t

        # Negated angle
        assert neg_t.angle == pytest.approx(-math.pi / 2)

        point = Vect2D(1, 0)
        t.apply_to_point(point)
        neg_t.apply_to_point(point)

        assert point.x == pytest.approx(1)
        assert point.y == pytest.approx(0)

    def test_double_negation_identity(self):
        """Test that double negation returns to original."""
        t = RigidTransform2D(Vect2D(3, 4), math.pi / 6)
        double_neg = -(-t)

        assert double_neg.offset.x == pytest.approx(t.offset.x)
        assert double_neg.offset.y == pytest.approx(t.offset.y)
        assert double_neg.angle == pytest.approx(t.angle)

    def test_inverse_cancels_transform(self):
        """Test that inverse transform cancels original."""
        t = RigidTransform2D(Vect2D(2, 3), math.pi / 4)
        neg_t = -t

        # Point after transform then inverse should return to original
        point = Vect2D(1, 1)
        original = point.copy()
        t.apply_to_point(point)
        neg_t.apply_to_point(point)

        assert point.x == pytest.approx(original.x)
        assert point.y == pytest.approx(original.y)


class TestAffineTransformConstruction:
    """Test AffineTransform2D instantiation."""

    def test_basic_construction(self):
        """Test basic construction with defaults."""
        t = AffineTransform2D()
        assert t.offset == Vect2D(0, 0)
        assert t.angle == 0
        assert t.factor == Vect2D(1, 1)

    def test_construction_with_parameters(self):
        """Test construction with all parameters."""
        offset = Vect2D(1, 2)
        angle = math.pi / 3
        scale = Vect2D(2, 3)
        t = AffineTransform2D(offset, angle, scale)

        assert t.offset == offset
        assert t.angle == pytest.approx(angle)
        assert t.factor == scale

    def test_copy(self):
        """Test that copy creates an independent instance."""
        t1 = AffineTransform2D(Vect2D(1, 2), math.pi / 4, Vect2D(2, 3))
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
        t = AffineTransform2D(Vect2D(0, 0), 0, Vect2D(1, 1))
        t.scale(Vect2D(2, 3))

        assert t.factor.x == pytest.approx(2)
        assert t.factor.y == pytest.approx(3)

    def test_scale_accumulates(self):
        """Test that scale accumulates."""
        t = AffineTransform2D(Vect2D(0, 0), 0, Vect2D(2, 2))
        t.scale(Vect2D(3, 4))

        assert t.factor.x == pytest.approx(6)
        assert t.factor.y == pytest.approx(8)

    def test_scale_asymmetric(self):
        """Test asymmetric scaling."""
        t = AffineTransform2D(Vect2D(0, 0), 0, Vect2D(1, 1))
        t.scale(Vect2D(2, 0.5))

        assert t.factor.x == pytest.approx(2)
        assert t.factor.y == pytest.approx(0.5)


class TestAffineTransformApply:
    """Test point transformation with affine transforms."""

    def test_apply_no_transformation(self):
        """Test apply with identity affine transform."""
        t = AffineTransform2D()
        point = Vect2D(3, 4)
        t.apply_to_point(point)
        assert point.x == pytest.approx(3)
        assert point.y == pytest.approx(4)

    def test_apply_scale_only(self):
        """Test apply with scaling only."""
        t = AffineTransform2D(Vect2D(0, 0), 0, Vect2D(2, 3))
        point = Vect2D(1, 1)
        t.apply_to_point(point)
        assert point.x == pytest.approx(2)
        assert point.y == pytest.approx(3)

    def test_apply_scale_then_rotate(self):
        """Test scale then rotation then translation."""
        # Scale by 2, rotate 90 degrees, translate by (1, 1)
        t = AffineTransform2D(Vect2D(1, 1), math.pi / 2, Vect2D(2, 1))
        point = Vect2D(1, 0)
        t.apply_to_point(point)

        # (1,0) scaled by (2,1) -> (2,0)
        # (2,0) rotated 90 degrees -> (0,2)
        # (0,2) translated by (1,1) -> (1,3)
        assert point.x == pytest.approx(1)
        assert point.y == pytest.approx(3)

    def test_apply_non_uniform_scale_then_rotate(self):
        """Test non-uniform scale with rotation."""
        t = AffineTransform2D(Vect2D(0, 0), math.pi / 2, Vect2D(2, 3))
        point = Vect2D(1, 1)
        t.apply_to_point(point)

        # (1,1) scaled by (2,3) -> (2,3)
        # (2,3) rotated 90 degrees -> (-3,2)
        assert point.x == pytest.approx(-3)
        assert point.y == pytest.approx(2)

    def test_apply_scale_zero(self):
        """Test scaling with zero factor (degenerate case)."""
        t = AffineTransform2D(Vect2D(0, 0), 0, Vect2D(0, 0))
        point = Vect2D(5, 10)
        t.apply_to_point(point)

        assert point.x == pytest.approx(0)
        assert point.y == pytest.approx(0)


class TestAffineTransformInheritance:
    """Test that AffineTransform2D correctly inherits from RigidTransform2D."""

    def test_rotate_method(self):
        """Test that rotate method from RigidTransform2D works."""
        t = AffineTransform2D(Vect2D(0, 0), 0, Vect2D(1, 1))
        t.rotate(math.pi / 4)

        assert t.angle == pytest.approx(math.pi / 4)

    def test_translate_method(self):
        """Test that translate method from RigidTransform2D works."""
        t = AffineTransform2D(Vect2D(1, 1), 0, Vect2D(1, 1))
        t.translate(Vect2D(2, 3))

        assert t.offset.x == pytest.approx(3)
        assert t.offset.y == pytest.approx(4)


class TestMirrorTransform2D:
    """Test axial symmetry transform."""

    def test_vertical_mirror_flips_y(self):
        t = MirrorTransform2D(Vect2D(0, 0), vertical=True)
        point = Vect2D(3, 5)
        t.apply_to_point(point)
        assert point.x == pytest.approx(3)
        assert point.y == pytest.approx(-5)

    def test_horizontal_mirror_flips_x(self):
        t = MirrorTransform2D(Vect2D(0, 0), vertical=False)
        point = Vect2D(3, 5)
        t.apply_to_point(point)
        assert point.x == pytest.approx(-3)
        assert point.y == pytest.approx(5)

    def test_mirror_with_offset(self):
        t = MirrorTransform2D(Vect2D(10, 0), vertical=True)
        point = Vect2D(3, 5)
        t.apply_to_point(point)
        assert point.x == pytest.approx(13)
        assert point.y == pytest.approx(-5)

    def test_angle_flip_vertical(self):
        t = MirrorTransform2D(Vect2D(0, 0), vertical=True)
        assert t.apply_to_angle(math.pi / 3) == pytest.approx(-math.pi / 3)

    def test_angle_flip_horizontal(self):
        t = MirrorTransform2D(Vect2D(0, 0), vertical=False)
        assert t.apply_to_angle(math.pi / 3) == pytest.approx(math.pi - math.pi / 3)

    def test_copy_is_independent(self):
        t1 = MirrorTransform2D(Vect2D(10, 20), vertical=True)
        t2 = t1.copy()
        t1._offset.x = 99
        assert t2._offset.x == 10


class TestApplyToPose:
    """Test that apply_to_pose actually mutates the pose."""

    def test_rigid_apply_to_pose_translation(self):
        t = RigidTransform2D(Vect2D(10, 20), 0)
        pose = Pose2D(1, 2, 0)
        t.apply_to_pose(pose)
        assert pose.x == pytest.approx(11)
        assert pose.y == pytest.approx(22)
        assert pose.theta == pytest.approx(0)

    def test_rigid_apply_to_pose_rotation(self):
        t = RigidTransform2D(Vect2D(0, 0), math.pi / 2)
        pose = Pose2D(1, 0, 0)
        t.apply_to_pose(pose)
        assert pose.x == pytest.approx(0, abs=1e-10)
        assert pose.y == pytest.approx(1)
        assert pose.theta == pytest.approx(math.pi / 2)

    def test_apply_to_pose_updates_cached_trig(self):
        """After apply_to_pose, the cached (_c, _s) must match the new theta."""
        t = RigidTransform2D(Vect2D(0, 0), math.pi / 4)
        pose = Pose2D(0, 0, 0)
        t.apply_to_pose(pose)
        assert pose._c == pytest.approx(math.cos(math.pi / 4))
        assert pose._s == pytest.approx(math.sin(math.pi / 4))
