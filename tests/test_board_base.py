"""Lifecycle tests for the BoardDriver base class.

Uses trivial fake children to verify init/close ordering without tying the
test to any concrete chip driver.
"""

from evo_lib.drivers.board.base import BoardDriver
from evo_lib.logger import Logger
from evo_lib.peripheral import Peripheral
from evo_lib.task import ImmediateResultTask, Task


class _FakeChild(Peripheral):
    def __init__(self, name: str, events: list[tuple[str, str]]):
        super().__init__(name)
        self._events = events

    def init(self) -> Task[()]:
        self._events.append(("init", self.name))
        return ImmediateResultTask()

    def close(self) -> None:
        self._events.append(("close", self.name))


def test_board_driver_chains_lifecycle_in_order():
    events: list[tuple[str, str]] = []
    children = [_FakeChild(n, events) for n in ("a", "b", "c")]
    board = BoardDriver(name="test_board", logger=Logger("test"), children=children)

    board.init().wait()
    board.close()

    assert events == [
        ("init", "a"),
        ("init", "b"),
        ("init", "c"),
        ("close", "c"),
        ("close", "b"),
        ("close", "a"),
    ]
    assert board.get_subcomponents() == children


def test_board_driver_close_continues_after_child_failure():
    events: list[tuple[str, str]] = []

    class _RaisingChild(_FakeChild):
        def close(self) -> None:
            self._events.append(("close", self.name))
            raise RuntimeError("boom")

    children = [_FakeChild("a", events), _RaisingChild("b", events), _FakeChild("c", events)]
    board = BoardDriver(name="test_board", logger=Logger("test"), children=children)

    board.init().wait()
    board.close()

    assert [e for e in events if e[0] == "close"] == [
        ("close", "c"),
        ("close", "b"),
        ("close", "a"),
    ]
