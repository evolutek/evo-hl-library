"""Tests for AX12 driver using fake implementation."""

import pytest

from evo_lib.drivers.ax12.config import AX12BusConfig
from evo_lib.drivers.ax12.factory import create_ax12_bus
from evo_lib.drivers.ax12.fake import AX12BusFake, AX12ServoFake


@pytest.fixture
def bus():
    b = AX12BusFake(name="ax12_bus", device="/dev/ttyACM0")
    b.init()
    yield b
    b.close()


@pytest.fixture
def servo(bus):
    return bus.add_servo(servo_id=2, name="finger_2")


class TestAX12BusFake:
    def test_init_empty(self, bus):
        assert len(bus.get_subcomponents()) == 0

    def test_add_servo(self, bus):
        s = bus.add_servo(2, "servo_2")
        assert isinstance(s, AX12ServoFake)
        assert s.servo_id == 2
        assert len(bus.get_subcomponents()) == 1

    def test_add_servo_idempotent(self, bus):
        s1 = bus.add_servo(2, "servo_2")
        s2 = bus.add_servo(2, "servo_2")
        assert s1 is s2
        assert len(bus.get_subcomponents()) == 1

    def test_add_multiple_servos(self, bus):
        bus.add_servo(2, "servo_2")
        bus.add_servo(3, "servo_3")
        assert len(bus.get_subcomponents()) == 2


class TestAX12ServoFake:
    def test_default_position(self, servo):
        assert servo.get_position().wait() == 512

    def test_move_to_position(self, servo):
        servo.move_to_position(200).wait()
        assert servo.get_position().wait() == 200

    def test_move_to_position_out_of_range_raises(self, servo):
        with pytest.raises(ValueError, match="out of range"):
            servo.move_to_position(1024)

    def test_move_to_position_negative_raises(self, servo):
        with pytest.raises(ValueError, match="out of range"):
            servo.move_to_position(-1)

    def test_move_to_position_boundaries(self, servo):
        servo.move_to_position(0).wait()
        assert servo.get_position().wait() == 0
        servo.move_to_position(1023).wait()
        assert servo.get_position().wait() == 1023

    def test_get_angle(self, servo):
        servo.move_to_position(512).wait()
        angle = servo.get_angle().wait()
        assert abs(angle - 150.15) < 0.2  # roughly center

    def test_get_fraction(self, servo):
        servo.move_to_position(512).wait()
        fraction = servo.get_fraction().wait()
        assert abs(fraction - 0.5) < 0.01

    def test_move_to_angle(self, servo):
        servo.move_to_angle(150.0).wait()
        pos = servo.get_position().wait()
        assert abs(pos - 511) <= 1  # 150/300 * 1023 ~ 511

    def test_move_to_angle_out_of_range_raises(self, servo):
        with pytest.raises(ValueError, match="out of range"):
            servo.move_to_angle(301.0)

    def test_move_to_fraction(self, servo):
        servo.move_to_fraction(0.5).wait()
        pos = servo.get_position().wait()
        assert abs(pos - 511) <= 1

    def test_move_to_fraction_out_of_range_raises(self, servo):
        with pytest.raises(ValueError, match="out of range"):
            servo.move_to_fraction(1.1)

    def test_set_speed(self, servo):
        servo.set_speed(0.5).wait()
        assert servo._state["speed"] == 511

    def test_free(self, servo):
        servo.free().wait()
        assert not servo._state["torque"]

    def test_multiple_servos_independent(self, bus):
        s2 = bus.add_servo(2, "servo_2")
        s3 = bus.add_servo(3, "servo_3")
        s2.move_to_position(100).wait()
        s3.move_to_position(500).wait()
        assert s2.get_position().wait() == 100
        assert s3.get_position().wait() == 500

    def test_name(self, servo):
        assert servo.name == "finger_2"


class TestAX12BusConfig:
    def test_defaults(self):
        cfg = AX12BusConfig(name="ax12")
        assert cfg.device == "/dev/ttyACM0"
        assert cfg.baudrate == 1_000_000
        assert cfg.servo_ids == []

    def test_custom(self):
        cfg = AX12BusConfig(
            name="ax12_bus",
            device="/dev/ttyUSB0",
            baudrate=500_000,
            servo_ids=[2, 3, 5],
        )
        assert cfg.device == "/dev/ttyUSB0"
        assert cfg.servo_ids == [2, 3, 5]


class TestAX12Factory:
    def test_create_fake(self):
        cfg = AX12BusConfig(
            name="ax12_test",
            servo_ids=[2, 3],
        )
        bus, servos = create_ax12_bus(cfg, fake=True)
        assert isinstance(bus, AX12BusFake)
        assert len(servos) == 2
        assert servos[2].servo_id == 2
        assert servos[3].servo_id == 3
        bus.close()

    def test_create_fake_empty(self):
        cfg = AX12BusConfig(name="ax12_empty")
        bus, servos = create_ax12_bus(cfg, fake=True)
        assert len(servos) == 0
        bus.close()
