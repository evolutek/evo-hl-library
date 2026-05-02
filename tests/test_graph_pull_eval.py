"""Tests for the pull-evaluation mechanism (cache, cycle detection, parallel)."""

import threading

import pytest

from evo_lib.argtypes import ArgTypes
from evo_lib.config import ConfigObject
from evo_lib.graph.eval_context import EvalContext, next_tick, pop_context, push_context
from evo_lib.graph.node import Node, NodeDefinition


def _instantiate(definition_cls, name: str) -> Node:
    node_def = definition_cls()
    node = node_def.instantiate_node(name, ConfigObject())
    node_def.create_node_endpoints(node, ConfigObject())
    node_def.config_node_inputs(node, ConfigObject())
    return node


# -- cache: same tick, same compute --


class _CountingNode(Node):
    compute_calls = 0

    def on_compute(self) -> None:
        type(self).compute_calls += 1
        self.get_value_output("result").set_value(42.0)


class _CountingNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(_CountingNode, "test/counting", "Counting")
        self.add_value_output("result", ArgTypes.F32())


def test_cache_reuses_within_same_tick():
    _CountingNode.compute_calls = 0
    node = _instantiate(_CountingNodeDefinition, "c")
    ctx = EvalContext(next_tick())
    prev = push_context(ctx)
    try:
        node.get_value_output("result").pull()
        node.get_value_output("result").pull()
        node.get_value_output("result").pull()
    finally:
        pop_context(prev)
    assert _CountingNode.compute_calls == 1


def test_cache_invalidates_across_ticks():
    _CountingNode.compute_calls = 0
    node = _instantiate(_CountingNodeDefinition, "c")
    for _ in range(3):
        ctx = EvalContext(next_tick())
        prev = push_context(ctx)
        try:
            node.get_value_output("result").pull()
        finally:
            pop_context(prev)
    assert _CountingNode.compute_calls == 3


# -- cycle detection --


class _RefNode(Node):
    upstream_input_name = "x"

    def on_compute(self) -> None:
        x = self.get_value_input(self.upstream_input_name).get_value()
        self.get_value_output("result").set_value(x)


class _RefNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(_RefNode, "test/ref", "Ref")
        self.add_value_input("x", ArgTypes.F32(), 0.0)
        self.add_value_output("result", ArgTypes.F32())


def test_cycle_detection_raises():
    a = _instantiate(_RefNodeDefinition, "a")
    b = _instantiate(_RefNodeDefinition, "b")
    a.get_value_output("result").link(b.get_value_input("x"))
    b.get_value_output("result").link(a.get_value_input("x"))
    with pytest.raises(RuntimeError, match="Cycle detected"):
        a.get_value_output("result").pull()


# -- parallel pulls: per-thread independence --


class _ThreadStampNode(Node):
    """Returns a value derived from a per-instance base. Used as an
    isolation probe under parallel pulls — two threads pull two distinct
    instances and must each see only their own base value."""

    def __init__(self, definition: NodeDefinition, name: str):
        super().__init__(definition, name)
        self.base: float = 0.0

    def on_compute(self) -> None:
        self.get_value_output("result").set_value(self.base + 1.0)


class _ThreadStampNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(_ThreadStampNode, "test/threadstamp", "ThreadStamp")
        self.add_value_output("result", ArgTypes.F32())


def test_parallel_pulls_are_thread_independent():
    """Two threads pull two distinct nodes whose `base` differs.
    Each thread must see only its own result. Confirms the per-thread
    cache and EvalContext stack stay independent under parallel evaluation."""
    n_iter = 200
    seen: dict[int, list[float]] = {0: [], 1: []}

    def worker(idx: int, base: float) -> None:
        node = _instantiate(_ThreadStampNodeDefinition, f"n{idx}")
        node.base = base
        for _ in range(n_iter):
            ctx = EvalContext(next_tick())
            prev = push_context(ctx)
            try:
                seen[idx].append(node.get_value_output("result").pull())
            finally:
                pop_context(prev)

    t0 = threading.Thread(target=worker, args=(0, 100.0))
    t1 = threading.Thread(target=worker, args=(1, 200.0))
    t0.start()
    t1.start()
    t0.join()
    t1.join()

    assert all(v == 101.0 for v in seen[0])
    assert all(v == 201.0 for v in seen[1])
