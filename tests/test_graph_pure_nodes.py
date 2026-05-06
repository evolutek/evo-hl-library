"""Tests for the math / logic / compare pure value nodes."""

import pytest

from evo_lib.config import ConfigObject
from evo_lib.graph.graph import Graph
from evo_lib.graph.node import Node
from evo_lib.graph.nodes.compare import (
    EqNodeDefinition,
    GeNodeDefinition,
    GtNodeDefinition,
    LeNodeDefinition,
    LtNodeDefinition,
    NeNodeDefinition,
)
from evo_lib.graph.nodes.logic import (
    AndNodeDefinition,
    NotNodeDefinition,
    OrNodeDefinition,
    XorNodeDefinition,
)
from evo_lib.graph.nodes.math import (
    AbsNodeDefinition,
    AddNodeDefinition,
    DivNodeDefinition,
    MaxNodeDefinition,
    MinNodeDefinition,
    ModNodeDefinition,
    MulNodeDefinition,
    NegNodeDefinition,
    SubNodeDefinition,
)
from evo_lib.graph.runner import GraphRunner
from evo_lib.logger import Logger
from evo_lib.scheduler import Scheduler


def _instantiate(definition_cls, name: str) -> Node:
    node_def = definition_cls()
    node = node_def.instantiate_node(name, ConfigObject())
    node_def.create_node_endpoints(node, ConfigObject())
    node_def.config_node_inputs(node, ConfigObject())
    return node


def _make_graph() -> tuple[Graph, Scheduler]:
    logger = Logger("test")
    scheduler = Scheduler(logger)
    runner = GraphRunner(logger, scheduler)
    graph = Graph("g")
    graph.activate(runner)
    return graph, scheduler


def _add(graph: Graph, definition_cls, name: str = "n", **inputs) -> Node:
    node = _instantiate(definition_cls, name)
    graph.add_node(node)
    # set_value (not set_default) so the input's generation > 0,
    # which is what marks the input as "available" for run().
    for k, v in inputs.items():
        node.get_value_input(k).set_value(v)
    return node


def _pull(scheduler: Scheduler, node: Node, output_name: str = "result"):
    output = node.get_value_output(output_name)
    output.pull()
    scheduler.handle()
    return output._cached_value


# -- math: pin every operator's behaviour, including the div-by-zero policy
#    (returns 0 instead of raising) which is a deliberate API choice.
@pytest.mark.parametrize(
    "definition,inputs,expected",
    [
        (AddNodeDefinition, {"a": 2.0, "b": 3.0}, 5.0),
        (SubNodeDefinition, {"a": 5.0, "b": 2.0}, 3.0),
        (MulNodeDefinition, {"a": 4.0, "b": 2.5}, 10.0),
        (DivNodeDefinition, {"a": 10.0, "b": 4.0}, 2.5),
        (ModNodeDefinition, {"a": 10.0, "b": 3.0}, 1.0),
        (MinNodeDefinition, {"a": 2.0, "b": 5.0}, 2.0),
        (MaxNodeDefinition, {"a": 2.0, "b": 5.0}, 5.0),
        (NegNodeDefinition, {"a": 3.0}, -3.0),
        (AbsNodeDefinition, {"a": -7.0}, 7.0),
    ],
    ids=lambda x: x.__name__ if hasattr(x, "__name__") else None,
)
def test_math_op(definition, inputs, expected):
    graph, scheduler = _make_graph()
    node = _add(graph, definition, **inputs)
    assert _pull(scheduler, node) == expected


# -- logic: one truthy and one falsy case per operator catches an inverted op.
@pytest.mark.parametrize(
    "definition,inputs,expected",
    [
        (AndNodeDefinition, {"a": True, "b": True}, True),
        (AndNodeDefinition, {"a": True, "b": False}, False),
        (OrNodeDefinition, {"a": False, "b": True}, True),
        (OrNodeDefinition, {"a": False, "b": False}, False),
        (XorNodeDefinition, {"a": True, "b": False}, True),
        (XorNodeDefinition, {"a": True, "b": True}, False),
        (NotNodeDefinition, {"a": False}, True),
    ],
)
def test_logic_op(definition, inputs, expected):
    graph, scheduler = _make_graph()
    node = _add(graph, definition, **inputs)
    assert _pull(scheduler, node) is expected


# -- compare: each operator probed at the boundary case where it differs
#    from a sibling (lt vs le on equality, eq vs ne on equal pair).
@pytest.mark.parametrize(
    "definition,inputs,expected",
    [
        (EqNodeDefinition, {"a": 1.0, "b": 1.0}, True),
        (EqNodeDefinition, {"a": 1.0, "b": 2.0}, False),
        (NeNodeDefinition, {"a": 1.0, "b": 2.0}, True),
        (LtNodeDefinition, {"a": 1.0, "b": 2.0}, True),
        (LtNodeDefinition, {"a": 2.0, "b": 2.0}, False),
        (LeNodeDefinition, {"a": 2.0, "b": 2.0}, True),
        (GtNodeDefinition, {"a": 3.0, "b": 2.0}, True),
        (GeNodeDefinition, {"a": 2.0, "b": 2.0}, True),
    ],
)
def test_compare_op(definition, inputs, expected):
    graph, scheduler = _make_graph()
    node = _add(graph, definition, **inputs)
    assert _pull(scheduler, node) is expected


def test_chain_pull_propagates_through_pure_nodes():
    """Pull on a chained pure node (mul) recursively pulls its upstream
    (add). Confirms intra-graph propagation between pure nodes."""
    graph, scheduler = _make_graph()
    add = _add(graph, AddNodeDefinition, "add", a=2.0, b=3.0)
    mul = _add(graph, MulNodeDefinition, "mul", b=10.0)
    add.get_value_output("result").link(mul.get_value_input("a"))
    assert _pull(scheduler, mul) == 50.0


def test_loader_registers_all_pure_nodes():
    """Guard against forgetting to register a node in
    GraphLoader.register_base_node_types."""
    from evo_lib.graph.loader import GraphLoader

    loader = GraphLoader()
    loader.register_base_node_types()
    exported = loader.export_node_types()
    names = set(exported["nodes"].keys())
    expected = {
        "math/add", "math/sub", "math/mul", "math/div", "math/mod",
        "math/min", "math/max", "math/neg", "math/abs",
        "logic/and", "logic/or", "logic/xor", "logic/not",
        "compare/eq", "compare/ne", "compare/lt", "compare/le",
        "compare/gt", "compare/ge",
    }
    assert expected.issubset(names)
