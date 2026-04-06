"""Graph loader: builds a Graph from JSON5 config and node definitions."""

from evo_lib.registry import Registry
from evo_lib.config import ConfigObject
from evo_lib.argtypes import argtype_to_config

from evo_lib.graph.graph import Graph, NodeDefinition

from evo_lib.graph.nodes.utils import WaitNodeDefinition
from evo_lib.graph.nodes.flow import IfElseNodeDefinition, EntryNodeDefinition


class GraphLoader:
    def __init__(self):
        self._node_definitions: Registry[NodeDefinition] = Registry("node_definitions")

    def register_node(self, node: NodeDefinition) -> None:
        self._node_definitions.register(node.get_name(), node)

    def register_base_nodes(self) -> None:
        """Register built-in node types."""
        self.register_node(WaitNodeDefinition())
        self.register_node(IfElseNodeDefinition())
        self.register_node(EntryNodeDefinition())

    def export_nodes(self) -> ConfigObject:
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
                vi_entry = vi_config.create_object(name)
                vi_entry["type"] = argtype_to_config(vi.type)
                vi_entry["default"] = vi.default

            vo_config = node_config.create_object("value_outputs")
            for name, vo in node_def.get_value_outputs().items():
                vo_entry = vo_config.create_object(name)
                vo_entry["type"] = argtype_to_config(vo.type)

        return config

    def load_config(self, config: ConfigObject) -> Graph:
        """Build a Graph from a config object."""
        graph = Graph()

        # Create nodes
        for name, node_config in config.items():
            node_type = node_config.get_str("type")
            node_def = self._node_definitions.get(node_type)
            graph.add_node(node_def.create(graph, name, node_config))

        # Link nodes
        for node_name, node in graph.get_nodes().items():
            node_config = config.get_object(node_name)
            node.get_definition().link(graph, node, node_config)

        return graph
