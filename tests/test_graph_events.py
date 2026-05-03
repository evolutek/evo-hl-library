"""Tests for the pre-scheduling events on Graph (run_node, run_flow_input, ignore_flow_input)."""

from evo_lib.graph.graph import Graph
from evo_lib.graph.node import FlowInput, Node, NodeDefinition
from evo_lib.graph.runner import GraphRunner
from evo_lib.logger import Logger
from evo_lib.scheduler import Scheduler
from evo_lib.task import ImmediateResultTask, Task


class _NoopNode(Node):
    on_run_calls: int = 0

    def on_run(self) -> Task[()]:
        type(self).on_run_calls += 1
        return ImmediateResultTask()


def _make_node_with_flow_input(graph: Graph, name: str = "n") -> Node:
    node_def = NodeDefinition(_NoopNode, "test/noop", "Noop")
    node_def.add_flow_input("flow")
    node = _NoopNode(node_def, name)
    node_def.create_node_endpoints(node, None)
    graph.add_node(node)
    return node


def _activate(graph: Graph) -> None:
    logger = Logger("test")
    scheduler = Scheduler(logger)
    graph.activate(GraphRunner(logger, scheduler))


def test_run_node_event_fires_before_on_run():
    _NoopNode.on_run_calls = 0
    graph = Graph("g")
    node = _make_node_with_flow_input(graph)
    _activate(graph)

    seen: list[tuple[Node, int]] = []
    graph.get_on_run_node_event().register(
        lambda n: seen.append((n, _NoopNode.on_run_calls))
    )

    graph.schedule_run_node(node)

    assert seen == [(node, 0)]
    assert _NoopNode.on_run_calls == 1


def test_run_flow_input_event_fires_with_delay():
    graph = Graph("g")
    node = _make_node_with_flow_input(graph)
    _activate(graph)

    seen: list[tuple[FlowInput, float]] = []
    graph.get_on_run_flow_input_event().register(
        lambda fi, d: seen.append((fi, d))
    )

    fi = node.get_flow_input("flow")
    graph.schedule_run_flow_input(fi, delay=0.25)

    assert seen == [(fi, 0.25)]


def test_ignore_flow_input_event_fires():
    graph = Graph("g")
    node = _make_node_with_flow_input(graph)
    _activate(graph)

    seen: list[FlowInput] = []
    graph.get_on_ignore_flow_input_event().register(seen.append)

    fi = node.get_flow_input("flow")
    graph.schedule_ignore_flow_input(fi)

    assert seen == [fi]


def test_listener_can_unregister_and_stop_receiving():
    graph = Graph("g")
    node = _make_node_with_flow_input(graph)
    _activate(graph)

    seen: list[Node] = []
    listener = graph.get_on_run_node_event().register(seen.append)

    graph.schedule_run_node(node)
    graph.get_on_run_node_event().unregister(listener)
    graph.schedule_run_node(node)

    assert seen == [node]


def test_onetime_listener_fires_once():
    graph = Graph("g")
    node = _make_node_with_flow_input(graph)
    _activate(graph)

    seen: list[Node] = []
    graph.get_on_run_node_event().register(seen.append, onetime=True)

    graph.schedule_run_node(node)
    graph.schedule_run_node(node)

    assert seen == [node]
