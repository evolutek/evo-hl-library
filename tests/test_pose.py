"""Tests for the vector type hierarchy."""

import math

from evo_lib.types.pose import (
    Pose2D,
    Pose3D,
)
from evo_lib.types.vect import (
    Vect2D,
    Vect3D,
)

# ===========================================================================
# Pose2D
# ===========================================================================


class TestPose2DConstruction:
    def test_basic(self):
        p = Pose2D(100, 200, 1.57)
        assert p.x == 100.0
        assert p.y == 200.0
        assert math.isclose(p.theta, 1.57)

    def test_theta_defaults_to_zero(self):
        p = Pose2D(10, 20)
        assert p.theta == 0.0


class TestPose2DPosition:
    def test_position_property(self):
        p = Pose2D(10, 20, 0.5)
        assert p.position == Vect2D(10, 20)


class TestPose2DTransform:
    def test_identity(self):
        """Transform at origin with no rotation is identity."""
        origin = Pose2D(0, 0, 0)
        point = Vect2D(5, 3)
        assert origin.transform(point) == point

    def test_translation_only(self):
        pose = Pose2D(100, 200, 0)
        point = Vect2D(5, 3)
        assert pose.transform(point) == Vect2D(105, 203)

    def test_rotation_90(self):
        """Sensor at origin, rotated 90 degrees."""
        pose = Pose2D(0, 0, math.pi / 2)
        point = Vect2D(1, 0)
        result = pose.transform(point)
        assert math.isclose(result.x, 0, abs_tol=1e-9)
        assert math.isclose(result.y, 1)

    def test_full_transform(self):
        """Sensor at (100, 50), facing right (theta=0), detects object at (30, 0) in sensor frame."""
        sensor = Pose2D(100, 50, 0)
        detection = Vect2D(30, 0)
        result = sensor.transform(detection)
        assert result == Vect2D(130, 50)

    def test_change_referencial_legacy(self):
        """Reproduce the legacy change_referencial behavior.

        global_pos = local_point.change_referencial(robot_pos, robot_theta)
        becomes: robot_pose.transform(local_point)
        """
        robot = Pose2D(500, 300, math.pi / 2)
        local = Vect2D(100, 0)
        result = robot.transform(local)
        assert math.isclose(result.x, 500, abs_tol=1e-9)
        assert math.isclose(result.y, 400)


class TestPose2DInverse:
    def test_inverse_roundtrip(self):
        pose = Pose2D(100, 200, 0.7)
        point = Vect2D(50, 30)
        transformed = pose.transform(point)
        recovered = pose.inverse().transform(transformed)
        assert math.isclose(recovered.x, point.x, abs_tol=1e-9)
        assert math.isclose(recovered.y, point.y, abs_tol=1e-9)


class TestPose2DCompose:
    def test_compose_translations(self):
        a = Pose2D(10, 20, 0)
        b = Pose2D(5, 3, 0)
        c = a.compose(b)
        assert c == Pose2D(15, 23, 0)

    def test_compose_with_rotation(self):
        """Robot at (100, 0) facing up, sensor at (0, 50) locally."""
        robot = Pose2D(100, 0, math.pi / 2)
        sensor_local = Pose2D(0, 50, 0)
        sensor_global = robot.compose(sensor_local)
        assert math.isclose(sensor_global.x, 50, abs_tol=1e-9)
        assert math.isclose(sensor_global.y, 0, abs_tol=1e-9)
        assert math.isclose(sensor_global.theta, math.pi / 2)


class TestPose2DFromDict:
    def test_full(self):
        p = Pose2D.from_dict({"x": 10, "y": 20, "theta": 0.5})
        assert p == Pose2D(10, 20, 0.5)

    def test_missing_theta(self):
        p = Pose2D.from_dict({"x": 10, "y": 20})
        assert p.theta == 0.0

    def test_from_config_like_dict(self):
        config = {
            "driver": "rplidar",
            "port": "/dev/ttyUSB0",
            "pose": {"x": 0, "y": 85, "theta": 0},
        }
        pose = Pose2D.from_dict(config["pose"])
        assert pose == Pose2D(0, 85, 0)


class TestPose2DToDict:
    def test_basic(self):
        assert Pose2D(10, 20, 0.5).to_dict() == {"x": 10.0, "y": 20.0, "theta": 0.5}

    def test_round_trip(self):
        p = Pose2D(10, 20, 0.5)
        assert Pose2D.from_dict(p.to_dict()) == p


class TestPose2DConversion:
    def test_to_3d(self):
        p = Pose2D(10, 20, 0.5)
        p3 = p.to_3d(z=100)
        assert p3 == Pose3D(10, 20, 100, yaw=0.5)


