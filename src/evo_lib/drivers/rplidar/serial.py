"""RPLidar driver, real implementation via rplidar-roboticia."""

from __future__ import annotations

import logging
import time
from math import radians
from threading import Event as ThreadEvent, Lock, Thread
from typing import Generator

from evo_lib.interfaces.lidar import Lidar2D, Lidar2DMeasure
from evo_lib.task import DelayedTask, Task
from evo_lib.event import Event

log = logging.getLogger(__name__)


class RPLidarSerial(Lidar2D):
    """RPLidar A2 scanner via USB UART (rplidar-roboticia)."""

    def __init__(self, name: str, device: str, baudrate: int = 115200):
        super().__init__(name)
        self._device = device
        self._baudrate = baudrate
        self._lidar = None
        self._thread_lock = Lock()
        self._scan_thread: Thread | None = None
        self._stop_event = ThreadEvent()
        self._scan_event: Event[list[Lidar2DMeasure]] = Event()

    def init(self) -> None:
        from rplidar import RPLidar as _HwRPLidar

        self._lidar = _HwRPLidar(self._device, baudrate=self._baudrate)
        info = self._lidar.get_info()
        log.info("RPLidar '%s' initialized: %s", self.name, info)

    def close(self) -> None:
        self.stop().wait()
        if self._lidar is not None:
            self._lidar.disconnect()
            self._lidar = None
            log.info("RPLidar '%s' closed", self.name)

    def start(self) -> Task[None]:
        task: DelayedTask[None] = DelayedTask(on_cancel=self._request_stop)
        self._stop_event.clear()
        thread = Thread(
            target=self._scan_loop, args=(task,), daemon=True,
        )
        with self._thread_lock:
            self._scan_thread = thread
        thread.start()
        return task

    def stop(self) -> Task[None]:
        task: DelayedTask[None] = DelayedTask()
        with self._thread_lock:
            thread = self._scan_thread
        if thread is not None and thread.is_alive():
            self._stop_event.set()
            Thread(target=self._wait_stop, args=(task, thread), daemon=True).start()
        else:
            task.complete()
        return task

    def iter(self, duration: float | None = None) -> Generator[Lidar2DMeasure, None, None]:
        if self._lidar is None:
            return
        start_time = time.monotonic()
        for scan in self._lidar.iter_scans():
            if self._stop_event.is_set():
                break
            for quality, angle_deg, distance in scan:
                yield Lidar2DMeasure(
                    angle=radians(angle_deg),
                    distance=distance,
                    timestamp=time.monotonic(),
                    quality=quality,
                )
            if duration is not None and (time.monotonic() - start_time) >= duration:
                break

    def on_scan(self) -> Event[list[Lidar2DMeasure]]:
        return self._scan_event

    # -- Private helpers --

    def _request_stop(self) -> None:
        self._stop_event.set()

    def _wait_stop(self, task: DelayedTask[None], thread: Thread) -> None:
        """Wait for the scan thread to finish, then complete the task."""
        thread.join()
        with self._thread_lock:
            if self._scan_thread is thread:
                self._scan_thread = None
        try:
            self._lidar.stop()
            self._lidar.stop_motor()
        except Exception as exc:
            log.warning("RPLidar '%s' error during stop: %s", self.name, exc)
        task.complete()

    def _scan_loop(self, task: DelayedTask[None]) -> None:
        """Background loop: iterate scans and trigger event per revolution."""
        log.info("RPLidar '%s' scanning started", self.name)
        try:
            self._lidar.start_motor()
            started = False
            for scan in self._lidar.iter_scans():
                if not started:
                    task.complete()
                    started = True
                if self._stop_event.is_set():
                    break
                measures = [
                    Lidar2DMeasure(
                        angle=radians(angle_deg),
                        distance=distance,
                        timestamp=time.monotonic(),
                        quality=quality,
                    )
                    for quality, angle_deg, distance in scan
                ]
                self._scan_event.trigger(measures)
        except Exception as exc:
            log.error("RPLidar '%s' scan error: %s", self.name, exc)
            if not task.is_done():
                task.error(exc)
        finally:
            log.info("RPLidar '%s' scanning stopped", self.name)
