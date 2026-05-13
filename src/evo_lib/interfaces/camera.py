"""Camera abstract interface and ArUco data types."""

import math
from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import DriverCommands
from evo_lib.peripheral import Placable
from evo_lib.task import ImmediateResultTask, Task

if TYPE_CHECKING:
    import numpy as np


DEFAULT_ARUCO_DICTIONARY = "DICT_4X4_100"
DEFAULT_CHARUCO_SQUARES_X = 5
DEFAULT_CHARUCO_SQUARES_Y = 5
DEFAULT_CHARUCO_SQUARE_MM = 40.0
DEFAULT_CHARUCO_MARKER_MM = 32.0


@dataclass(slots=True)
class ArucoMarker:
    id: int
    corners: "np.ndarray"
    rvec_camera: "np.ndarray | None" = None
    tvec_camera: "np.ndarray | None" = None
    position_robot_mm: "np.ndarray | None" = None
    # (qw, qx, qy, qz) — full rotation; needed for tilted markers where yaw alone loses info.
    quat_robot: "tuple[float, float, float, float] | None" = None
    yaw_robot_rad: "float | None" = None


_MARKER_STRUCT = ArgTypes.Struct(
    [
        ("id", ArgTypes.U32()),
        ("x_mm", ArgTypes.F32()),
        ("y_mm", ArgTypes.F32()),
        ("z_mm", ArgTypes.F32()),
        ("qw", ArgTypes.F32()),
        ("qx", ArgTypes.F32()),
        ("qy", ArgTypes.F32()),
        ("qz", ArgTypes.F32()),
        ("yaw_deg", ArgTypes.F32()),
    ]
)


def _marker_to_robot_dict(m: ArucoMarker) -> dict[str, Any]:
    pos = m.position_robot_mm
    qw, qx, qy, qz = m.quat_robot if m.quat_robot is not None else (1.0, 0.0, 0.0, 0.0)
    return {
        "id": int(m.id),
        "x_mm": float(pos[0]),
        "y_mm": float(pos[1]),
        "z_mm": float(pos[2]),
        "qw": qw,
        "qx": qx,
        "qy": qy,
        "qz": qz,
        "yaw_deg": math.degrees(m.yaw_robot_rad) if m.yaw_robot_rad is not None else 0.0,
    }


class Camera(Placable):
    commands = DriverCommands()

    @abstractmethod
    def capture(self) -> "np.ndarray":
        """One frame, BGR uint8 (height, width, 3). Stale buffers must be dropped."""

    @abstractmethod
    def detect(self) -> list[ArucoMarker]:
        """Capture and return detected ArUco markers.

        Pose fields are populated only if intrinsics are loaded;
        position_robot_mm and yaw_robot_rad only if extrinsics are also loaded.
        """

    @abstractmethod
    def set_focus(self, value: int) -> "Task[()]": ...

    @abstractmethod
    def set_setting(self, name: str, value: int) -> "Task[()]": ...

    @abstractmethod
    def is_intrinsics_loaded(self) -> bool: ...

    @abstractmethod
    def is_extrinsics_loaded(self) -> bool: ...

    @abstractmethod
    def save_calibration(self, path: str | None = None) -> None: ...

    @property
    @abstractmethod
    def width(self) -> int: ...

    @property
    @abstractmethod
    def height(self) -> int: ...

    @commands.register(
        args=[],
        result=[("ids", ArgTypes.Array(ArgTypes.U32()))],
    )
    def get_marker_ids(self) -> "Task[list[int]]":
        """List ArUco ids visible in the current frame. No calibration needed."""
        return ImmediateResultTask([int(m.id) for m in self.detect()])

    @commands.register(
        args=[],
        result=[("markers", ArgTypes.Array(_MARKER_STRUCT))],
    )
    def get_markers_robot(self) -> "Task[list[dict[str, Any]]]":
        """List markers with pose in the robot frame. Requires extrinsics."""
        return ImmediateResultTask(
            [_marker_to_robot_dict(m) for m in self.detect() if m.position_robot_mm is not None]
        )

    @commands.register(
        args=[
            ("x_mm", ArgTypes.F32()),
            ("y_mm", ArgTypes.F32()),
            ("yaw_deg", ArgTypes.F32()),
        ],
        result=[("markers", ArgTypes.Array(_MARKER_STRUCT))],
    )
    def get_markers_table(
        self, x_mm: float, y_mm: float, yaw_deg: float
    ) -> "Task[list[dict[str, Any]]]":
        """List markers in the table frame, given the robot pose in the table.

        TODO: when Trajman exposes the live robot pose, drop the args here and
        fall back to that provider so the AI can call it without arguments.
        """
        from evo_lib.types.pose import Pose3D

        T_table_robot = Pose3D(x_mm, y_mm, 0.0, 0.0, 0.0, math.radians(yaw_deg))
        out: list[dict[str, Any]] = []
        for m in self.detect():
            if m.position_robot_mm is None or m.quat_robot is None:
                continue
            xr, yr, zr = (
                float(m.position_robot_mm[0]),
                float(m.position_robot_mm[1]),
                float(m.position_robot_mm[2]),
            )
            qw, qx, qy, qz = m.quat_robot
            T_robot_marker = Pose3D.from_quaternion(xr, yr, zr, qw, qx, qy, qz)
            T_table_marker = T_table_robot.compose(T_robot_marker)
            out.append(
                {
                    "id": int(m.id),
                    "x_mm": T_table_marker.x,
                    "y_mm": T_table_marker.y,
                    "z_mm": T_table_marker.z,
                    "qw": T_table_marker.qw,
                    "qx": T_table_marker.qx,
                    "qy": T_table_marker.qy,
                    "qz": T_table_marker.qz,
                    "yaw_deg": math.degrees(T_table_marker.yaw),
                }
            )
        return ImmediateResultTask(out)
