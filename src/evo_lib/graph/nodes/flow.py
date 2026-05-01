"""Built-in flow control nodes: Entry, IfElse."""

from typing import TYPE_CHECKING, override

from evo_lib.argtypes import ArgTypes
from evo_lib.graph.node import FlowInput, Node, NodeDefinition, ValueInput, ValueOutput
from evo_lib.task import ImmediateErrorTask, ImmediateResultTask, Task

if TYPE_CHECKING:
    from evo_lib.graph.graph import Graph


class EntryNode(Node):
    def __init__(self, definition: NodeDefinition, name: str):
        super().__init__(definition, name)

    @override
    def set_graph(self, graph: Graph) -> None:
        super().set_graph(graph)
        # Override set_graph to configure this node value and flow outputs
        self._value_outputs.clear()
        for name, output in graph.get_value_inputs().items():
            self._value_outputs.append(ValueOutput(self, name, output.type))
        # self._flow_outputs.clear()
        # for name in graph.get_flow_inputs():
        #     self._flow_outputs.append(FlowOutput(name))

    def on_run(self) -> Task[()]:
        output = self.get_flow_output("next")
        if output is not None:
            output.run()
        return ImmediateResultTask()


class EntryNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(EntryNode, "graph:entry", "Entry")
        self.add_flow_output("next")


class ExitNode(Node):
    def __init__(self, definition: NodeDefinition, name: str):
        super().__init__(definition, name)
        self._caller_node: CallNode | None = None

    def set_caller_node(self, node: CallNode) -> None:
        self._caller_node = node

    @override
    def set_graph(self, graph: Graph) -> None:
        super().set_graph(graph)
        # Override set_graph to configure this node value and flow inputs
        self._value_inputs.clear()
        for name, output in graph.get_value_outputs().items():
            self._value_inputs.append(ValueInput(self, name, output.type, None))
        self._flow_inputs.clear()
        for name in graph.get_flow_outputs():
            self._flow_inputs.append(FlowInput(self, name))

    @override
    def on_run_flow_input(self, input: FlowInput) -> None:
        if self._caller_node is not None:
            caller_flow_input = self._caller_node.get_flow_output(input.get_name())
            assert caller_flow_input is not None
            caller_flow_input.run()

    @override
    def on_ignore_flow_input(self, input: FlowInput) -> None:
        if self._caller_node is not None:
            caller_flow_input = self._caller_node.get_flow_output(input.get_name())
            assert caller_flow_input is not None
            caller_flow_input.ignore()


class ExitNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(ExitNode, "graph:exit", "Exit")
        self.add_flow_input("flow")


class CallNode(Node):
    def __init__(self, definition: CallNodeDefinition, name: str):
        super().__init__(definition, name)
        # Clone the called graph because each running graph needs to be a separate instance
        self._called_graph = definition.get_called_graph().clone()

    def on_run(self) -> Task[()]:
        entry_node = self._called_graph.get_entry_node()
        if entry_node is None:
            return ImmediateErrorTask(RuntimeError("No entry node found in called graph"))

        exit_node = self._called_graph.get_exit_node()
        if exit_node is not None:
            exit_node.set_caller_node(self)

        # Set value inputs of the entry node from the calling graph
        for self_value_input in self.get_value_inputs():
            entry_value_input = entry_node.get_value_output(self_value_input.get_name())
            if entry_value_input is not None:
                entry_value_input.set_value(self_value_input.get_value())

        # Activate the subgraph so it can be run and event nodes can be called
        self._called_graph.activate(self.get_runner())

        # Run the subgraph
        entry_node.run()
        running_task = self._called_graph.get_running_task()
        assert running_task is not None

        return running_task

    @override
    def reset(self) -> None:
        super().reset()
        self._called_graph.reset()


class CallNodeDefinition(NodeDefinition):
    def __init__(self, called_graph: Graph):
        super().__init__(CallNode, f"graph:call:{called_graph.get_name()}", "Call")
        self._graph = called_graph
        self.add_flow_input("flow")

    def get_called_graph(self) -> Graph:
        return self._graph


class IfElseNode(Node):
    def __init__(self, definition: NodeDefinition, name: str):
        super().__init__(definition, name)

    def on_run(self) -> Task[()]:
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

        return ImmediateResultTask()


class IfElseNodeDefinition(NodeDefinition):
    def __init__(self):
        super().__init__(IfElseNode, "if", "If")
        self.add_flow_input("flow")
        self.add_flow_output("true")
        self.add_flow_output("false")
        self.add_value_input("condition", ArgTypes.Bool(), False)
