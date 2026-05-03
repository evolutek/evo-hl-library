"""Tests for the pull-evaluation mechanism (cache, cycle detection, parallel)."""

import pytest

from evo_lib.argtypes import ArgTypes
from evo_lib.config import ConfigObject
from evo_lib.graph.graph import Graph
from evo_lib.graph.node import Node, NodeDefinition
from evo_lib.graph.runner import GraphRunner
from evo_lib.logger import Logger
from evo_lib.scheduler import Scheduler


def _instantiate(definition_cls, name: str) -> Node:
    node_def = definition_cls()
    node = node_def.instantiate_node(name, ConfigObject())
    node_def.create_node_endpoints(node, ConfigObject())
    node_def.config_node_inputs(node, ConfigObject())
    return node


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
