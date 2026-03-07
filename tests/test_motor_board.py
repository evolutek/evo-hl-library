"""Tests for motor board driver using fake implementation."""

import pytest

from evo_lib.drivers.motor_board.fake import MotorBoardFake


@pytest.fixture
def mdb():
    drv = MotorBoardFake(address=0x69)
    drv.init()
    yield drv
    drv.close()


class TestMotorBoardFake:
    def test_goto(self, mdb):
        assert mdb.goto(0, 1000, 500).wait() is True
        assert mdb.steppers[0]["position"] == 1000
        assert mdb.steppers[0]["speed"] == 500

    def test_move_relative(self, mdb):
        mdb.goto(0, 100, 300)
        mdb.move(0, 50, 200)
        assert mdb.steppers[0]["position"] == 150

    def test_home(self, mdb):
        mdb.goto(0, 500, 100)
        assert mdb.home(0, 200).wait() is True
        assert mdb.steppers[0]["position"] == 0

    def test_multiple_steppers(self, mdb):
        mdb.goto(0, 100, 100)
        mdb.goto(1, 200, 200)
        assert mdb.steppers[0]["position"] == 100
        assert mdb.steppers[1]["position"] == 200

    def test_init_clears(self, mdb):
        mdb.goto(0, 100, 100)
        mdb.init()
        assert len(mdb.steppers) == 0

    def test_close_clears(self, mdb):
        mdb.goto(0, 100, 100)
        mdb.close()
        assert len(mdb.steppers) == 0

    def test_name(self, mdb):
        assert mdb.name == "motor_board_fake"

    def test_task_is_done(self, mdb):
        task = mdb.goto(0, 100, 100)
        assert task.is_done() is True