class TestPose2DEquality:
    def test_equal(self):
        assert Pose2D(1, 2, 0.5) == Pose2D(1, 2, 0.5)

    def test_not_equal(self):
        assert Pose2D(1, 2, 0.5) != Pose2D(1, 2, 0.6)

    def test_not_equal_to_other_type(self):
        assert Pose2D(1, 2, 0) != Vect2D(1, 2)


class TestPose2DRepr:
    def test_repr(self):
        assert repr(Pose2D(10, 20, 0.5)) == "Pose2D(x=10.0, y=20.0, theta=0.5)"


# ===========================================================================
# Pose3D
# ===========================================================================


class TestPose3DConstruction:
    def test_basic(self):
        p = Pose3D(1, 2, 3, 0.1, 0.2, 0.3)
        assert p.x == 1.0
        assert p.y == 2.0
        assert p.z == 3.0
        assert math.isclose(p.roll, 0.1, abs_tol=1e-12)
        assert math.isclose(p.pitch, 0.2, abs_tol=1e-12)
        assert math.isclose(p.yaw, 0.3, abs_tol=1e-12)

    def test_angles_default_to_zero(self):
        p = Pose3D(1, 2, 3)
        assert p.roll == 0.0
        assert p.pitch == 0.0
        assert p.yaw == 0.0

    def test_quaternion_identity(self):
        p = Pose3D(0, 0, 0)
        assert p.quaternion == (1.0, 0.0, 0.0, 0.0)

    def test_quaternion_yaw_90(self):
        p = Pose3D(0, 0, 0, yaw=math.pi / 2)
        qw, qx, qy, qz = p.quaternion
        assert math.isclose(qw, math.cos(math.pi / 4))
        assert math.isclose(qx, 0, abs_tol=1e-15)
        assert math.isclose(qy, 0, abs_tol=1e-15)
        assert math.isclose(qz, math.sin(math.pi / 4))

    def test_from_quaternion(self):
        p = Pose3D.from_quaternion(10, 20, 30, 1, 0, 0, 0)
        assert p.x == 10.0
        assert p.roll == 0.0

    def test_euler_round_trip(self):
        """Euler -> quaternion -> Euler should be stable."""
        p = Pose3D(0, 0, 0, 0.3, 0.5, 0.7)
        assert math.isclose(p.roll, 0.3, abs_tol=1e-12)
        assert math.isclose(p.pitch, 0.5, abs_tol=1e-12)
        assert math.isclose(p.yaw, 0.7, abs_tol=1e-12)


class TestPose3DPosition:
    def test_position_property(self):
        p = Pose3D(1, 2, 3, 0.1, 0.2, 0.3)
        assert p.position == Vect3D(1, 2, 3)


class TestPose3DTransform:
    def test_identity(self):
        origin = Pose3D(0, 0, 0)
        point = Vect3D(5, 3, 1)
        assert origin.transform(point) == point

    def test_translation_only(self):
        pose = Pose3D(10, 20, 30)
        point = Vect3D(1, 2, 3)
        assert pose.transform(point) == Vect3D(11, 22, 33)

    def test_yaw_only_matches_2d(self):
        """With only yaw, 3D transform should match 2D."""
        pose_2d = Pose2D(100, 50, math.pi / 4)
        pose_3d = Pose3D(100, 50, 0, yaw=math.pi / 4)
        point_2d = Vect2D(10, 0)
        point_3d = Vect3D(10, 0, 0)
        result_2d = pose_2d.transform(point_2d)
        result_3d = pose_3d.transform(point_3d)
        assert math.isclose(result_2d.x, result_3d.x, abs_tol=1e-9)
        assert math.isclose(result_2d.y, result_3d.y, abs_tol=1e-9)


class TestPose3DInverse:
    def test_inverse_roundtrip(self):
        pose = Pose3D(10, 20, 30, 0.1, 0.2, 0.3)
        point = Vect3D(5, 3, 1)
        transformed = pose.transform(point)
        recovered = pose.inverse().transform(transformed)
        assert math.isclose(recovered.x, point.x, abs_tol=1e-6)
        assert math.isclose(recovered.y, point.y, abs_tol=1e-6)
        assert math.isclose(recovered.z, point.z, abs_tol=1e-6)


