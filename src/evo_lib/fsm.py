"""Generic finite state machine.

Each state has a callback that returns a Task[S | None].
When the task resolves to a state, the FSM transitions to it.
When the task resolves to None, the FSM stops.
Transitions are validated via allowed predecessors (prevs).
"""

import threading
from enum import Enum
from typing import Callable

from evo_lib.task import DelayedTask, Task, TaskCancelledError


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


class FSM[S: Enum]:
    """A task-based finite state machine parameterized by a state enum type.

    Thread-safe: transitions are serialized via an internal lock.

    Example:
        fsm = FSM(MyStates)
        fsm.register(MyStates.WAIT, wait_callback, prevs=[])
        fsm.register(MyStates.RUN, run_callback, prevs=[MyStates.WAIT])
        fsm.start(MyStates.WAIT).on_complete(lambda _: print("done"))
    """

    def __init__(self, states_enum: type[S]):
        self._states_enum = states_enum
        self._callbacks: dict[S, Callable[[], Task[S | None]]] = {}
        self._prevs: dict[S, list[S]] = {}
        self._state: S | None = None
        self._task: DelayedTask | None = None
        self._current_state_task: Task | None = None
        self._lock = threading.RLock()

    @property
    def state(self) -> S | None:
        """Return the current state, or None if not started."""
        return self._state

    def register(
        self,
        state: S,
        callback: Callable[[], Task[S | None]],
        prevs: list[S],
    ) -> None:
        """Register a state with its callback and allowed predecessors.

        Args:
            state: The state to register.
            callback: Called when entering the state. Must return a Task that
                      resolves to the next state (or None to stop the FSM).
            prevs: List of states allowed to transition into this state.
                   Empty list means this is a valid start state only.
        """
        self._callbacks[state] = callback
        self._prevs[state] = prevs

    def start(self, initial_state: S) -> Task:
        """Start the FSM from the given initial state.

        The initial state must have prevs=[] (start state).
        Returns a Task that completes when the FSM stops (callback returns None).
        """
        with self._lock:
            if self._task is not None:
                raise RuntimeError("FSM already started")

            if initial_state not in self._callbacks:
                raise TransitionError(f"State {initial_state.value} is not registered")

            if self._prevs[initial_state]:
                raise TransitionError(
                    f"State {initial_state.value} is not a valid start state (prevs is not empty)"
                )

            self._task = DelayedTask()
            self._enter_state(initial_state)
            return self._task

    def cancel(self) -> None:
        """Cancel the FSM externally. Cancels the current state task."""
        with self._lock:
            if self._task is None or self._task.is_done():
                return
            if self._current_state_task is not None:
                self._current_state_task.cancel()
            else:
                self._task.error(TaskCancelledError("FSM cancelled"))

    def _enter_state(self, state: S) -> None:
        # Must be called with self._lock held
        self._state = state
        callback = self._callbacks[state]
        state_task = callback()
        self._current_state_task = state_task
        state_task.on_complete(self._on_state_complete)
        state_task.on_error(self._on_state_error)

    def _on_state_complete(self, next_state: S | None) -> None:
        with self._lock:
            if self._task.is_done():
                return

            if next_state is None:
                self._current_state_task = None
                self._task.complete()
                return

            allowed = self._prevs.get(next_state, [])
            if self._state not in allowed:
                self._current_state_task = None
                self._task.error(
                    TransitionError(
                        f"Transition from {self._state.value} to {next_state.value} is not allowed"
                    )
                )
                return

            self._enter_state(next_state)

    def _on_state_error(self, error: Exception) -> None:
        with self._lock:
            if self._task.is_done():
                return
            self._current_state_task = None
            self._task.error(error)
