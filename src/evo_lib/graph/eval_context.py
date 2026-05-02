"""Per-run evaluation context for pull-based value endpoints.

A ``EvalContext`` is pushed on a thread-local stack at the start of a node
run and popped at the end. Pure nodes (no flow endpoints) use it to cache
their computed outputs for the duration of that run, and to detect cycles.
Each thread has its own current context, so parallel runs are independent.
"""

from itertools import count
from threading import local
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from evo_lib.graph.node import Node


_tick_counter = count(1)
_thread_local = local()


class EvalContext:
    def __init__(self, tick: int):
        self.tick = tick
        self._evaluating: set[int] = set()

    def enter(self, node: "Node") -> None:
        nid = id(node)
        if nid in self._evaluating:
            raise RuntimeError(
                f"Cycle detected while evaluating pure node '{node.get_name()}'"
            )
        self._evaluating.add(nid)

    def exit(self, node: "Node") -> None:
        self._evaluating.discard(id(node))


def next_tick() -> int:
    return next(_tick_counter)


def current_context() -> EvalContext | None:
    return getattr(_thread_local, "ctx", None)


def push_context(ctx: EvalContext) -> EvalContext | None:
    prev = getattr(_thread_local, "ctx", None)
    _thread_local.ctx = ctx
    return prev


def pop_context(prev: EvalContext | None) -> None:
    _thread_local.ctx = prev
