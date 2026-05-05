"""Core graph types: nodes, endpoints, connections, and definitions.

A graph is a set of nodes connected by execution flow and value connections.
Flow connections describe execution order. Value connections pass data between nodes.
"""

from threading import Lock
from typing import TYPE_CHECKING, Any

from evo_lib.argtypes import ArgType
from evo_lib.graph.node import (
    FlowInput,
    Node,
    TypeEnv,
    ValueInput,
    ValueInputDefinition,
    ValueOutput,
    ValueOutputDefinition,
    resolve,
)
from evo_lib.graph.nodes.flow import CallNodeDefinition, EntryNode, ExitNode
from evo_lib.task import DelayedTask, Task

if TYPE_CHECKING:
    from evo_lib.graph.runner import GraphRunner


class Graph:
    def __init__(self, name: str):
        self._name = name
        self._nodes: dict[str, Node] = {}
        self._call_node_definition = CallNodeDefinition(self)
        self._runner: GraphRunner | None = None
        self._running_graph_task: DelayedTask | None = None
        self._running_nodes_tasks: set[Task] = set()
        self._nb_scheduled_things = 0
        self._lock = Lock()

    def get_name(self) -> str:
        return self._name

    def add_value_input(self, name: str, type: ArgType, default: Any = None) -> None:
        self._call_node_definition.add_value_input(name, type, default)

    def add_value_output(self, name: str, type: ArgType) -> None:
        self._call_node_definition.add_value_output(name, type)

    def add_flow_output(self, name: str) -> None:
        self._call_node_definition.add_flow_output(name)

    def get_value_outputs(self) -> dict[str, ValueOutputDefinition]:
        return self._call_node_definition.get_value_outputs()

    def get_value_inputs(self) -> dict[str, ValueInputDefinition]:
        return self._call_node_definition.get_value_inputs()

    def get_flow_outputs(self) -> list[str]:
        return self._call_node_definition.get_flow_outputs()

    def get_call_node_definition(self) -> CallNodeDefinition:
        return self._call_node_definition

    def is_running(self) -> bool:
        return self._running_graph_task is not None and not self._running_graph_task.is_done()

    def is_terminate(self) -> bool:
        return self._running_graph_task is not None and self._running_graph_task.is_done()

    def get_running_task(self) -> Task[()] | None:
        return self._running_graph_task

    def _check_end(self) -> None:
        assert self._runner is not None
        # Check if nothing is running or pending on the graph,
        # if that the case, complete _running_graph_task
        with self._lock:
            end = len(self._running_nodes_tasks) == 0 and self._nb_scheduled_things == 0
        if end:
            assert self._running_graph_task is not None
            self._running_graph_task.complete()
            self._warn_stale_flow_outputs()
            self._runner.get_logger().debug("Graph finished")

    def _warn_stale_flow_outputs(self) -> None:
        from evo_lib.graph.node import FlowEndpointState

        runner = self.get_runner()
        if runner is None:
            return
        stale: list[str] = []
        for node in self._nodes.values():
            if not node._run_requested:
                continue
            for fo in node.get_flow_outputs():
                if fo._state != FlowEndpointState.WAITING or not fo.get_connections():
                    continue
                targets = ", ".join(
                    f"{c.get_node().get_name()}.{c.get_name()}"
                    for c in fo.get_connections()
                )
                stale.append(f"{node.get_name()}.{fo.get_name()} → ({targets})")
        if stale:
            runner.get_logger().warning(
                f"Graph finished with {len(stale)} stale flow_output(s) "
                f"left dangling: {'; '.join(stale)}"
            )

    def _remove_node_run_task(self, task: Task) -> None:
        with self._lock:
            self._running_nodes_tasks.remove(task)
        self._check_end()

    def _on_node_run_complete(self, task: Task, node: Node) -> None:
        runner = self.get_runner()
        if runner is not None:
            runner.get_logger().debug(
                f"Done node '{node.get_name()}' [{node._fmt_type()}]"
                f"{node._fmt_inputs()}{node._fmt_outputs()}{node._fmt_flow_out()}"
            )
        self._remove_node_run_task(task)

    def _on_node_run_error(self, task: Task, error: Exception) -> None:
        self._remove_node_run_task(task)
        # TODO: Do something with the error

    def _add_node_run_task(self, task: Task) -> None:
        with self._lock:
            self._running_nodes_tasks.add(task)

    def schedule_run_node(self, node: Node) -> None:
        task = node.on_run()
        self._add_node_run_task(task)
        # Task.on_complete spreads the result tuple via *self._result, so the
        # callback must absorb whatever arity the producing node emits.
        task.on_complete(lambda *_args: self._on_node_run_complete(task, node))
        task.on_error(lambda error: self._on_node_run_error(task, error))

    def _do_run_flow_input(self, input_flow: FlowInput) -> None:
        node = input_flow.get_node()
        node.on_run_flow_input(input_flow)
        with self._lock:
            self._nb_scheduled_things -= 1
        self._check_end()

    def schedule_run_flow_input(self, input_flow: FlowInput, delay: float = 0) -> None:
        assert self._runner is not None
        with self._lock:
            self._nb_scheduled_things += 1
        self._runner.get_scheduler().schedule_after(
            delay=delay, priority=0, callback=self._do_run_flow_input, args=(input_flow,)
        )

    def _do_ignore_flow_input(self, input_flow: FlowInput) -> None:
        node = input_flow.get_node()
        node.on_ignore_flow_input(input_flow)
        with self._lock:
            self._nb_scheduled_things -= 1
        self._check_end()

    def schedule_ignore_flow_input(self, input_flow: FlowInput) -> None:
        assert self._runner is not None
        with self._lock:
            self._nb_scheduled_things += 1
        self._runner.get_scheduler().schedule_now(
            priority=0, callback=self._do_ignore_flow_input, args=(input_flow,)
        )

    def _do_set_value_input(self, input_value: ValueInput) -> None:
        input_value.get_node().on_set_value_input(input_value)
        with self._lock:
            self._nb_scheduled_things -= 1
        self._check_end()

    def schedule_set_value_input(self, input_value: ValueInput) -> None:
        assert self._runner is not None
        with self._lock:
            self._nb_scheduled_things += 1
        self._runner.get_scheduler().schedule_now(
            priority=0, callback=self._do_set_value_input, args=(input_value,)
        )

    def _do_pull_value_output(self, output_value: ValueOutput) -> None:
        output_value.on_pull()
        with self._lock:
            self._nb_scheduled_things -= 1
        self._check_end()

    def schedule_pull_value_output(self, output_value: ValueOutput) -> None:
        assert self._runner is not None
        with self._lock:
            self._nb_scheduled_things += 1
        self._runner.get_scheduler().schedule_now(
            priority=0, callback=self._do_pull_value_output, args=(output_value,)
        )

    def get_runner(self) -> GraphRunner | None:
        return self._runner

    def activate(self, runner: GraphRunner) -> None:
        if self._running_graph_task is not None:
            raise RuntimeError("You can only activate a graph that is inactive")
        self._runner = runner
        self._running_graph_task = DelayedTask()
        self._nb_scheduled_things = 0

    def deactivate(self) -> None:
        if not self.is_terminate():
            raise RuntimeError("You can only deactivate a graph that has stop running")
        self._running_graph_task = None
        self._runner = None

    def reset(self) -> None:
        if self.is_running():
            raise RuntimeError("You can only reset a graph that is not running")
        if self.is_terminate():
            self.deactivate()
        for node in self.get_nodes().values():
            node.reset()

    def clone(self) -> "Graph":
        cloned_graph = Graph(self.get_name())

        # Clone flow outputs
        for flow_output in self.get_flow_outputs():
            cloned_graph.add_flow_output(flow_output)

        # Clone value outputs
        for name, value_output in self.get_value_outputs().items():
            cloned_graph.add_value_output(name, value_output.type)

        # Clone value inputs
        for name, value_input in self.get_value_inputs().items():
            cloned_graph.add_value_input(name, value_input.type, value_input.default)

        # Clone nodes
        for node in self.get_nodes().values():
            cloned_node = node.clone()
            cloned_graph.add_node(cloned_node)

        # Relink nodes
        for cloned_node in cloned_graph.get_nodes().values():
            node = self.get_node(cloned_node.get_name())
            assert node is not None

            for cloned_flow_output in cloned_node.get_flow_outputs():
                flow_output = node.get_flow_output(cloned_flow_output.get_name())
                assert flow_output is not None
                for flow_input in flow_output.get_connections():
                    cloned_peer_node = cloned_graph.get_node(flow_input.get_node().get_name())
                    assert cloned_peer_node is not None
                    cloned_flow_input = cloned_peer_node.get_flow_input(flow_input.get_name())
                    assert cloned_flow_input is not None
                    cloned_flow_output.link(cloned_flow_input)

            for cloned_value_output in cloned_node.get_value_outputs():
                value_output = node.get_value_output(cloned_value_output.get_name())
                assert value_output is not None
                for value_input in value_output.get_connections():
                    cloned_peer_node = cloned_graph.get_node(value_input.get_node().get_name())
                    assert cloned_peer_node is not None
                    cloned_value_input = cloned_peer_node.get_value_input(value_input.get_name())
                    assert cloned_value_input is not None
                    cloned_value_output.link(cloned_value_input)

        return cloned_graph

    def get_node(self, name: str) -> Node | None:
        return self._nodes.get(name)

    def get_nodes(self) -> dict[str, Node]:
        return self._nodes

    def get_entry_node(self) -> EntryNode | None:
        for node in self._nodes.values():
            if isinstance(node, EntryNode):
                return node
        return None

    def get_exit_node(self) -> ExitNode | None:
        for node in self._nodes.values():
            if isinstance(node, ExitNode):
                return node
        return None

    def add_node(self, node: Node) -> None:
        if node.get_graph() is not None:
            raise RuntimeError(f"Node '{node.get_name()}' is already part of a graph")
        node.set_graph(self)
        self._nodes[node.get_name()] = node

    def resolve_types(self) -> TypeEnv:
        return resolve(self)
