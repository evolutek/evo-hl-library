"""Tests for FSM."""

import threading
from enum import StrEnum

import pytest

from evo_lib.fsm import FSM, TransitionError
from evo_lib.task import DelayedTask, ImmediateResultTask, TaskCancelledError


class St(StrEnum):
    A = "a"
    B = "b"
    C = "c"
    ERR = "err"


class TestFSMTransitions:
    def test_valid_transition(self):
        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(St.B), prevs=[])
        fsm.register(St.B, lambda: ImmediateResultTask(None), prevs=[St.A])
        task = fsm.start(St.A)
        task.wait()
        assert fsm.state == St.B

    def test_invalid_transition_raises(self):
        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(St.C), prevs=[])
        fsm.register(St.B, lambda: ImmediateResultTask(None), prevs=[St.A])
        fsm.register(St.C, lambda: ImmediateResultTask(None), prevs=[St.B])
        task = fsm.start(St.A)
        with pytest.raises(TransitionError, match="not allowed"):
            task.wait()

    def test_chain_three_states(self):
        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(St.B), prevs=[])
        fsm.register(St.B, lambda: ImmediateResultTask(St.C), prevs=[St.A])
        fsm.register(St.C, lambda: ImmediateResultTask(None), prevs=[St.B])
        task = fsm.start(St.A)
        task.wait()
        assert fsm.state == St.C


class TestFSMStart:
    def test_unregistered_state_raises(self):
        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(None), prevs=[])
        with pytest.raises(TransitionError, match="not registered"):
            fsm.start(St.B)

    def test_non_start_state_raises(self):
        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(St.B), prevs=[])
        fsm.register(St.B, lambda: ImmediateResultTask(None), prevs=[St.A])
        with pytest.raises(TransitionError, match="not a valid start state"):
            fsm.start(St.B)

    def test_double_start_raises(self):
        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(None), prevs=[])
        fsm.start(St.A)
        with pytest.raises(RuntimeError, match="already started"):
            fsm.start(St.A)


class TestFSMTransitionToUnregistered:
    def test_transition_to_unregistered_state_raises(self):
        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(St.B), prevs=[])
        fsm.register(St.B, lambda: ImmediateResultTask(St.C), prevs=[St.A])
        # St.C never registered: prevs.get(C) returns [], so prevs check fails
        task = fsm.start(St.A)
        with pytest.raises(TransitionError, match="not allowed"):
            task.wait()


class TestFSMError:
    def test_state_error_propagates(self):
        def failing():
            t = DelayedTask()
            t.error(ValueError("hardware fault"))
            return t

        fsm = FSM(St)
        fsm.register(St.A, failing, prevs=[])
        task = fsm.start(St.A)
        with pytest.raises(ValueError, match="hardware fault"):
            task.wait()


class TestFSMErrorState:
    def test_error_transitions_to_error_state(self):
        entered_error = threading.Event()

        def error_callback():
            entered_error.set()
            return ImmediateResultTask(None)

        def failing():
            t = DelayedTask()
            t.error(ValueError("boom"))
            return t

        fsm = FSM(St)
        fsm.register(St.A, failing, prevs=[])
        fsm.register(St.ERR, error_callback, prevs=[St.A, St.B, St.C])
        fsm.register_error_state(St.ERR)
        task = fsm.start(St.A)
        task.wait()
        assert fsm.state == St.ERR
        assert entered_error.is_set()

    def test_error_in_error_state_stops_fsm(self):
        def failing():
            t = DelayedTask()
            t.error(ValueError("double fault"))
            return t

        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(St.B), prevs=[])
        fsm.register(St.B, failing, prevs=[St.A])
        fsm.register(St.ERR, failing, prevs=[St.A, St.B, St.C])
        fsm.register_error_state(St.ERR)
        task = fsm.start(St.A)
        with pytest.raises(ValueError, match="double fault"):
            task.wait()

    def test_no_error_state_propagates_error(self):
        def failing():
            t = DelayedTask()
            t.error(ValueError("no fallback"))
            return t

        fsm = FSM(St)
        fsm.register(St.A, failing, prevs=[])
        task = fsm.start(St.A)
        with pytest.raises(ValueError, match="no fallback"):
            task.wait()


class TestFSMHooks:
    def test_on_enter_called(self):
        log = []
        fsm = FSM(St)
        fsm.register(
            St.A, lambda: ImmediateResultTask(St.B), prevs=[],
            on_enter=lambda: log.append("enter_A"),
        )
        fsm.register(
            St.B, lambda: ImmediateResultTask(None), prevs=[St.A],
            on_enter=lambda: log.append("enter_B"),
        )
        fsm.start(St.A).wait()
        assert log == ["enter_A", "enter_B"]

    def test_on_exit_called(self):
        log = []
        fsm = FSM(St)
        fsm.register(
            St.A, lambda: ImmediateResultTask(St.B), prevs=[],
            on_exit=lambda: log.append("exit_A"),
        )
        fsm.register(
            St.B, lambda: ImmediateResultTask(None), prevs=[St.A],
            on_exit=lambda: log.append("exit_B"),
        )
        fsm.start(St.A).wait()
        assert log == ["exit_A", "exit_B"]

    def test_hooks_order(self):
        log = []
        fsm = FSM(St)
        fsm.register(
            St.A, lambda: ImmediateResultTask(St.B), prevs=[],
            on_enter=lambda: log.append("enter_A"),
            on_exit=lambda: log.append("exit_A"),
        )
        fsm.register(
            St.B, lambda: ImmediateResultTask(None), prevs=[St.A],
            on_enter=lambda: log.append("enter_B"),
            on_exit=lambda: log.append("exit_B"),
        )
        fsm.start(St.A).wait()
        assert log == ["enter_A", "exit_A", "enter_B", "exit_B"]


class TestFSMCancel:
    def test_cancel_stops_fsm(self):
        pending = DelayedTask()
        fsm = FSM(St)
        fsm.register(St.A, lambda: pending, prevs=[])
        task = fsm.start(St.A)

        fsm.cancel()
        with pytest.raises(TaskCancelledError):
            task.wait()

    def test_cancel_via_task(self):
        pending = DelayedTask()
        fsm = FSM(St)
        fsm.register(St.A, lambda: pending, prevs=[])
        task = fsm.start(St.A)

        task.cancel()
        with pytest.raises(TaskCancelledError):
            task.wait()

    def test_cancel_when_not_started_is_noop(self):
        fsm = FSM(St)
        fsm.register(St.A, lambda: ImmediateResultTask(None), prevs=[])
        fsm.cancel()


class TestFSMThreaded:
    def test_async_transition(self):
        pending = DelayedTask()
        fsm = FSM(St)
        fsm.register(St.A, lambda: pending, prevs=[])
        fsm.register(St.B, lambda: ImmediateResultTask(None), prevs=[St.A])
        task = fsm.start(St.A)
        assert fsm.state == St.A

        # Complete from another thread
        def producer():
            pending.complete(St.B)

        t = threading.Thread(target=producer)
        t.start()
        task.wait(timeout=1.0)
        t.join(timeout=1.0)
        assert fsm.state == St.B
