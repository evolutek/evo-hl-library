"""ChArUco calibration helpers — used by UvcCamera and the calibration CLI."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import numpy as np


DEFAULT_RMS_THRESHOLD_PX = 0.5
DEFAULT_PER_VIEW_REJECT_PX = 1.5


def _aruco_dict_from_name(name: str) -> Any:
    import cv2

    full_name = name if name.startswith("DICT_") else f"DICT_{name}"
    if not hasattr(cv2.aruco, full_name):
        raise ValueError(f"Unknown ArUco dictionary: {name}")
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, full_name))


def _build_charuco_board(
    squares_x: int,
    squares_y: int,
    square_mm: float,
    marker_mm: float,
    dictionary_name: str,
) -> Any:
    import cv2

    dictionary = _aruco_dict_from_name(dictionary_name)
    return cv2.aruco.CharucoBoard((squares_x, squares_y), square_mm, marker_mm, dictionary)


def _marker_object_points(marker_mm: float) -> "np.ndarray":
    # Pre-computed once, reused inside the detect() hot path to avoid
    # per-frame allocation.
    import numpy as np

    half = marker_mm * 0.5
    return np.array(
        [
            [-half, half, 0.0],
            [half, half, 0.0],
            [half, -half, 0.0],
            [-half, -half, 0.0],
        ],
        dtype=np.float32,
    )


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds")


class CharucoCalibrationSession:
    """Stateful collector for ChArUco views, decoupled from any Peripheral."""

    def __init__(
        self,
        board: Any,
        dictionary: Any,
        rms_threshold_px: float = DEFAULT_RMS_THRESHOLD_PX,
        per_view_reject_px: float = DEFAULT_PER_VIEW_REJECT_PX,
    ):
        self._board = board
        self._dictionary = dictionary
        self._rms_threshold = rms_threshold_px
        self._per_view_reject = per_view_reject_px
        self._all_corners: list[Any] = []
        self._all_ids: list[Any] = []
        self._image_size: tuple[int, int] | None = None

    @property
    def view_count(self) -> int:
        return len(self._all_corners)

    def capture_view(self, gray_frame: "np.ndarray") -> int:
        import cv2

        if self._image_size is None:
            h, w = gray_frame.shape[:2]
            self._image_size = (w, h)

        detector = cv2.aruco.ArucoDetector(self._dictionary, cv2.aruco.DetectorParameters())
        marker_corners, marker_ids, _ = detector.detectMarkers(gray_frame)
        if marker_ids is None or len(marker_ids) == 0:
            return 0

        ret, charuco_corners, charuco_ids = cv2.aruco.interpolateCornersCharuco(
            marker_corners, marker_ids, gray_frame, self._board
        )
        if ret <= 0 or charuco_corners is None or charuco_ids is None:
            return 0

        self._all_corners.append(charuco_corners)
        self._all_ids.append(charuco_ids)
        return int(ret)

    def compute(self) -> dict[str, Any]:
        import cv2
        import numpy as np

        if self._image_size is None:
            raise RuntimeError("No views captured; nothing to calibrate.")
        if len(self._all_corners) < 4:
            raise RuntimeError(f"Only {len(self._all_corners)} views captured; need at least 4.")

        rms, K, dist, rvecs, tvecs, std_intr, std_extr, per_view = (
            cv2.aruco.calibrateCameraCharucoExtended(
                charucoCorners=self._all_corners,
                charucoIds=self._all_ids,
                board=self._board,
                imageSize=self._image_size,
                cameraMatrix=None,
                distCoeffs=None,
            )
        )

        # Drop motion-blurred / partial views and re-run on survivors.
        per_view_arr = np.asarray(per_view).reshape(-1)
        keep_mask = per_view_arr <= self._per_view_reject
        n_drop = int(np.size(keep_mask) - np.sum(keep_mask))
        if n_drop > 0 and np.sum(keep_mask) >= 4:
            kept_corners = [c for c, k in zip(self._all_corners, keep_mask) if k]
            kept_ids = [i for i, k in zip(self._all_ids, keep_mask) if k]
            rms, K, dist, rvecs, tvecs, std_intr, std_extr, per_view = (
                cv2.aruco.calibrateCameraCharucoExtended(
                    charucoCorners=kept_corners,
                    charucoIds=kept_ids,
                    board=self._board,
                    imageSize=self._image_size,
                    cameraMatrix=None,
                    distCoeffs=None,
                )
            )

        if rms > self._rms_threshold:
            raise RuntimeError(
                f"Calibration RMS {rms:.3f}px exceeds threshold "
                f"{self._rms_threshold:.3f}px (kept {len(self._all_corners) - n_drop} views, "
                f"dropped {n_drop}); capture more or steadier views."
            )

        return {
            "K": K.flatten().tolist(),
            "dist": dist.flatten().tolist(),
            "image_size": list(self._image_size),
            "rms": float(rms),
            "n_views_used": int(len(self._all_corners) - n_drop),
            "n_views_dropped": int(n_drop),
            "captured_at": _now_iso(),
        }
