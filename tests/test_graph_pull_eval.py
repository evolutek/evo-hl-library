"""Tests for the pull-evaluation mechanism on pure value nodes."""

from evo_lib.argtypes import ArgTypes
from evo_lib.config import ConfigObject
from evo_lib.graph.graph import Graph
from evo_lib.graph.node import Node, NodeDefinition
from evo_lib.graph.runner import GraphRunner
from evo_lib.logger import Logger
from evo_lib.scheduler import Scheduler


class _PureNode(Node):
    pass


class _PureNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(_PureNode, "test/pure", "Pure")
        self.add_value_input("x", ArgTypes.F32(), 0.0)
        self.add_value_output("result", ArgTypes.F32())


def _make_node_in_active_graph() -> tuple[Graph, _PureNode]:
    node_def = _PureNodeDefinition()
    node = node_def.instantiate_node("n", ConfigObject())
    node_def.create_node_endpoints(node, ConfigObject())
    node_def.config_node_inputs(node, ConfigObject())

    graph = Graph("g")
    graph.add_node(node)

    logger = Logger("test")
    scheduler = Scheduler(logger)
    runner = GraphRunner(logger, scheduler)
    graph.activate(runner)
    return graph, node


def test_value_output_pull_routes_through_scheduler():
    """ValueOutput.pull() must enqueue a callback on the graph rather
    than calling on_pull synchronously: this is what breaks the call
    stack on chained pure nodes."""
    graph, node = _make_node_in_active_graph()
    output = node.get_value_output("result")

    before = graph._nb_scheduled_things
    output.pull()
    after = graph._nb_scheduled_things

    assert after == before + 1
