"""Tests for Pilot drivers."""

import struct

from evo_lib.drivers.pilot.protocol import INIT_PACKET, Commands, build_packet
from evo_lib.drivers.pilot.virtual import HolonomicPilotVirtual, PilotVirtual
from evo_lib.interfaces.pilot import PilotMoveStatus


class TestProtocol:
    def test_build_empty_packet(self):
        packet = build_packet(Commands.FREE)
        assert packet == bytes([2, Commands.FREE])

    def test_build_goto_xy(self):
        packet = build_packet(Commands.GOTO_XY, 100.0, 200.0)
        assert packet[0] == 2 + 8  # length + cmd + 2 floats
        assert packet[1] == Commands.GOTO_XY
        x, y = struct.unpack("ff", packet[2:])
        assert abs(x - 100.0) < 0.01
        assert abs(y - 200.0) < 0.01

    def test_build_set_theta(self):
        packet = build_packet(Commands.SET_THETA, 1.57)
        assert packet[0] == 6  # 2 + 4 bytes float
        assert packet[1] == Commands.SET_THETA

    def test_build_global_goto(self):
        packet = build_packet(Commands.GLOBAL_GOTO, 100.0, 200.0, 1.57, 0.0, 1.0, 0.0, 1.0, 0, 0)
        assert packet[0] == 32  # 2 + 7*4 + 2
        assert packet[1] == Commands.GLOBAL_GOTO

    def test_init_packet(self):
        assert INIT_PACKET == bytes([5, 254, 0xAA, 0xAA, 0xAA])


class TestPilotVirtual:
    def test_go_to(self):
        pilot = PilotVirtual("pilot", speed_trsl=10000.0)
        pilot.init()
        status = pilot.go_to(100.0, 0.0).wait()
        assert status == PilotMoveStatus.REACHED
        x, y, _ = pilot.position
        assert abs(x - 100.0) < 0.1

    def test_rotate(self):
        pilot = PilotVirtual("pilot", speed_rot=100.0)
        pilot.init()
        status = pilot.rotate(1.57).wait()
        assert status == PilotMoveStatus.REACHED
        _, _, theta = pilot.position
        assert abs(theta - 1.57) < 0.01

    def test_free(self):
        pilot = PilotVirtual("pilot")
        pilot.init()
        pilot.free().wait()

    def test_stop(self):
        pilot = PilotVirtual("pilot")
        pilot.init()
        pilot.stop().wait()

    def test_initial_position(self):
        pilot = PilotVirtual("pilot")
        assert pilot.position == (0.0, 0.0, 0.0)


class TestHolonomicPilotVirtual:
    def test_go_to_while_head_to(self):
        pilot = HolonomicPilotVirtual("holo", speed_trsl=10000.0, speed_rot=100.0)
        pilot.init()
        status = pilot.go_to_while_head_to(100.0, 0.0, 1.57).wait()
        assert status == PilotMoveStatus.REACHED
        x, _, theta = pilot.position
        assert abs(x - 100.0) < 0.1
        assert abs(theta - 1.57) < 0.01

    def test_go_to_while_rotate(self):
        pilot = HolonomicPilotVirtual("holo", speed_trsl=10000.0, speed_rot=100.0)
        pilot.init()
        status = pilot.go_to_while_rotate(50.0, 0.0, 0.5).wait()
        assert status == PilotMoveStatus.REACHED
        x, _, theta = pilot.position
        assert abs(x - 50.0) < 0.1
        assert abs(theta - 0.5) < 0.01
