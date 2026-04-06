"""Generic finite state machine.

Each state has a callback that returns a Task[S | None].
When the task resolves to a state, the FSM transitions to it.
When the task resolves to None, the FSM stops.
Transitions are validated via allowed predecessors (previouses).
"""

from enum import Enum
from typing import Callable

from evo_lib.task import Task, DelayedTask


class TransitionError(Exception):
    """Raised when an invalid state transition is attempted."""
    pass


class FSM[S: Enum]:
    """A task-based finite state machine parameterized by a state enum type.

    Example:
        fsm = FSM(MyStates)
        fsm.setup_state(MyStates.WAIT, wait_callback, previouses=[])
        fsm.setup_state(MyStates.RUN, run_callback, previouses=[MyStates.WAIT])
        fsm.start(MyStates.WAIT).on_complete(lambda _: print("done"))
    """

    def __init__(self, states_enum: type[S]):
        self._states_enum = states_enum
        self._callbacks: dict[S, Callable[[], Task[S | None]]] = {}
        self._previouses: dict[S, list[S]] = {}
        self._state: S | None = None
        self._task: DelayedTask | None = None

    def get_state(self) -> S | None:
        """Return the current state, or None if not started."""
        return self._state

    def setup_state(
        self,
        state: S,
        callback: Callable[[], Task[S | None]],
        previouses: list[S],
    ) -> None:
        """Register a state with its callback and allowed predecessors.

        Args:
            state: The state to register.
            callback: Called when entering the state. Must return a Task that
                      resolves to the next state (or None to stop the FSM).
            previouses: List of states allowed to transition into this state.
                        Empty list means this is a valid start state only.
        """
        self._callbacks[state] = callback
        self._previouses[state] = previouses

    def start(self, initial_state: S | None = None) -> Task:
        """Start the FSM from the given state (or the first registered state).

        Returns a Task that completes when the FSM stops (a callback returns None).
        """
        if self._task is not None:
            raise RuntimeError("FSM already started")

        if initial_state is None:
            if not self._callbacks:
                raise RuntimeError("No states registered")
            initial_state = next(iter(self._callbacks))

        if initial_state not in self._callbacks:
            raise TransitionError(f"State {initial_state.value} is not registered")

        self._task = DelayedTask()
        self._enter_state(initial_state)
        return self._task

    def _enter_state(self, state: S) -> None:
        self._state = state
        callback = self._callbacks[state]
        state_task = callback()
        state_task.on_complete(self._on_state_complete)
        state_task.on_error(self._on_state_error)

    def _on_state_complete(self, next_state: S | None) -> None:
        if next_state is None:
            self._task.complete()
            return

        # Validate transition
        allowed = self._previouses.get(next_state, [])
        if self._state not in allowed:
            self._task.error(TransitionError(
                f"Transition from {self._state.value} to {next_state.value} is not allowed"
            ))
            return

        if next_state not in self._callbacks:
            self._task.error(TransitionError(
                f"State {next_state.value} is not registered"
            ))
            return

        self._enter_state(next_state)

    def _on_state_error(self, error: Exception) -> None:
        self._task.error(error)
