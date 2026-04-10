"""Built-in flow control nodes: Entry, IfElse."""

from evo_lib.argtypes import ArgTypes
from evo_lib.graph.graph import Graph, Node, NodeDefinition


class EntryNode(Node):
    def __init__(self, definition: NodeDefinition, name: str, graph: Graph):
        super().__init__(definition, name, graph)

    def on_run(self) -> None:
        output = self.get_flow_output("flow")
        if output is not None:
            output.run()


class EntryNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(EntryNode, "entry", "Entry")
        self.add_flow_output("flow")


class IfElseNode(Node):
    def __init__(self, definition: NodeDefinition, name: str, graph: Graph):
        super().__init__(definition, name, graph)

    def on_run(self) -> None:
        condition = self.get_value_input("condition")
        true_output = self.get_flow_output("true")
        false_output = self.get_flow_output("false")

        if condition is not None and condition.get_value():
            if true_output:
                true_output.run()
            if false_output:
                false_output.ignore()
        else:
            if true_output:
                true_output.ignore()
            if false_output:
                false_output.run()


class IfElseNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(IfElseNode, "if", "If")
        self.add_flow_input("flow")
        self.add_flow_output("true")
        self.add_flow_output("false")
        self.add_value_input("condition", ArgTypes.Bool(), False)
