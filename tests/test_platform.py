from evo_lib.platform import PlatformHardware, PlatformOS


def test_enum_values_are_strings():
    assert PlatformOS.LINUX.value == "linux"
    assert PlatformHardware.RASPBERRY_PI.value == "rpi"
