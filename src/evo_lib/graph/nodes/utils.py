"""Built-in utility nodes: Wait."""

from evo_lib.argtypes import ArgTypes
from evo_lib.graph.graph import Graph, Node, NodeDefinition
from evo_lib.task import ImmediateResultTask, Task


class WaitNode(Node):
    def __init__(self, definition: NodeDefinition, name: str, graph: Graph):
        super().__init__(definition, name, graph)

    def on_run(self) -> Task[()]:
        delay_input = self.get_value_input("delay")
        delay = delay_input.get_value() if delay_input else 0
        output = self.get_flow_output("next")
        if output is not None:
            for input in output.get_connections():
                self.get_graph().schedule_run_flow_input(input, delay)
        return ImmediateResultTask()


class WaitNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(WaitNode, "wait", "Wait")
        self.add_flow_input("flow")
        self.add_flow_output("next")
        self.add_value_input("delay", ArgTypes.F32(), 0)
