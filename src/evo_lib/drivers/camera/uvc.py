"""UVC (V4L2) camera driver with built-in ArUco detection and ChArUco calibration."""

from __future__ import annotations

import os
import subprocess
import threading
import time
from typing import TYPE_CHECKING, Any

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
    DriverCommands,
    DriverDefinition,
    DriverInitArgs,
    DriverInitArgsDefinition,
)
from evo_lib.drivers.camera.aruco import (
    CharucoCalibrationSession,
    _aruco_dict_from_name,
    _build_charuco_board,
    _marker_object_points,
    _now_iso,
)
from evo_lib.interfaces.camera import (
    DEFAULT_ARUCO_DICTIONARY,
    DEFAULT_CHARUCO_MARKER_MM,
    DEFAULT_CHARUCO_SQUARE_MM,
    DEFAULT_CHARUCO_SQUARES_X,
    DEFAULT_CHARUCO_SQUARES_Y,
    ArucoMarker,
    Camera,
)
from evo_lib.logger import Logger
from evo_lib.task import ImmediateResultTask, Task

if TYPE_CHECKING:
    import numpy as np


DEFAULT_FOURCC = "MJPG"
DEFAULT_WIDTH = 1920
DEFAULT_HEIGHT = 1080


def _v4l2_set_ctrl(device: str, ctrl: str, value: int) -> tuple[bool, str]:
    result = subprocess.run(
        ["v4l2-ctl", "-d", device, f"--set-ctrl={ctrl}={value}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        text=True,
    )
    return result.returncode == 0, (result.stderr or "").strip()


def _v4l2_has_ctrl(device: str, ctrl: str) -> bool:
    result = subprocess.run(
        ["v4l2-ctl", "-d", device, "--list-ctrls"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and ctrl in result.stdout


def _rot_to_quat(R: "np.ndarray") -> tuple[float, float, float, float]:
    """3x3 rotation matrix to (qw, qx, qy, qz) unit quaternion (Shepperd's method)."""
    import numpy as np

    trace = R[0, 0] + R[1, 1] + R[2, 2]
    if trace > 0.0:
        s = 2.0 * np.sqrt(1.0 + trace)
        return (
            float(0.25 * s),
            float((R[2, 1] - R[1, 2]) / s),
            float((R[0, 2] - R[2, 0]) / s),
            float((R[1, 0] - R[0, 1]) / s),
        )
    if R[0, 0] > R[1, 1] and R[0, 0] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[0, 0] - R[1, 1] - R[2, 2])
        return (
            float((R[2, 1] - R[1, 2]) / s),
            float(0.25 * s),
            float((R[0, 1] + R[1, 0]) / s),
            float((R[0, 2] + R[2, 0]) / s),
        )
    if R[1, 1] > R[2, 2]:
        s = 2.0 * np.sqrt(1.0 + R[1, 1] - R[0, 0] - R[2, 2])
        return (
            float((R[0, 2] - R[2, 0]) / s),
            float((R[0, 1] + R[1, 0]) / s),
            float(0.25 * s),
            float((R[1, 2] + R[2, 1]) / s),
        )
    s = 2.0 * np.sqrt(1.0 + R[2, 2] - R[0, 0] - R[1, 1])
    return (
        float((R[1, 0] - R[0, 1]) / s),
        float((R[0, 2] + R[2, 0]) / s),
        float((R[1, 2] + R[2, 1]) / s),
        float(0.25 * s),
    )


class _ArucoState:
    """Detection + calibration state shared between UvcCamera and UvcCameraVirtual."""

    def __init__(
        self,
        marker_size_mm: float,
        dictionary: str,
        charuco_squares_x: int,
        charuco_squares_y: int,
        charuco_square_mm: float,
        charuco_marker_mm: float,
        calibration_path: str | None,
    ):
        self.marker_size_mm = marker_size_mm
        self.dictionary_name = dictionary
        self.charuco_geom = (
            charuco_squares_x,
            charuco_squares_y,
            charuco_square_mm,
            charuco_marker_mm,
        )
        self.calibration_path = calibration_path
        self.K = None
        self.dist = None
        self.image_size: tuple[int, int] | None = None
        self.R_robot_camera = None
        self.t_robot_camera = None
        self._obj_pts_cache: dict[float, "np.ndarray"] = {
            marker_size_mm: _marker_object_points(marker_size_mm)
        }
        self._detector_handle = None

    def _obj_pts_for(self, size_mm: float) -> "np.ndarray":
        cached = self._obj_pts_cache.get(size_mm)
        if cached is None:
            cached = _marker_object_points(size_mm)
            self._obj_pts_cache[size_mm] = cached
        return cached

    def _size_for_id(self, marker_id: int) -> float:
        from evo_lib.types import EUROBOT_TAG_SIZES_MM

        return EUROBOT_TAG_SIZES_MM.get(marker_id, self.marker_size_mm)

    def detector(self) -> Any:
        import cv2

        if self._detector_handle is None:
            dictionary = _aruco_dict_from_name(self.dictionary_name)
            self._detector_handle = cv2.aruco.ArucoDetector(
                dictionary, cv2.aruco.DetectorParameters()
            )
        return self._detector_handle

    def detect_in_frame(self, frame: "np.ndarray") -> list[ArucoMarker]:
        import cv2
        import numpy as np

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if frame.ndim == 3 else frame
        marker_corners, marker_ids, _ = self.detector().detectMarkers(gray)
        if marker_ids is None or len(marker_ids) == 0:
            return []

        results: list[ArucoMarker] = []
        for i, marker_id in enumerate(marker_ids.flatten()):
            corners_ij = marker_corners[i].reshape(4, 2).astype(np.float32)
            mid = int(marker_id)
            marker = ArucoMarker(id=mid, corners=corners_ij)
            if self.K is not None and self.dist is not None:
                obj_pts = self._obj_pts_for(self._size_for_id(mid))
                ok, rvec, tvec = cv2.solvePnP(
                    obj_pts,
                    corners_ij,
                    self.K,
                    self.dist,
                    flags=cv2.SOLVEPNP_IPPE_SQUARE,
                )
                if ok:
                    marker.rvec_camera = rvec.reshape(3)
                    marker.tvec_camera = tvec.reshape(3)
                    if self.R_robot_camera is not None and self.t_robot_camera is not None:
                        pos_robot = self.R_robot_camera @ marker.tvec_camera.reshape(
                            3, 1
                        ) + self.t_robot_camera.reshape(3, 1)
                        marker.position_robot_mm = pos_robot.reshape(3)
                        R_camera_marker, _ = cv2.Rodrigues(rvec)
                        R_robot_marker = self.R_robot_camera @ R_camera_marker
                        qw, qx, qy, qz = _rot_to_quat(R_robot_marker)
                        marker.quat_robot = (qw, qx, qy, qz)
                        siny = 2.0 * (qw * qz + qx * qy)
                        cosy = 1.0 - 2.0 * (qy * qy + qz * qz)
                        marker.yaw_robot_rad = float(np.arctan2(siny, cosy))
            results.append(marker)
        return results

    def calibration_session(self) -> CharucoCalibrationSession:
        sx, sy, sq_mm, mk_mm = self.charuco_geom
        board = _build_charuco_board(sx, sy, sq_mm, mk_mm, self.dictionary_name)
        dictionary = _aruco_dict_from_name(self.dictionary_name)
        return CharucoCalibrationSession(board=board, dictionary=dictionary)

    def apply_intrinsics(self, intrinsics: dict[str, Any]) -> None:
        import numpy as np

        self.K = np.asarray(intrinsics["K"], dtype=np.float64).reshape(3, 3)
        self.dist = np.asarray(intrinsics["dist"], dtype=np.float64).reshape(-1)
        self.image_size = tuple(intrinsics["image_size"])

    def is_intrinsics_loaded(self) -> bool:
        return self.K is not None and self.dist is not None

    def is_extrinsics_loaded(self) -> bool:
        return self.R_robot_camera is not None and self.t_robot_camera is not None

    def calibrate_extrinsics(
        self,
        markers: list[ArucoMarker],
        reference_marker_id: int,
        R_robot_marker: "np.ndarray",
        t_robot_marker_mm: "np.ndarray",
    ) -> dict[str, Any]:
        # T_robot_camera = T_robot_marker @ inv(T_camera_marker).
        # Rotation matrices are orthonormal so R^{-1} = R^T (no expensive inverse).
        import cv2
        import numpy as np

        if self.K is None or self.dist is None:
            raise RuntimeError("Cannot calibrate extrinsics without intrinsics first.")

        target = next((m for m in markers if m.id == reference_marker_id), None)
        if target is None or target.rvec_camera is None or target.tvec_camera is None:
            raise RuntimeError(
                f"Reference marker {reference_marker_id} not visible "
                f"(detected ids: {[m.id for m in markers]})"
            )

        R_camera_marker, _ = cv2.Rodrigues(target.rvec_camera.reshape(3, 1))
        t_camera_marker = target.tvec_camera.reshape(3, 1)
        R_marker_camera = R_camera_marker.T
        t_marker_camera = -R_marker_camera @ t_camera_marker

        R_robot_camera = np.asarray(R_robot_marker) @ R_marker_camera
        t_robot_camera = np.asarray(R_robot_marker) @ t_marker_camera + np.asarray(
            t_robot_marker_mm
        ).reshape(3, 1)

        self.R_robot_camera = R_robot_camera
        self.t_robot_camera = t_robot_camera

        return {
            "R_robot_camera": R_robot_camera.flatten().tolist(),
            "t_robot_camera_mm": t_robot_camera.flatten().tolist(),
            "reference_marker_id": int(reference_marker_id),
            "captured_at": _now_iso(),
        }

    def load(self, path: str | None = None) -> bool:
        target = path or self.calibration_path
        if target is None or not os.path.exists(target):
            return False

        import json5
        import numpy as np

        with open(target, "r") as f:
            data = json5.load(f)

        intr = data.get("intrinsics")
        if intr is not None:
            self.K = np.asarray(intr["K"], dtype=np.float64).reshape(3, 3)
            self.dist = np.asarray(intr["dist"], dtype=np.float64).reshape(-1)
            self.image_size = tuple(intr.get("image_size", (0, 0)))

        extr = data.get("extrinsics")
        if extr is not None:
            # Legacy json5 used R_world_camera / t_world_camera_mm — accept both
            # so robots calibrated before the rename keep working without
            # forcing a recalibration.
            R_key = "R_robot_camera" if "R_robot_camera" in extr else "R_world_camera"
            t_key = "t_robot_camera_mm" if "t_robot_camera_mm" in extr else "t_world_camera_mm"
            self.R_robot_camera = np.asarray(extr[R_key], dtype=np.float64).reshape(3, 3)
            self.t_robot_camera = np.asarray(extr[t_key], dtype=np.float64).reshape(3)
        return intr is not None or extr is not None

    def save(self, path: str | None = None) -> str:
        target = path or self.calibration_path
        if target is None:
            raise RuntimeError("no calibration_path configured")

        import json5

        os.makedirs(os.path.dirname(target), exist_ok=True)
        payload: dict[str, Any] = {}
        if self.K is not None and self.dist is not None:
            payload["intrinsics"] = {
                "K": self.K.flatten().tolist(),
                "dist": self.dist.flatten().tolist(),
                "image_size": list(self.image_size or (0, 0)),
                "captured_at": _now_iso(),
            }
        if self.R_robot_camera is not None and self.t_robot_camera is not None:
            payload["extrinsics"] = {
                "R_robot_camera": self.R_robot_camera.flatten().tolist(),
                "t_robot_camera_mm": self.t_robot_camera.flatten().tolist(),
                "captured_at": _now_iso(),
            }
        with open(target, "w") as f:
            json5.dump(payload, f, indent=2)
        return target


class UvcCamera(Camera):
    commands = DriverCommands(parents=[Camera.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        device: str,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fourcc: str = DEFAULT_FOURCC,
        focus: int | None = None,
        autofocus: bool = False,
        settings: dict[str, int] | None = None,
        marker_size_mm: float = 32.0,
        dictionary: str = DEFAULT_ARUCO_DICTIONARY,
        calibration_path: str | None = None,
        charuco_squares_x: int = DEFAULT_CHARUCO_SQUARES_X,
        charuco_squares_y: int = DEFAULT_CHARUCO_SQUARES_Y,
        charuco_square_mm: float = DEFAULT_CHARUCO_SQUARE_MM,
        charuco_marker_mm: float = DEFAULT_CHARUCO_MARKER_MM,
    ):
        super().__init__(name)
        self._log = logger
        self._device = device
        self._width = width
        self._height = height
        self._fourcc = fourcc
        self._focus = focus
        self._autofocus = autofocus
        self._settings = dict(settings) if settings else {}
        self._cap = None
        self._lock = threading.Lock()
        # Background reader: see frame_capture.md. Grab+retrieve in a loop
        # (= cv2.VideoCapture.read), keep only the latest frame for callers.
        self._read_thread: threading.Thread | None = None
        self._read_stop = threading.Event()
        self._latest_frame: "np.ndarray | None" = None
        self._latest_frame_lock = threading.Lock()
        self._aruco = _ArucoState(
            marker_size_mm=marker_size_mm,
            dictionary=dictionary,
            charuco_squares_x=charuco_squares_x,
            charuco_squares_y=charuco_squares_y,
            charuco_square_mm=charuco_square_mm,
            charuco_marker_mm=charuco_marker_mm,
            calibration_path=calibration_path,
        )

    def init(self) -> Task[()]:
        import cv2

        # AF must be locked before VideoCapture grabs its first buffer,
        # otherwise focal length floats and any K calibrated downstream is invalid.
        # Fixed-focus lenses don't expose this control at all (e.g. U20CAM-1080p).
        if _v4l2_has_ctrl(self._device, "focus_automatic_continuous"):
            af_value = 1 if self._autofocus else 0
            ok, err = _v4l2_set_ctrl(self._device, "focus_automatic_continuous", af_value)
            if not ok:
                self._log.warning(
                    f"UvcCamera '{self.name}': could not set focus_automatic_continuous "
                    f"on {self._device}: {err}"
                )
        elif self._autofocus:
            self._log.warning(
                f"UvcCamera '{self.name}': autofocus requested but {self._device} "
                f"has no focus_automatic_continuous control (fixed-focus lens)"
            )
        if self._focus is not None and not self._autofocus:
            _v4l2_set_ctrl(self._device, "focus_absolute", self._focus)

        for ctrl, value in self._settings.items():
            ok, err = _v4l2_set_ctrl(self._device, ctrl, value)
            if not ok:
                self._log.warning(
                    f"UvcCamera '{self.name}': v4l2 ctrl {ctrl}={value} ignored ({err})"
                )

        self._cap = cv2.VideoCapture(self._device, cv2.CAP_V4L2)
        if not self._cap.isOpened():
            raise RuntimeError(f"UvcCamera '{self.name}': failed to open {self._device}")

        # FOURCC must be set before the size: UVC's resolution table is
        # format-dependent, MJPG and YUYV expose different size lists.
        self._cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*self._fourcc))
        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self._width)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self._height)
        self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        self._width = int(self._cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self._height = int(self._cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        loaded = self._aruco.load()
        self._log.info(
            f"UvcCamera '{self.name}' opened on {self._device} "
            f"@ {self._width}x{self._height} {self._fourcc} "
            f"(focus={'AUTO' if self._autofocus else self._focus}, "
            f"calibration={'loaded' if loaded else 'absent'})"
        )
        self._read_stop.clear()
        self._read_thread = threading.Thread(
            target=self._read_loop,
            name=f"uvc-read-{self.name}",
            daemon=True,
        )
        self._read_thread.start()
        return ImmediateResultTask()

    def _read_loop(self) -> None:
        """Read frames continuously and keep only the latest. See frame_capture.md."""
        while not self._read_stop.is_set():
            with self._lock:
                cap = self._cap
            if cap is None:
                break
            try:
                ok, frame = cap.read()
            except Exception:
                break
            if ok and frame is not None:
                with self._latest_frame_lock:
                    self._latest_frame = frame
            else:
                time.sleep(0.005)

    def close(self) -> None:
        self._read_stop.set()
        if self._read_thread is not None:
            self._read_thread.join(timeout=1.0)
            self._read_thread = None
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
        with self._latest_frame_lock:
            self._latest_frame = None
        self._log.info(f"UvcCamera '{self.name}' closed")

    def capture(self) -> "np.ndarray":
        if self._cap is None:
            raise RuntimeError(f"UvcCamera '{self.name}' not opened")
        # Wait briefly for the background thread to publish its first frame.
        deadline = time.monotonic() + 1.0
        while True:
            with self._latest_frame_lock:
                frame = self._latest_frame
            if frame is not None:
                return frame
            if time.monotonic() > deadline:
                raise RuntimeError(f"UvcCamera '{self.name}': no frame available")
            time.sleep(0.005)

    def detect(self) -> list[ArucoMarker]:
        return self._aruco.detect_in_frame(self.capture())

    def set_focus(self, value: int) -> Task[()]:
        ok, err = _v4l2_set_ctrl(self._device, "focus_absolute", value)
        if not ok:
            self._log.warning(f"UvcCamera '{self.name}': set_focus({value}) failed: {err}")
        else:
            self._focus = value
        return ImmediateResultTask()

    def set_setting(self, name: str, value: int) -> Task[()]:
        ok, err = _v4l2_set_ctrl(self._device, name, value)
        if not ok:
            self._log.warning(f"UvcCamera '{self.name}': set_setting({name}) failed: {err}")
        else:
            self._settings[name] = value
        return ImmediateResultTask()

    def calibration_session(self) -> CharucoCalibrationSession:
        return self._aruco.calibration_session()

    def apply_intrinsics(self, intrinsics: dict[str, Any]) -> None:
        self._aruco.apply_intrinsics(intrinsics)

    def calibrate_extrinsics(
        self,
        reference_marker_id: int,
        R_robot_marker: "np.ndarray",
        t_robot_marker_mm: "np.ndarray",
    ) -> dict[str, Any]:
        return self._aruco.calibrate_extrinsics(
            self.detect(), reference_marker_id, R_robot_marker, t_robot_marker_mm
        )

    def calibrate_extrinsics_from_pose(
        self,
        reference_marker_id: int,
        rvec_camera_marker: "np.ndarray",
        tvec_camera_marker: "np.ndarray",
        R_robot_marker: "np.ndarray",
        t_robot_marker_mm: "np.ndarray",
    ) -> dict[str, Any]:
        # Apply extrinsics from a pre-computed marker pose (e.g. averaged
        # across N frames via bundle PnP) instead of running detect() again.
        import numpy as np

        marker = ArucoMarker(
            id=reference_marker_id,
            corners=np.zeros((4, 2), dtype=np.float32),
        )
        marker.rvec_camera = np.asarray(rvec_camera_marker).reshape(3)
        marker.tvec_camera = np.asarray(tvec_camera_marker).reshape(3)
        return self._aruco.calibrate_extrinsics(
            [marker], reference_marker_id, R_robot_marker, t_robot_marker_mm
        )

    @property
    def K(self) -> "np.ndarray | None":
        return self._aruco.K

    @property
    def dist(self) -> "np.ndarray | None":
        return self._aruco.dist

    def detect_from_frame(self, frame: "np.ndarray") -> list[ArucoMarker]:
        return self._aruco.detect_in_frame(frame)

    def is_intrinsics_loaded(self) -> bool:
        return self._aruco.is_intrinsics_loaded()

    def is_extrinsics_loaded(self) -> bool:
        return self._aruco.is_extrinsics_loaded()

    def load_calibration(self, path: str | None = None) -> bool:
        return self._aruco.load(path)

    def save_calibration(self, path: str | None = None) -> None:
        target = self._aruco.save(path)
        self._log.info(f"UvcCamera '{self.name}' saved calibration -> {target}")

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height


class UvcCameraDefinition(DriverDefinition):
    def __init__(self, logger: Logger):
        super().__init__(UvcCamera.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("device", ArgTypes.String())
        defn.add_optional("width", ArgTypes.U32(), DEFAULT_WIDTH)
        defn.add_optional("height", ArgTypes.U32(), DEFAULT_HEIGHT)
        defn.add_optional("fourcc", ArgTypes.String(), DEFAULT_FOURCC)
        defn.add_optional("focus", ArgTypes.I32(), -1)  # -1 = no override
        defn.add_optional("autofocus", ArgTypes.Bool(), False)
        defn.add_optional("marker_size_mm", ArgTypes.F32(), 32.0)
        defn.add_optional("dictionary", ArgTypes.String(), DEFAULT_ARUCO_DICTIONARY)
        defn.add_optional("calibration_path", ArgTypes.String(), "")
        defn.add_optional("charuco_squares_x", ArgTypes.U32(), DEFAULT_CHARUCO_SQUARES_X)
        defn.add_optional("charuco_squares_y", ArgTypes.U32(), DEFAULT_CHARUCO_SQUARES_Y)
        defn.add_optional("charuco_square_mm", ArgTypes.F32(), DEFAULT_CHARUCO_SQUARE_MM)
        defn.add_optional("charuco_marker_mm", ArgTypes.F32(), DEFAULT_CHARUCO_MARKER_MM)
        return defn

    def create(self, args: DriverInitArgs) -> UvcCamera:
        focus_arg = args.get("focus")
        focus = None if focus_arg == -1 else int(focus_arg)
        cal_path = args.get("calibration_path") or None
        return UvcCamera(
            name=args.get_name(),
            logger=self._logger,
            device=args.get("device"),
            width=args.get("width"),
            height=args.get("height"),
            fourcc=args.get("fourcc"),
            focus=focus,
            autofocus=args.get("autofocus"),
            settings=None,
            marker_size_mm=args.get("marker_size_mm"),
            dictionary=args.get("dictionary"),
            calibration_path=cal_path,
            charuco_squares_x=args.get("charuco_squares_x"),
            charuco_squares_y=args.get("charuco_squares_y"),
            charuco_square_mm=args.get("charuco_square_mm"),
            charuco_marker_mm=args.get("charuco_marker_mm"),
        )


class UvcCameraVirtual(Camera):
    """Drop-in replacement for UvcCamera. ``device`` read as a folder of
    JPEG/PNG to replay, or ignored to yield blank frames. Same ArUco surface."""

    commands = DriverCommands(parents=[Camera.commands])

    def __init__(
        self,
        name: str,
        logger: Logger,
        device: str,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fourcc: str = DEFAULT_FOURCC,
        focus: int | None = None,
        autofocus: bool = False,
        settings: dict[str, int] | None = None,
        marker_size_mm: float = 32.0,
        dictionary: str = DEFAULT_ARUCO_DICTIONARY,
        calibration_path: str | None = None,
        charuco_squares_x: int = DEFAULT_CHARUCO_SQUARES_X,
        charuco_squares_y: int = DEFAULT_CHARUCO_SQUARES_Y,
        charuco_square_mm: float = DEFAULT_CHARUCO_SQUARE_MM,
        charuco_marker_mm: float = DEFAULT_CHARUCO_MARKER_MM,
    ):
        super().__init__(name)
        self._log = logger
        self._device = device
        self._width = width
        self._height = height
        # fourcc / focus / autofocus kept for signature parity with UvcCamera
        self._fourcc = fourcc
        self._focus = focus
        self._autofocus = autofocus
        self._settings = dict(settings) if settings else {}
        self._frames: list[str] = []
        self._injected_frames: list["np.ndarray"] | None = None
        self._injected_markers: list[ArucoMarker] | None = None
        self._cursor = 0
        self._lock = threading.Lock()
        self._opened = False
        self._aruco = _ArucoState(
            marker_size_mm=marker_size_mm,
            dictionary=dictionary,
            charuco_squares_x=charuco_squares_x,
            charuco_squares_y=charuco_squares_y,
            charuco_square_mm=charuco_square_mm,
            charuco_marker_mm=charuco_marker_mm,
            calibration_path=calibration_path,
        )

    def init(self) -> Task[()]:
        if os.path.isdir(self._device):
            entries = sorted(os.listdir(self._device))
            self._frames = [
                os.path.join(self._device, f)
                for f in entries
                if f.lower().endswith((".jpg", ".jpeg", ".png", ".bmp"))
            ]
            self._log.info(
                f"UvcCameraVirtual '{self.name}' replaying {len(self._frames)} frames "
                f"from {self._device}"
            )
        else:
            self._log.info(
                f"UvcCameraVirtual '{self.name}' synthetic mode ({self._width}x{self._height})"
            )
        self._aruco.load()
        self._opened = True
        return ImmediateResultTask()

    def close(self) -> None:
        self._opened = False
        self._log.info(f"UvcCameraVirtual '{self.name}' closed")

    def capture(self) -> "np.ndarray":
        if not self._opened:
            raise RuntimeError(f"UvcCameraVirtual '{self.name}' not opened")
        import numpy as np

        with self._lock:
            if self._injected_frames:
                frame = self._injected_frames[self._cursor % len(self._injected_frames)]
                self._cursor += 1
                return frame
            if self._frames:
                import cv2

                path = self._frames[self._cursor % len(self._frames)]
                self._cursor += 1
                frame = cv2.imread(path, cv2.IMREAD_COLOR)
                if frame is None:
                    raise RuntimeError(f"UvcCameraVirtual '{self.name}': failed to read {path}")
                return frame
            return np.zeros((self._height, self._width, 3), dtype=np.uint8)

    def detect(self) -> list[ArucoMarker]:
        if self._injected_markers is not None:
            return list(self._injected_markers)
        return self._aruco.detect_in_frame(self.capture())

    def set_focus(self, value: int) -> Task[()]:
        self._focus = value
        return ImmediateResultTask()

    def set_setting(self, name: str, value: int) -> Task[()]:
        self._settings[name] = value
        return ImmediateResultTask()

    def calibration_session(self) -> CharucoCalibrationSession:
        return self._aruco.calibration_session()

    def apply_intrinsics(self, intrinsics: dict[str, Any]) -> None:
        self._aruco.apply_intrinsics(intrinsics)

    def calibrate_extrinsics(
        self,
        reference_marker_id: int,
        R_robot_marker: "np.ndarray",
        t_robot_marker_mm: "np.ndarray",
    ) -> dict[str, Any]:
        return self._aruco.calibrate_extrinsics(
            self.detect(), reference_marker_id, R_robot_marker, t_robot_marker_mm
        )

    def calibrate_extrinsics_from_pose(
        self,
        reference_marker_id: int,
        rvec_camera_marker: "np.ndarray",
        tvec_camera_marker: "np.ndarray",
        R_robot_marker: "np.ndarray",
        t_robot_marker_mm: "np.ndarray",
    ) -> dict[str, Any]:
        # Apply extrinsics from a pre-computed marker pose (e.g. averaged
        # across N frames via bundle PnP) instead of running detect() again.
        import numpy as np

        marker = ArucoMarker(
            id=reference_marker_id,
            corners=np.zeros((4, 2), dtype=np.float32),
        )
        marker.rvec_camera = np.asarray(rvec_camera_marker).reshape(3)
        marker.tvec_camera = np.asarray(tvec_camera_marker).reshape(3)
        return self._aruco.calibrate_extrinsics(
            [marker], reference_marker_id, R_robot_marker, t_robot_marker_mm
        )

    @property
    def K(self) -> "np.ndarray | None":
        return self._aruco.K

    @property
    def dist(self) -> "np.ndarray | None":
        return self._aruco.dist

    def detect_from_frame(self, frame: "np.ndarray") -> list[ArucoMarker]:
        return self._aruco.detect_in_frame(frame)

    def is_intrinsics_loaded(self) -> bool:
        return self._aruco.is_intrinsics_loaded()

    def is_extrinsics_loaded(self) -> bool:
        return self._aruco.is_extrinsics_loaded()

    def load_calibration(self, path: str | None = None) -> bool:
        return self._aruco.load(path)

    def save_calibration(self, path: str | None = None) -> None:
        self._aruco.save(path)

    @property
    def width(self) -> int:
        return self._width

    @property
    def height(self) -> int:
        return self._height

    # Simulation helpers

    def inject_frames(self, frames: list["np.ndarray"]) -> None:
        self._injected_frames = list(frames)
        self._frames = []
        self._cursor = 0

    def inject_markers(self, markers: list[ArucoMarker]) -> None:
        self._injected_markers = list(markers)

    def clear_inject(self) -> None:
        self._injected_frames = None
        self._injected_markers = None
        self._cursor = 0

    @property
    def settings(self) -> dict[str, int]:
        return dict(self._settings)


class UvcCameraVirtualDefinition(DriverDefinition):
    def __init__(self, logger: Logger):
        super().__init__(UvcCameraVirtual.commands)
        self._logger = logger

    def get_init_args_definition(self) -> DriverInitArgsDefinition:
        defn = DriverInitArgsDefinition()
        defn.add_required("device", ArgTypes.String())
        defn.add_optional("width", ArgTypes.U32(), DEFAULT_WIDTH)
        defn.add_optional("height", ArgTypes.U32(), DEFAULT_HEIGHT)
        defn.add_optional("fourcc", ArgTypes.String(), DEFAULT_FOURCC)
        defn.add_optional("focus", ArgTypes.I32(), -1)
        defn.add_optional("autofocus", ArgTypes.Bool(), False)
        defn.add_optional("marker_size_mm", ArgTypes.F32(), 32.0)
        defn.add_optional("dictionary", ArgTypes.String(), DEFAULT_ARUCO_DICTIONARY)
        defn.add_optional("calibration_path", ArgTypes.String(), "")
        defn.add_optional("charuco_squares_x", ArgTypes.U32(), DEFAULT_CHARUCO_SQUARES_X)
        defn.add_optional("charuco_squares_y", ArgTypes.U32(), DEFAULT_CHARUCO_SQUARES_Y)
        defn.add_optional("charuco_square_mm", ArgTypes.F32(), DEFAULT_CHARUCO_SQUARE_MM)
        defn.add_optional("charuco_marker_mm", ArgTypes.F32(), DEFAULT_CHARUCO_MARKER_MM)
        return defn

    def create(self, args: DriverInitArgs) -> UvcCameraVirtual:
        focus_arg = args.get("focus")
        focus = None if focus_arg == -1 else int(focus_arg)
        cal_path = args.get("calibration_path") or None
        return UvcCameraVirtual(
            name=args.get_name(),
            logger=self._logger,
            device=args.get("device"),
            width=args.get("width"),
            height=args.get("height"),
            fourcc=args.get("fourcc"),
            focus=focus,
            autofocus=args.get("autofocus"),
            settings=None,
            marker_size_mm=args.get("marker_size_mm"),
            dictionary=args.get("dictionary"),
            calibration_path=cal_path,
            charuco_squares_x=args.get("charuco_squares_x"),
            charuco_squares_y=args.get("charuco_squares_y"),
            charuco_square_mm=args.get("charuco_square_mm"),
            charuco_marker_mm=args.get("charuco_marker_mm"),
        )
