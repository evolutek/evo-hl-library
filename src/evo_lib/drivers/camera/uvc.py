"""UVC (V4L2) camera driver with built-in ArUco detection and ChArUco calibration."""

from __future__ import annotations

import os
import subprocess
import threading
from typing import TYPE_CHECKING, Any

from evo_lib.argtypes import ArgTypes
from evo_lib.driver_definition import (
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
        self.R_world_camera = None
        self.t_world_camera = None
        self.marker_obj_pts = _marker_object_points(marker_size_mm)
        self._detector_handle = None

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
            marker = ArucoMarker(id=int(marker_id), corners=corners_ij)
            if self.K is not None and self.dist is not None:
                ok, rvec, tvec = cv2.solvePnP(
                    self.marker_obj_pts,
                    corners_ij,
                    self.K,
                    self.dist,
                    flags=cv2.SOLVEPNP_IPPE_SQUARE,
                )
                if ok:
                    marker.rvec_camera = rvec.reshape(3)
                    marker.tvec_camera = tvec.reshape(3)
                    if self.R_world_camera is not None and self.t_world_camera is not None:
                        pos_world = self.R_world_camera @ marker.tvec_camera.reshape(
                            3, 1
                        ) + self.t_world_camera.reshape(3, 1)
                        marker.position_world_mm = pos_world.reshape(3)
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
        return self.R_world_camera is not None and self.t_world_camera is not None

    def calibrate_extrinsics(
        self,
        markers: list[ArucoMarker],
        reference_marker_id: int,
        R_world_marker: "np.ndarray",
        t_world_marker_mm: "np.ndarray",
    ) -> dict[str, Any]:
        # T_world_camera = T_world_marker @ inv(T_camera_marker).
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

        R_world_camera = np.asarray(R_world_marker) @ R_marker_camera
        t_world_camera = np.asarray(R_world_marker) @ t_marker_camera + np.asarray(
            t_world_marker_mm
        ).reshape(3, 1)

        self.R_world_camera = R_world_camera
        self.t_world_camera = t_world_camera

        return {
            "R_world_camera": R_world_camera.flatten().tolist(),
            "t_world_camera_mm": t_world_camera.flatten().tolist(),
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
            self.R_world_camera = np.asarray(extr["R_world_camera"], dtype=np.float64).reshape(3, 3)
            self.t_world_camera = np.asarray(extr["t_world_camera_mm"], dtype=np.float64).reshape(3)
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
        if self.R_world_camera is not None and self.t_world_camera is not None:
            payload["extrinsics"] = {
                "R_world_camera": self.R_world_camera.flatten().tolist(),
                "t_world_camera_mm": self.t_world_camera.flatten().tolist(),
                "captured_at": _now_iso(),
            }
        with open(target, "w") as f:
            json5.dump(payload, f, indent=2)
        return target


class UvcCamera(Camera):
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
        return ImmediateResultTask()

    def close(self) -> None:
        with self._lock:
            if self._cap is not None:
                self._cap.release()
                self._cap = None
        self._log.info(f"UvcCamera '{self.name}' closed")

    def capture(self) -> "np.ndarray":
        if self._cap is None:
            raise RuntimeError(f"UvcCamera '{self.name}' not opened")
        with self._lock:
            ok, frame = self._cap.read()
        if not ok:
            raise RuntimeError(f"UvcCamera '{self.name}': frame grab failed")
        return frame

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
        R_world_marker: "np.ndarray",
        t_world_marker_mm: "np.ndarray",
    ) -> dict[str, Any]:
        return self._aruco.calibrate_extrinsics(
            self.detect(), reference_marker_id, R_world_marker, t_world_marker_mm
        )

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
        super().__init__()
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
        R_world_marker: "np.ndarray",
        t_world_marker_mm: "np.ndarray",
    ) -> dict[str, Any]:
        return self._aruco.calibrate_extrinsics(
            self.detect(), reference_marker_id, R_world_marker, t_world_marker_mm
        )

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
        super().__init__()
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
