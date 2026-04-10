"""Generic finite state machine.

Each state has a callback that returns a Task[S | None].
When the task resolves to a state, the FSM transitions to it.
When the task resolves to None, the FSM stops.
Transitions are validated via allowed predecessors (prevs).
"""

import logging
from enum import StrEnum
from threading import RLock
from typing import Callable

from evo_lib.task import DelayedTask, Task, TaskCancelledError
from evo_lib.logger import Logger


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""


class FSM[S: StrEnum]:
    """A task-based finite state machine parameterized by a state enum type.

    Thread-safe: transitions are serialized via an internal lock.

    Example:
        fsm = FSM(MyStates)
        fsm.register(MyStates.WAIT, wait_callback, prevs=[])
        fsm.register(MyStates.RUN, run_callback, prevs=[MyStates.WAIT])
        fsm.start(MyStates.WAIT).on_complete(lambda _: print("done"))
    """

    def __init__(self, logger: Logger, states_enum: type[S]):
        self._logger = logger
        self._states_enum = states_enum
        self._callbacks: dict[S, Callable[[], Task[S | None]]] = {}
        self._prevs: dict[S, list[S]] = {}
        self._on_enter: dict[S, Callable[[], None]] = {}
        self._on_exit: dict[S, Callable[[], None]] = {}
        self._error_state: S | None = None
        self._state: S | None = None
        self._task: DelayedTask | None = None
        self._current_state_task: Task | None = None
        self._lock = RLock()

    @property
    def state(self) -> S | None:
        """Return the current state, or None if not started."""
        return self._state

    def register(
        self,
        state: S,
        callback: Callable[[], Task[S | None]],
        prevs: list[S],
        on_enter: Callable[[], None] | None = None,
        on_exit: Callable[[], None] | None = None,
    ) -> None:
        """Register a state with its callback and allowed predecessors.

        Args:
            state: The state to register.
            callback: Called when entering the state. Must return a Task that
                      resolves to the next state (or None to stop the FSM).
            prevs: List of states allowed to transition into this state.
                   Empty list means this is a valid start state only.
            on_enter: Optional hook called before the state callback.
            on_exit: Optional hook called when leaving the state.
        """
        self._callbacks[state] = callback
        self._prevs[state] = prevs
        if on_enter is not None:
            self._on_enter[state] = on_enter
        if on_exit is not None:
            self._on_exit[state] = on_exit

    def register_error_state(self, state: S) -> None:
        """Set a fallback state to enter when an error occurs.

        If set, the FSM transitions to this state instead of stopping on error.
        The error state must be registered and should accept transitions from
        any state (all states should be in its prevs list).
        """
        self._error_state = state

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

            self._task = DelayedTask(self.cancel)
            self._enter_state(initial_state)
            return self._task

    def cancel(self) -> bool:
        """Cancel the FSM externally. Cancels the current state task.

        Returns True if the FSM was running and got cancelled.
        """
        with self._lock:
            if self._task is None or self._task.is_done():
                return False
            if self._current_state_task is not None:
                self._current_state_task.cancel()
            else:
                self._task.error(TaskCancelledError("FSM cancelled"))
            return True

    def _exit_state(self) -> None:
        # Must be called with self._lock held
        if self._state is not None and self._state in self._on_exit:
            self._on_exit[self._state]()

    def _enter_state(self, state: S) -> None:
        # Must be called with self._lock held
        prev = self._state
        self._exit_state()
        self._state = state
        if prev is not None:
            self._logger.debug(f"{prev.value} -> {state.value}")
        else:
            self._logger.debug(f"-> {state.value} (start)")
        if state in self._on_enter:
            self._on_enter[state]()
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
                self._exit_state()
                self._logger.debug(f"{self._state.value} -> (stop)")
                self._task.complete()
                return

            allowed = self._prevs.get(next_state, [])
            if self._state not in allowed:
                self._current_state_task = None
                self._logger.warning(
                    f"Invalid transition {self._state.value} -> {next_state.value}",
                )
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

            if self._error_state is not None and self._state != self._error_state:
                self._logger.error(
                    f"Error in {self._state.value}, entering error state: {error}",
                )
                self._enter_state(self._error_state)
                return

            self._logger.error(f"Error in {self._state.value}: {error}")
            self._task.error(error)
