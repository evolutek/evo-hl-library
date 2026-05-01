"""Core graph types: nodes, endpoints, connections, and definitions.

A graph is a set of nodes connected by execution flow and value connections.
Flow connections describe execution order. Value connections pass data between nodes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Any

from evo_lib.argtypes import ArgType
from evo_lib.config import ConfigObject, ConfigValidationError
from evo_lib.task import ImmediateResultTask, Task

if TYPE_CHECKING:
    from evo_lib.graph.graph import Graph
    from evo_lib.graph.runner import GraphRunner


# -- Endpoints --


class Endpoint(ABC):
    def __init__(self, node: Node, name: str):
        self._node = node
        self._name = name

    def get_name(self) -> str:
        return self._name

    def get_node(self) -> Node:
        return self._node

    @abstractmethod
    def reset(self) -> None:
        pass


class FlowEndpointState(Enum):
    WAITING = 0
    RUNNED = 1
    IGNORED = 2


class FlowInput(Endpoint):
    def __init__(self, node: Node, name: str):
        super().__init__(node, name)
        self._connections: list[FlowOutput] = []
        self._state: FlowEndpointState = FlowEndpointState.WAITING
        self._nb_ignored_input_connections: int = 0
        self._nb_runned_input_connections: int = 0

    def reset(self) -> None:
        self._state = FlowEndpointState.WAITING
        self._nb_ignored_input_connections = 0
        self._nb_runned_input_connections = 0

    def get_connections(self) -> list[FlowOutput]:
        return self._connections

    def _update_state(self) -> None:
        if self._state != FlowEndpointState.WAITING:
            return
        total_completed_connections = (
            self._nb_runned_input_connections + self._nb_ignored_input_connections
        )
        if total_completed_connections >= len(self._connections):
            if self._nb_runned_input_connections > 0:
                self._state = FlowEndpointState.RUNNED
                self.get_node().get_graph().schedule_run_flow_input(self)
            else:
                self._state = FlowEndpointState.IGNORED
                self.get_node().get_graph().schedule_ignore_flow_input(self)

    def run(self, source: FlowOutput) -> None:
        self._nb_runned_input_connections += 1
        self._update_state()

    def ignore(self, source: FlowOutput) -> None:
        self._nb_ignored_input_connections += 1
        self._update_state()


class FlowOutput(Endpoint):
    def __init__(self, node: Node, name: str):
        super().__init__(node, name)
        self._connections: list[FlowInput] = []
        self._state: FlowEndpointState = FlowEndpointState.WAITING

    def link(self, peer: FlowInput) -> None:
        self._connections.append(peer)
        peer._connections.append(self)

    def get_connections(self) -> list[FlowInput]:
        return self._connections

    def reset(self) -> None:
        self._state = FlowEndpointState.WAITING

    def run(self) -> None:
        assert self._state == FlowEndpointState.WAITING
        # Run every flow input connected to this flow output
        for inp in self._connections:
            inp.run(source=self)
        self._state = FlowEndpointState.RUNNED

    def ignore(self) -> None:
        assert self._state == FlowEndpointState.WAITING
        # Ignore every flow input connected to this flow output
        for inp in self._connections:
            inp.ignore(source=self)
        self._state = FlowEndpointState.IGNORED


@dataclass
class ValueInputDefinition:
    type: ArgType
    default: Any


@dataclass
class ValueOutputDefinition:
    type: ArgType


class ValueEndpoint(Endpoint):
    def __init__(self, node: Node, name: str, type: ArgType):
        super().__init__(node, name)
        self._type = type

    def get_type(self) -> ArgType:
        return self._type


class ValueInput(ValueEndpoint):
    def __init__(self, node: Node, name: str, type: ArgType, default: Any):
        super().__init__(node, name, type)
        self._default: Any = default
        self._value: Any = default
        self._connections: list[ValueOutput] = []

    def reset(self) -> None:
        self._value = self._default

    def get_connections(self) -> list[ValueOutput]:
        return self._connections

    def set_default(self, value: Any) -> None:
        self._default = value
        self._value = value

    def set_value(self, value: Any) -> None:
        self._value = value

    def get_value(self) -> Any:
        return self._value


class ValueOutput(ValueEndpoint):
    def __init__(self, node: Node, name: str, type: ArgType):
        super().__init__(node, name, type)
        self._connections: list[ValueInput] = []

    def get_connections(self) -> list[ValueInput]:
        return self._connections

    def set_value(self, value: Any) -> None:
        for inp in self._connections:
            inp.set_value(value)

    def link(self, peer: ValueInput) -> None:
        self._connections.append(peer)
        peer._connections.append(self)

    def reset(self) -> None:
        pass


# -- Node --


class Node(ABC):
    def __init__(self, definition: NodeDefinition, name: str):
        self._definition = definition
        self._name = name
        self._graph: Graph | None = None
        self._value_inputs: list[ValueInput] = []
        self._value_outputs: list[ValueOutput] = []
        self._flow_inputs: list[FlowInput] = []
        self._flow_outputs: list[FlowOutput] = []
        self._nb_ignored_input_flow: int = 0
        self._nb_runned_input_flow: int = 0

    def clone(self) -> "Node":
        cloned = self.__class__(self._definition, self._name)
        return cloned

    def get_graph(self) -> Graph | None:
        return self._graph

    def set_graph(self, graph: Graph) -> None:
        self._graph = graph

    def get_runner(self) -> GraphRunner:
        runner = self.get_graph().get_runner()
        assert runner is not None
        return runner

    def get_definition(self) -> NodeDefinition:
        return self._definition

    def get_name(self) -> str:
        return self._name

    def get_flow_output(self, name: str) -> FlowOutput | None:
        for ep in self._flow_outputs:
            if ep.get_name() == name:
                return ep
        return None

    def get_flow_input(self, name: str) -> FlowInput | None:
        for ep in self._flow_inputs:
            if ep.get_name() == name:
                return ep
        return None

    def get_value_output(self, name: str) -> ValueOutput | None:
        for ep in self._value_outputs:
            if ep.get_name() == name:
                return ep
        return None

    def get_value_input(self, name: str) -> ValueInput | None:
        for ep in self._value_inputs:
            if ep.get_name() == name:
                return ep
        return None

    def get_value_inputs(self) -> list[ValueInput]:
        return self._value_inputs

    def get_value_outputs(self) -> list[ValueOutput]:
        return self._value_outputs

    def get_flow_inputs(self) -> list[FlowInput]:
        return self._flow_inputs

    def get_flow_outputs(self) -> list[FlowOutput]:
        return self._flow_outputs

    def on_run(self) -> Task[()]:
        """Called when the node is run. By default, this is
        called after all flow inputs has been run.
        This method should return a task that completes when
        the node is done running. The task must not complete
        before all flow output has been runned or ignored.
        Default implement is to run all flow outputs and return
        an immediate result task."""
        for flow_output in self._flow_outputs:
            flow_output.run()
        return ImmediateResultTask()

    def run(self) -> None:
        self.get_runner()._logger.debug(f"Run node '{self.get_name()}'")
        self.get_graph().schedule_run_node(self)

    def ignore(self) -> None:
        self.get_runner()._logger.debug(f"Ignore node '{self.get_name()}'")
        for flow_output in self._flow_outputs:
            flow_output.ignore()

    def reset(self) -> None:
        self._nb_ignored_input_flow = 0
        self._nb_runned_input_flow = 0
        for value_input in self._value_inputs:
            value_input.reset()
        for flow_input in self._flow_inputs:
            flow_input.reset()

    def _check_need_to_run_or_ignore(self) -> None:
        total_completed_connections = self._nb_runned_input_flow + self._nb_ignored_input_flow
        if total_completed_connections == len(self._flow_inputs):
            if self._nb_runned_input_flow > 0:
                self.run()
            else:
                self.ignore()

    def on_run_flow_input(self, input: FlowInput) -> None:
        """Called when a flow input is run."""
        self._nb_runned_input_flow += 1
        self._check_need_to_run_or_ignore()

    def on_ignore_flow_input(self, input: FlowInput) -> None:
        """Called when a flow input is ignored."""
        self._nb_ignored_input_flow += 1
        self._check_need_to_run_or_ignore()


# -- Node definition --


class NodeDefinition:
    def __init__(self, type: type[Node], name: str, title: str):
        self._type = type
        self._name = name
        self._title = title
        self._flow_inputs: set[str] = set()
        self._flow_outputs: set[str] = set()
        self._value_inputs: dict[str, ValueInputDefinition] = {}
        self._value_outputs: dict[str, ValueOutputDefinition] = {}

    def add_flow_input(self, name: str) -> None:
        self._flow_inputs.add(name)

    def add_flow_output(self, name: str) -> None:
        self._flow_outputs.add(name)

    def add_value_input(self, name: str, type: ArgType, default: Any = None) -> None:
        self._value_inputs[name] = ValueInputDefinition(type, default)

    def add_value_output(self, name: str, type: ArgType) -> None:
        self._value_outputs[name] = ValueOutputDefinition(type)

    def get_type(self) -> type[Node]:
        return self._type

    def get_name(self) -> str:
        return self._name

    def get_title(self) -> str:
        return self._title

    def get_value_inputs(self) -> dict[str, ValueInputDefinition]:
        return self._value_inputs

    def get_value_outputs(self) -> dict[str, ValueOutputDefinition]:
        return self._value_outputs

    def get_flow_inputs(self) -> set[str]:
        return self._flow_inputs

    def get_flow_outputs(self) -> set[str]:
        return self._flow_outputs

    def create_node(self, name: str, config: ConfigObject) -> Node:
        """Instantiate a node, create its endpoints, apply config defaults."""
        node = self._type(self, name)

        # Create endpoints (only here, NOT in node constructors)
        for endpoint_name in self._flow_outputs:
            node._flow_outputs.append(FlowOutput(node, endpoint_name))

        for endpoint_name in self._flow_inputs:
            fi = FlowInput(node, endpoint_name)
            node._flow_inputs.append(fi)
            node._nb_ignored_input_flow += 1

        for endpoint_name, endpoint_def in self._value_outputs.items():
            node._value_outputs.append(ValueOutput(node, endpoint_name, endpoint_def.type))

        for endpoint_name, endpoint_def in self._value_inputs.items():
            node._value_inputs.append(
                ValueInput(node, endpoint_name, endpoint_def.type, endpoint_def.default)
            )

        return node

    def _link_flow_output(self, graph: Graph, endpoint: FlowOutput, connections: list[str]) -> None:
        for connection in connections:
            parts = connection.split(":")
            if len(parts) < 1 or len(parts) > 2:
                raise ConfigValidationError(
                    f"Invalid endpoint reference '{connection}' for flow output "
                    f"'{endpoint.get_name()}' of node '{endpoint.get_node().get_name()}'"
                )

            peer_node = graph.get_node(parts[0])
            if peer_node is None:
                raise ConfigValidationError(
                    f"Unknown node '{parts[0]}' referenced from flow output "
                    f"'{endpoint.get_name()}' of node '{endpoint.get_node().get_name()}'"
                )

            if len(parts) == 1:
                peer_inputs = peer_node.get_flow_inputs()
                if len(peer_inputs) != 1:
                    raise ConfigValidationError(
                        f"Ambiguous: node '{parts[0]}' has {len(peer_inputs)} flow inputs, "
                        f"specify which one"
                    )
                endpoint.link(peer_inputs[0])
            else:
                peer_ep = peer_node.get_flow_input(parts[1])
                if peer_ep is None:
                    raise ConfigValidationError(
                        f"Unknown flow input '{parts[1]}' on node '{parts[0]}'"
                    )
                endpoint.link(peer_ep)

    def _link_value_output(
        self, graph: Graph, endpoint: ValueOutput, connections: list[str]
    ) -> None:
        for connection in connections:
            parts = connection.split(":")
            if len(parts) < 1 or len(parts) > 2:
                raise ConfigValidationError(
                    f"Invalid endpoint reference '{connection}' for value output "
                    f"'{endpoint.get_name()}' of node '{endpoint.get_node().get_name()}'"
                )

            peer_node = graph.get_node(parts[0])
            if peer_node is None:
                raise ConfigValidationError(
                    f"Unknown node '{parts[0]}' referenced from value output "
                    f"'{endpoint.get_name()}' of node '{endpoint.get_node().get_name()}'"
                )

            if len(parts) == 1:
                peer_inputs = peer_node.get_value_inputs()
                if len(peer_inputs) != 1:
                    raise ConfigValidationError(
                        f"Ambiguous: node '{parts[0]}' has {len(peer_inputs)} value inputs, "
                        f"specify which one"
                    )
                endpoint.link(peer_inputs[0])
            else:
                peer_ep = peer_node.get_value_input(parts[1])
                if peer_ep is None:
                    raise ConfigValidationError(
                        f"Unknown value input '{parts[1]}' on node '{parts[0]}'"
                    )
                endpoint.link(peer_ep)

    def link_node(self, node: Node, config: ConfigObject) -> None:
        """Connect a node's outputs to other nodes based on config."""
        graph: Graph = node.get_graph()
        connections: list[Any]

        # Connect flow outputs
        flow = config.get_object_or("flow", ConfigObject())
        for endpoint_name in flow.keys():
            connections = flow.get_array(endpoint_name)
            endpoint = node.get_flow_output(endpoint_name)
            if endpoint is None:
                raise ConfigValidationError(
                    f"Unknown flow output '{endpoint_name}' for node type {self.get_name()}"
                )
            self._link_flow_output(graph, endpoint, connections)

        # Connect value outputs
        outputs = config.get_object_or("outputs", ConfigObject())
        for endpoint_name in outputs.keys():
            connections = outputs.get_array(endpoint_name)
            endpoint = node.get_value_output(endpoint_name)
            if endpoint is None:
                raise ConfigValidationError(
                    f"Unknown value output '{endpoint_name}' for node type {self.get_name()}"
                )
            self._link_value_output(graph, endpoint, connections)

    def apply_default_inputs(self, node: Node, config: ConfigObject):
        # Apply config overrides for value input defaults
        config_inputs = config.get_object_or("inputs", ConfigObject())
        for endpoint_name, raw_default_value in config_inputs.items():
            endpoint = node.get_value_input(endpoint_name)
            if endpoint is None:
                raise ConfigValidationError(
                    f"Unknown value input '{endpoint_name}' for node type {self.get_name()}"
                )
            default_value = endpoint.get_type().value_from_config(raw_default_value)
            endpoint.set_default(default_value)
