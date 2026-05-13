"""Camera abstract interface and ArUco data types."""

from abc import abstractmethod
from dataclasses import dataclass
from typing import TYPE_CHECKING

from evo_lib.peripheral import Placable

if TYPE_CHECKING:
    import numpy as np

    from evo_lib.task import Task


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
    position_world_mm: "np.ndarray | None" = None


class Camera(Placable):
    @abstractmethod
    def capture(self) -> "np.ndarray":
        """One frame, BGR uint8 (height, width, 3). Stale buffers must be dropped."""

    @abstractmethod
    def detect(self) -> list[ArucoMarker]:
        """Capture and return detected ArUco markers.

        Pose fields are populated only if intrinsics are loaded;
        position_world_mm only if extrinsics are also loaded.
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
    def load_calibration(self, path: str | None = None) -> bool: ...

    @abstractmethod
    def save_calibration(self, path: str | None = None) -> None: ...

    @property
    @abstractmethod
    def width(self) -> int: ...

    @property
    @abstractmethod
    def height(self) -> int: ...
