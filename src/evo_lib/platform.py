import platform
from enum import Enum


class PlatformOS(Enum):
    UNKNOWN = "unknown"
    LINUX = "linux"
    WINDOWS = "windows"


class PlatformHardware(Enum):
    UNKNOWN = "unknown"
    RASPBERRY_PI = "rpi"
    COMPUTER = "computer"


class Platform:
    def __init__(self):
        self.os: PlatformOS = PlatformOS.UNKNOWN
        self.hardware: PlatformHardware = PlatformHardware.RASPBERRY_PI

    def get_hardware(self) -> PlatformHardware:
        return self.hardware

    def get_os(self) -> PlatformOS:
        return self.os

    def detect(self) -> None:
        system = platform.system()
        if system == "Linux":
            self.os = PlatformOS.LINUX
        elif system == "Windows":
            self.os = PlatformOS.WINDOWS
        else:
            self.os = PlatformOS.UNKNOWN

        release = platform.release()
        if release.count("Raspbian") > 0: # TODO: Check if correct
            self.hardware = PlatformHardware.RASPBERRY_PI
        else:
            self.hardware = PlatformHardware.COMPUTER


_platform: Platform | None = None

def get_platform() -> Platform:
    global _platform
    if _platform is None:
      _platform = Platform()
      _platform.detect()
    return _platform
