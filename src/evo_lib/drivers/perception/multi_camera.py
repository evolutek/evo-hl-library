"""Multi-camera ArUco aggregator: fuses detections from N cameras."""

import math
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.interfaces.camera import ArucoMarker, Camera
from evo_lib.peripheral import Peripheral
from evo_lib.registry import Registry
from evo_lib.task import ImmediateResultTask, Task
from evo_lib.types.pose import Pose3D


_BRICK_STRUCT = ArgTypes.Struct(
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
        ("source_camera", ArgTypes.String()),
    ]
)


def _safe_detect(cam: Camera) -> list[ArucoMarker]:
    try:
        return cam.detect()
    except Exception:
        return []


class MultiCamera(Peripheral):
    """Aggregates several Cameras: one row per (camera, marker) observation."""

    commands = DriverCommands()

    def __init__(self, name: str, cameras: list[Camera]):
        super().__init__(name)
        self._cameras = list(cameras)
        # ComponentsManager skips Array-typed deps; wire both directions here.
        for cam in self._cameras:
            self.add_dependency(cam)
            cam.add_dependent(self)
        self._pool: ThreadPoolExecutor | None = None

    def init(self) -> Task[()]:
        self._pool = ThreadPoolExecutor(
            max_workers=max(1, len(self._cameras)),
            thread_name_prefix=f"multicam-{self.name}",
        )
        return ImmediateResultTask()

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None

    def _detect_all_robot(self) -> list[ArucoMarker]:
        if self._pool is None:
            raise RuntimeError(f"MultiCamera '{self.name}' not initialized")
        futures = [(cam, self._pool.submit(_safe_detect, cam)) for cam in self._cameras]
        out: list[ArucoMarker] = []
        for cam, fut in futures:
            for m in fut.result():
                if m.position_robot_mm is None or m.quat_robot is None:
                    continue
                m.source_camera = cam.name
                out.append(m)
        return out

    @commands.register(
        args=[],
        result=[("bricks", ArgTypes.Array(_BRICK_STRUCT))],
    )
    def get_bricks_robot(self) -> "Task[list[dict[str, Any]]]":
        """All ArUco observations in the robot frame, one row per (camera, marker)."""
        out: list[dict[str, Any]] = []
        for m in self._detect_all_robot():
            assert m.position_robot_mm is not None and m.quat_robot is not None
            qw, qx, qy, qz = m.quat_robot
            px, py, pz = m.position_robot_mm
            out.append(
                {
                    "id": int(m.id),
                    "x_mm": float(px),
                    "y_mm": float(py),
                    "z_mm": float(pz),
                    "qw": qw,
                    "qx": qx,
                    "qy": qy,
                    "qz": qz,
                    "yaw_deg": math.degrees(m.yaw_robot_rad) if m.yaw_robot_rad is not None else 0.0,
                    "source_camera": m.source_camera or "",
                }
            )
        return ImmediateResultTask(out)

    @commands.register(
        args=[
            ("x_mm", ArgTypes.F32()),
            ("y_mm", ArgTypes.F32()),
            ("yaw_deg", ArgTypes.F32()),
        ],
        result=[("bricks", ArgTypes.Array(_BRICK_STRUCT))],
    )
    def get_bricks_table(
        self, x_mm: float, y_mm: float, yaw_deg: float
    ) -> "Task[list[dict[str, Any]]]":
        """All ArUco observations in the table frame, given the robot pose in the table."""
        T_table_robot = Pose3D(x_mm, y_mm, 0.0, 0.0, 0.0, math.radians(yaw_deg))
        out: list[dict[str, Any]] = []
        for m in self._detect_all_robot():
            assert m.position_robot_mm is not None and m.quat_robot is not None
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
                    "source_camera": m.source_camera or "",
                }
            )
        return ImmediateResultTask(out)


class MultiCameraDefinition(DriverDefinition):
    def __init__(self, peripherals: Registry[Peripheral]):
        super().__init__(MultiCamera.commands)
        self._peripherals = peripherals

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required(
            "cameras",
            ArgTypes.Array(ArgTypes.Component(Camera, self._peripherals)),
        )
        return defn

    def create(self, args: DriverInitArgs) -> MultiCamera:
        return MultiCamera(name=args.get_name(), cameras=args.get("cameras"))
