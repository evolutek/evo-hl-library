"""Pure boolean logic nodes: And, Or, Not, Xor."""

from evo_lib.argtypes import ArgTypes
from evo_lib.graph.node import Node, NodeDefinition
from evo_lib.task import ImmediateResultTask, Task


class _BinaryBoolNode(Node):
    def _op(self, a: bool, b: bool) -> bool:
        raise NotImplementedError

    def on_run(self) -> Task[()]:
        a = self.get_value_input("a").get_value()
        b = self.get_value_input("b").get_value()
        self.get_value_output("result").set_value(self._op(a, b))
        return ImmediateResultTask()


class _UnaryBoolNode(Node):
    def _op(self, a: bool) -> bool:
        raise NotImplementedError

    def on_run(self) -> Task[()]:
        a = self.get_value_input("a").get_value()
        self.get_value_output("result").set_value(self._op(a))
        return ImmediateResultTask()


class _BinaryBoolNodeDefinition(NodeDefinition):
    def __init__(self, node_cls: type[Node], name: str, title: str):
        super().__init__(node_cls, name, title)
        self.add_value_input("a", ArgTypes.Bool(), False)
        self.add_value_input("b", ArgTypes.Bool(), False)
        self.add_value_output("result", ArgTypes.Bool())


class _UnaryBoolNodeDefinition(NodeDefinition):
    def __init__(self, node_cls: type[Node], name: str, title: str):
        super().__init__(node_cls, name, title)
        self.add_value_input("a", ArgTypes.Bool(), False)
        self.add_value_output("result", ArgTypes.Bool())


class AndNode(_BinaryBoolNode):
    def _op(self, a: bool, b: bool) -> bool:
        return a and b


class AndNodeDefinition(_BinaryBoolNodeDefinition):
    def __init__(self):
        super().__init__(AndNode, "logic/and", "And")


class OrNode(_BinaryBoolNode):
    def _op(self, a: bool, b: bool) -> bool:
        return a or b


class OrNodeDefinition(_BinaryBoolNodeDefinition):
    def __init__(self):
        super().__init__(OrNode, "logic/or", "Or")


class XorNode(_BinaryBoolNode):
    def _op(self, a: bool, b: bool) -> bool:
        return a != b


class XorNodeDefinition(_BinaryBoolNodeDefinition):
    def __init__(self):
        super().__init__(XorNode, "logic/xor", "Xor")


class NotNode(_UnaryBoolNode):
    def _op(self, a: bool) -> bool:
        return not a


class NotNodeDefinition(_UnaryBoolNodeDefinition):
    def __init__(self):
        super().__init__(NotNode, "logic/not", "Not")
