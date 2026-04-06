"""Core graph types: nodes, endpoints, connections, and definitions.

A graph is a set of nodes connected by execution flow and value connections.
Flow connections describe execution order. Value connections pass data between nodes.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any, TYPE_CHECKING

from evo_lib.config import ConfigObject, ConfigValidationError
from evo_lib.argtypes import ArgType

if TYPE_CHECKING:
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

    def reset(self) -> None:
        pass


class FlowInputState(Enum):
    ACTIVE = 0
    INACTIVE = 1
    RUN = 2


class FlowInput(Endpoint):
    def __init__(self, node: Node, name: str):
        super().__init__(node, name)
        self.connections: list[FlowOutput] = []
        self.state: FlowInputState = FlowInputState.ACTIVE

    def reset(self) -> None:
        self.state = FlowInputState.ACTIVE


class FlowOutput(Endpoint):
    def __init__(self, node: Node, name: str):
        super().__init__(node, name)
        self._connections: list[FlowInput] = []

    def link(self, peer: FlowInput) -> None:
        self._connections.append(peer)
        peer.connections.append(self)

    def _run(self) -> None:
        for inp in self._connections:
            inp._node.on_run(self, inp)

    def run(self) -> None:
        self._node.schedule(self._run)

    def _ignore(self) -> None:
        for inp in self._connections:
            inp._node.on_ignore(self, inp)

    def ignore(self) -> None:
        self._node.schedule(self._ignore)


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
        self.type = type


class ValueInput(ValueEndpoint):
    def __init__(self, node: Node, name: str, type: ArgType, default: Any):
        super().__init__(node, name, type)
        self._default: Any = default
        self._value: Any = default
        self._connections: list[ValueOutput] = []

    def reset(self) -> None:
        self._value = self._default

    def get_value(self) -> Any:
        return self._value


class ValueOutput(ValueEndpoint):
    def __init__(self, node: Node, name: str, type: ArgType):
        super().__init__(node, name, type)
        self._connections: list[ValueInput] = []

    def set(self, value: Any) -> None:
        for inp in self._connections:
            inp._value = value

    def link(self, peer: ValueInput) -> None:
        self._connections.append(peer)
        peer._connections.append(self)


# -- Node --

class Node(ABC):
    def __init__(self, definition: NodeDefinition, name: str, graph: Graph):
        self._definition = definition
        self._name = name
        self._graph = graph
        self._value_inputs: list[ValueInput] = []
        self._value_outputs: list[ValueOutput] = []
        self._flow_inputs: list[FlowInput] = []
        self._flow_outputs: list[FlowOutput] = []
        self._nb_active_input_flow: int = 0
        self._nb_run_input_flow: int = 0

    def get_definition(self) -> NodeDefinition:
        return self._definition

    def get_name(self) -> str:
        return self._name

    def schedule(self, callback) -> None:
        """Schedule a callback via the graph runner's scheduler."""
        self._graph._runner._scheduler.schedule_now(0, callback)

    def get_flow_output(self, name: str) -> FlowOutput | None:
        for ep in self._flow_outputs:
            if ep._name == name:
                return ep
        return None

    def get_flow_input(self, name: str) -> FlowInput | None:
        for ep in self._flow_inputs:
            if ep._name == name:
                return ep
        return None

    def get_value_output(self, name: str) -> ValueOutput | None:
        for ep in self._value_outputs:
            if ep._name == name:
                return ep
        return None

    def get_value_input(self, name: str) -> ValueInput | None:
        for ep in self._value_inputs:
            if ep._name == name:
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

    @abstractmethod
    def run(self) -> None:
        pass

    def reset(self) -> None:
        for inp in self._value_inputs:
            inp.reset()

    def on_run(self, _output: FlowOutput, input: FlowInput) -> None:
        assert input.state != FlowInputState.INACTIVE
        if input.state == FlowInputState.ACTIVE:
            input.state = FlowInputState.RUN
            self._nb_run_input_flow += 1
            if self._nb_run_input_flow >= self._nb_active_input_flow:
                self.run()

    def on_ignore(self, _output: FlowOutput, input: FlowInput) -> None:
        assert input.state != FlowInputState.RUN
        if input.state == FlowInputState.ACTIVE:
            input.state = FlowInputState.INACTIVE
            self._nb_active_input_flow -= 1
            if self._nb_active_input_flow == 0:
                for output in self._flow_outputs:
                    output.ignore()


# -- Node definition --

class NodeDefinition[T: Node = Node]:
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

    def create(self, graph: Graph, name: str, config: ConfigObject) -> T:
        """Instantiate a node, create its endpoints, apply config defaults."""
        node = self._type(self, name, graph)

        # Create endpoints (only here, NOT in node constructors)
        for ep_name in self._flow_outputs:
            node._flow_outputs.append(FlowOutput(node, ep_name))

        for ep_name in self._flow_inputs:
            fi = FlowInput(node, ep_name)
            node._flow_inputs.append(fi)
            node._nb_active_input_flow += 1

        for ep_name, ep_def in self._value_outputs.items():
            node._value_outputs.append(ValueOutput(node, ep_name, ep_def.type))

        definition_value_inputs = self._value_inputs
        for ep_name, ep_def in definition_value_inputs.items():
            node._value_inputs.append(ValueInput(node, ep_name, ep_def.type, ep_def.default))

        # Apply config overrides for value input defaults
        config_inputs = config.get_object("inputs", {})
        for ep_name, default_value in config_inputs.items():
            if ep_name not in definition_value_inputs:
                raise ConfigValidationError(
                    f"Unknown value input '{ep_name}' for node type {self.get_name()}"
                )
            node.get_value_input(ep_name)._default = default_value

        return node

    def _link_flow_output(self, graph: Graph, endpoint: FlowOutput, connections: list[str]) -> None:
        for connection in connections:
            parts = connection.split(':')
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

    def _link_value_output(self, graph: Graph, endpoint: ValueOutput, connections: list[str]) -> None:
        for connection in connections:
            parts = connection.split(':')
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

    def link(self, graph: Graph, node: T, config: ConfigObject) -> None:
        """Connect a node's outputs to other nodes based on config."""
        flow = config.get_object("flow", {})
        for ep_name, connections in flow.items():
            ep = node.get_flow_output(ep_name)
            if ep is None:
                raise ConfigValidationError(
                    f"Unknown flow output '{ep_name}' for node type {self.get_name()}"
                )
            self._link_flow_output(graph, ep, connections)

        outputs = config.get_object("outputs", {})
        for ep_name, connections in outputs.items():
            ep = node.get_value_output(ep_name)
            if ep is None:
                raise ConfigValidationError(
                    f"Unknown value output '{ep_name}' for node type {self.get_name()}"
                )
            self._link_value_output(graph, ep, connections)


# -- Graph --

class Graph:
    def __init__(self):
        self._runner: GraphRunner | None = None
        self._nodes: dict[str, Node] = {}

    def get_node(self, name: str) -> Node | None:
        return self._nodes.get(name)

    def get_nodes(self) -> dict[str, Node]:
        return self._nodes

    def add_node(self, node: Node) -> None:
        self._nodes[node.get_name()] = node