class TestPose3DCompose:
    def test_compose_translations(self):
        a = Pose3D(10, 20, 30)
        b = Pose3D(5, 3, 1)
        c = a.compose(b)
        assert c == Pose3D(15, 23, 31)

    def test_compose_with_yaw(self):
        """Matches 2D compose when only yaw is used."""
        robot_2d = Pose2D(100, 0, math.pi / 2)
        sensor_2d = Pose2D(0, 50, 0)
        result_2d = robot_2d.compose(sensor_2d)

        robot_3d = Pose3D(100, 0, 0, yaw=math.pi / 2)
        sensor_3d = Pose3D(0, 50, 0)
        result_3d = robot_3d.compose(sensor_3d)

        assert math.isclose(result_2d.x, result_3d.x, abs_tol=1e-9)
        assert math.isclose(result_2d.y, result_3d.y, abs_tol=1e-9)
        assert math.isclose(result_2d.theta, result_3d.yaw, abs_tol=1e-9)

    def test_compose_with_pitch_only(self):
        """Pitch-only compose: sensor tilted 90° down sees (0,0,-100) → (100,0,0) in parent."""
        parent = Pose3D(0, 0, 0, pitch=math.pi / 2)
        child = Pose3D(100, 0, 0)
        composed = parent.compose(child)
        # pitch=90° rotates X→Z, so child at (100,0,0) local becomes (0,0,-100)... wait
        # Actually: parent.transform((100,0,0)) with pitch=pi/2
        # R with pitch=pi/2: sp=1, cp=0, no roll, no yaw
        # r = (0, 0, 1,  0, 1, 0,  -1, 0, 0)
        # x' = 0*100 + 0*0 + 1*0 = 0, y' = 0, z' = -100
        assert math.isclose(composed.x, 0, abs_tol=1e-9)
        assert math.isclose(composed.y, 0, abs_tol=1e-9)
        assert math.isclose(composed.z, -100, abs_tol=1e-9)
        assert math.isclose(composed.pitch, math.pi / 2, abs_tol=1e-9)

    def test_compose_inverse_gives_identity(self):
        pose = Pose3D(10, 20, 30, 0.1, 0.2, 0.3)
        identity = pose.compose(pose.inverse())
        assert math.isclose(identity.x, 0, abs_tol=1e-6)
        assert math.isclose(identity.y, 0, abs_tol=1e-6)
        assert math.isclose(identity.z, 0, abs_tol=1e-6)
        assert math.isclose(identity.roll, 0, abs_tol=1e-6)
        assert math.isclose(identity.pitch, 0, abs_tol=1e-6)
        assert math.isclose(identity.yaw, 0, abs_tol=1e-6)

    def test_compose_equivalence_with_transform(self):
        """compose(a, b).transform(p) == a.transform(b.transform(p))"""
        a = Pose3D(10, 20, 30, 0.1, 0.2, 0.3)
        b = Pose3D(5, 3, 1, 0.05, 0.1, 0.15)
        p = Vect3D(7, 11, 13)
        via_compose = a.compose(b).transform(p)
        via_chain = a.transform(b.transform(p))
        assert math.isclose(via_compose.x, via_chain.x, abs_tol=1e-6)
        assert math.isclose(via_compose.y, via_chain.y, abs_tol=1e-6)
        assert math.isclose(via_compose.z, via_chain.z, abs_tol=1e-6)


class TestPose3DToDict:
    def test_basic(self):
        d = Pose3D(1, 2, 3, 0.1, 0.2, 0.3).to_dict()
        assert d["x"] == 1.0
        assert d["y"] == 2.0
        assert d["z"] == 3.0
        assert math.isclose(d["roll"], 0.1, abs_tol=1e-12)
        assert math.isclose(d["pitch"], 0.2, abs_tol=1e-12)
        assert math.isclose(d["yaw"], 0.3, abs_tol=1e-12)

    def test_round_trip(self):
        p = Pose3D(1, 2, 3, 0.1, 0.2, 0.3)
        assert Pose3D.from_dict(p.to_dict()) == p


class TestPose3DFromDict:
    def test_full(self):
        p = Pose3D.from_dict({"x": 1, "y": 2, "z": 3, "roll": 0.1, "pitch": 0.2, "yaw": 0.3})
        assert p == Pose3D(1, 2, 3, 0.1, 0.2, 0.3)

    def test_angles_default(self):
        p = Pose3D.from_dict({"x": 1, "y": 2, "z": 3})
        assert p.roll == 0.0
        assert p.pitch == 0.0
        assert p.yaw == 0.0


class TestPose3DConversion:
    def test_to_2d(self):
        p = Pose3D(10, 20, 30, 0.1, 0.2, 0.3)
        p2 = p.to_2d()
        assert p2 == Pose2D(10, 20, 0.3)


class TestPose3DRepr:
    def test_repr(self):
        p = Pose3D(1, 2, 3)
        assert repr(p) == "Pose3D(x=1.0, y=2.0, z=3.0, roll=0.0, pitch=0.0, yaw=0.0)"
