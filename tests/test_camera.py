"""Tests for the UvcCamera driver: signature parity, virtual capture, calibration round-trip."""

import inspect
import os

import numpy as np
import pytest

from evo_lib.drivers.camera import (
    UvcCamera,
    UvcCameraDefinition,
    UvcCameraVirtual,
    UvcCameraVirtualDefinition,
)
from evo_lib.interfaces.camera import ArucoMarker
from evo_lib.logger import Logger


@pytest.fixture
def logger():
    return Logger("test")


# Swap-real-virtual invariant: the virtual twin must accept exactly the
# same constructor arguments as the real driver.


class TestSignatureParity:
    def test_uvc_camera_constructor_parity(self):
        real = inspect.signature(UvcCamera.__init__)
        virt = inspect.signature(UvcCameraVirtual.__init__)
        assert list(real.parameters) == list(virt.parameters)
        for name in real.parameters:
            assert (
                real.parameters[name].default == virt.parameters[name].default
            ), f"default for {name} differs"

    def test_uvc_camera_definition_parity(self, logger):
        real = UvcCameraDefinition(logger).get_init_args_definition().get_args()
        virt = UvcCameraVirtualDefinition(logger).get_init_args_definition().get_args()
        assert real.keys() == virt.keys()
        for key in real:
            assert real[key].is_required() == virt[key].is_required()


class TestUvcCameraVirtual:
    def test_synthetic_mode_returns_blank_frames(self, logger):
        cam = UvcCameraVirtual(
            name="cam", logger=logger, device="/nonexistent", width=320, height=240
        )
        cam.init()
        frame = cam.capture()
        assert frame.shape == (240, 320, 3)
        assert frame.dtype == np.uint8
        assert np.all(frame == 0)
        cam.close()

    def test_replay_mode_loops_through_directory(self, logger, tmp_path):
        import cv2

        for i in range(3):
            img = np.full((80, 120, 3), i * 60, dtype=np.uint8)
            cv2.imwrite(str(tmp_path / f"f{i:03d}.png"), img)

        cam = UvcCameraVirtual(name="cam", logger=logger, device=str(tmp_path))
        cam.init()
        means = [cam.capture().mean() for _ in range(6)]
        assert means == [0.0, 60.0, 120.0, 0.0, 60.0, 120.0]
        cam.close()

    def test_inject_frames_overrides_disk(self, logger):
        cam = UvcCameraVirtual(name="cam", logger=logger, device="/nonexistent")
        cam.init()
        frames = [
            np.full((10, 10, 3), 5, dtype=np.uint8),
            np.full((10, 10, 3), 200, dtype=np.uint8),
        ]
        cam.inject_frames(frames)
        assert cam.capture().mean() == 5
        assert cam.capture().mean() == 200
        assert cam.capture().mean() == 5
        cam.close()

    def test_set_setting_records_value(self, logger):
        cam = UvcCameraVirtual(name="cam", logger=logger, device="/nonexistent")
        cam.init()
        cam.set_setting("exposure_time_absolute", 250)
        assert cam.settings["exposure_time_absolute"] == 250
        cam.close()


class TestArucoDetection:
    def test_inject_markers_bypasses_detection(self, logger):
        cam = UvcCameraVirtual(
            name="cam", logger=logger, device="/nope", width=64, height=64
        )
        cam.init()
        injected = [
            ArucoMarker(id=42, corners=np.zeros((4, 2), dtype=np.float32)),
            ArucoMarker(id=7, corners=np.zeros((4, 2), dtype=np.float32)),
        ]
        cam.inject_markers(injected)
        assert [m.id for m in cam.detect()] == [42, 7]

        cam.clear_inject()
        # No injection + blank frames -> empty detection
        assert cam.detect() == []
        cam.close()


class TestCalibrationRoundtrip:
    def test_save_then_load_preserves_values(self, logger, tmp_path):
        cal_path = str(tmp_path / "cal.json5")
        cam = UvcCameraVirtual(
            name="cam",
            logger=logger,
            device="/nope",
            width=64,
            height=64,
            calibration_path=cal_path,
        )
        cam.init()

        K = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float64)
        dist = np.array([0.1, -0.2, 0.001, 0.002, 0.05], dtype=np.float64)
        cam.apply_intrinsics(
            {"K": K.flatten().tolist(), "dist": dist.tolist(), "image_size": [640, 480]}
        )
        cam.save_calibration()
        assert os.path.exists(cal_path)

        cam2 = UvcCameraVirtual(
            name="cam2",
            logger=logger,
            device="/nope",
            calibration_path=cal_path,
        )
        cam2.init()
        assert cam2.is_intrinsics_loaded()
        assert np.allclose(cam2._aruco.K, K)
        assert np.allclose(cam2._aruco.dist, dist)
        cam.close()
        cam2.close()

    def test_save_without_calibration_writes_empty_payload(self, logger, tmp_path):
        cal_path = str(tmp_path / "cal.json5")
        cam = UvcCameraVirtual(
            name="cam", logger=logger, device="/nope", calibration_path=cal_path
        )
        cam.init()
        cam.save_calibration()

        import json5

        with open(cal_path) as f:
            data = json5.load(f)
        assert data == {}
        cam.close()
