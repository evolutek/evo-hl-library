"""Graph loader: builds a Graph from JSON5 config and node definitions."""

from evo_lib.argtypes import argtype_from_config, argtype_to_config
from evo_lib.config import ConfigObject
from evo_lib.graph.graph import Graph
from evo_lib.graph.node import NodeDefinition
from evo_lib.graph.nodes.compare import (
    EqNodeDefinition,
    EqStrNodeDefinition,
    GeNodeDefinition,
    GtNodeDefinition,
    LeNodeDefinition,
    LtNodeDefinition,
    NeNodeDefinition,
    NeStrNodeDefinition,
)
from evo_lib.graph.nodes.flow import EntryNodeDefinition, ExitNodeDefinition, IfElseNodeDefinition
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
from evo_lib.graph.nodes.utils import WaitNodeDefinition
from evo_lib.registry import Registry


class GraphLoader:
    def __init__(self):
        self._node_definitions: Registry[NodeDefinition] = Registry("node_definitions")
        self._partially_loaded_graphes: dict[str, tuple[Graph, ConfigObject]] = {}

    def register_node_type(self, node: NodeDefinition) -> None:
        self._node_definitions.register(node.get_name(), node)

    def register_base_node_types(self) -> None:
        """Register built-in node types."""
        self.register_node_type(WaitNodeDefinition())
        self.register_node_type(IfElseNodeDefinition())
        self.register_node_type(EntryNodeDefinition())
        self.register_node_type(ExitNodeDefinition())
        # Pure math
        self.register_node_type(AddNodeDefinition())
        self.register_node_type(SubNodeDefinition())
        self.register_node_type(MulNodeDefinition())
        self.register_node_type(DivNodeDefinition())
        self.register_node_type(ModNodeDefinition())
        self.register_node_type(MinNodeDefinition())
        self.register_node_type(MaxNodeDefinition())
        self.register_node_type(NegNodeDefinition())
        self.register_node_type(AbsNodeDefinition())
        # Pure logic
        self.register_node_type(AndNodeDefinition())
        self.register_node_type(OrNodeDefinition())
        self.register_node_type(XorNodeDefinition())
        self.register_node_type(NotNodeDefinition())
        # Pure comparisons
        self.register_node_type(EqNodeDefinition())
        self.register_node_type(NeNodeDefinition())
        self.register_node_type(LtNodeDefinition())
        self.register_node_type(LeNodeDefinition())
        self.register_node_type(GtNodeDefinition())
        self.register_node_type(GeNodeDefinition())
        self.register_node_type(EqStrNodeDefinition())
        self.register_node_type(NeStrNodeDefinition())

    def export_node_types(self) -> ConfigObject:
        """Export all registered node definitions as a config object."""
        config = ConfigObject()
        config["version"] = 1

        nodes_config = config.create_object("nodes")
        for node_def in self._node_definitions.get_all():
            node_config = nodes_config.create_object(node_def.get_name())
            node_config["title"] = node_def.get_title()
            node_config["flow_inputs"] = list(node_def.get_flow_inputs())
            node_config["flow_outputs"] = list(node_def.get_flow_outputs())

            vi_config = node_config.create_object("value_inputs")
            for name, vi in node_def.get_value_inputs().items():
                vi_entry = argtype_to_config(vi.type)
                vi_entry["default"] = vi.default
                vi_config[name] = vi_entry

            vo_config = node_config.create_object("value_outputs")
            for name, vo in node_def.get_value_outputs().items():
                vo_entry = argtype_to_config(vo.type)
                vo_config[name] = vo_entry

        return config

    def partially_load_graph(self, name: str, config: ConfigObject) -> Graph:
        """Load a Graph from a config object.
        To finalize the loading, call `finalize_loading_graphes`.
        Graph loading is stopped in two steps because, some graph
        can call other graphs, so graph objects must instantiate
        first before their nodes can be loaded (their can be a
        subgraph call node that is linked to another graph)."""

        if name in self._partially_loaded_graphes:
            raise ValueError(f"Graph {name} is already partially loaded")

        graph = Graph(name)

        # Create value inputs
        value_inputs_config = config.get_object_or("value_inputs", ConfigObject())
        for input_name in value_inputs_config.keys():
            input_config = value_inputs_config.get_object(input_name)
            input_type = argtype_from_config(input_config)
            raw_default = input_config.get("default", None)
            default_value = (
                input_type.value_from_config(raw_default) if raw_default is not None else None
            )
            graph.add_value_input(input_name, input_type, default_value)

        # Create value outputs
        value_outputs_config = config.get_object_or("value_outputs", ConfigObject())
        for output_name in value_outputs_config.keys():
            output_config = value_outputs_config.get_object(output_name)
            output_type = argtype_from_config(output_config)
            graph.add_value_output(name, output_type)

        # Create flow outputs
        flow_outputs_config = config.get_array_or("flow_outputs", [])
        for flow_output_name in flow_outputs_config:
            graph.add_flow_output(flow_output_name)

        call_node_definition = graph.get_call_node_definition()
        self.register_node_type(call_node_definition)

        self._partially_loaded_graphes[name] = (graph, config)

        return graph

    def finalize_loading_graphes(self) -> None:
        """Finalize loading of all partially loaded graphs
        (i.e., create nodes and link them).
        This method should be called after all graphs have been
        partially loaded."""

        for graph, config in self._partially_loaded_graphes.values():
            # Create nodes for all graphs
            nodes_config = config.get_object("nodes")
            for node_name in nodes_config.keys():
                node_config = nodes_config.get_object(node_name)
                node_type = node_config.get_str("type")
                node_def = self._node_definitions.get(node_type)
                node = node_def.instantiate_node(node_name, node_config)
                node_def.create_node_endpoints(node, node_config)
                graph.add_node(node)

            # Link nodes and apply config default inputs
            for node_name, node in graph.get_nodes().items():
                node_config = nodes_config.get_object(node_name)
                node_def = node.get_definition()
                node_def.link_node_endpoints(node, node_config)
                node_def.config_node_inputs(node, node_config)
                # Reset to be sure to be in the correct state to run
                node.reset()

        self._partially_loaded_graphes.clear()
