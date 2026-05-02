"""Pure F32 comparison nodes returning bool: Eq, Ne, Lt, Le, Gt, Ge."""

from evo_lib.argtypes import ArgTypes
from evo_lib.graph.node import Node, NodeDefinition
from evo_lib.task import ImmediateResultTask, Task


class _CompareNode(Node):
    def _op(self, a: float, b: float) -> bool:
        raise NotImplementedError

    def on_run(self) -> Task[()]:
        a = self.get_value_input("a").get_value()
        b = self.get_value_input("b").get_value()
        self.get_value_output("result").set_value(self._op(a, b))
        return ImmediateResultTask()


class _CompareNodeDefinition(NodeDefinition):
    def __init__(self, node_cls: type[Node], name: str, title: str):
        super().__init__(node_cls, name, title)
        self.add_value_input("a", ArgTypes.F32(), 0.0)
        self.add_value_input("b", ArgTypes.F32(), 0.0)
        self.add_value_output("result", ArgTypes.Bool())


class EqNode(_CompareNode):
    def _op(self, a: float, b: float) -> bool:
        return a == b


class EqNodeDefinition(_CompareNodeDefinition):
    def __init__(self):
        super().__init__(EqNode, "compare/eq", "Eq")


class NeNode(_CompareNode):
    def _op(self, a: float, b: float) -> bool:
        return a != b


class NeNodeDefinition(_CompareNodeDefinition):
    def __init__(self):
        super().__init__(NeNode, "compare/ne", "Ne")


class LtNode(_CompareNode):
    def _op(self, a: float, b: float) -> bool:
        return a < b


class LtNodeDefinition(_CompareNodeDefinition):
    def __init__(self):
        super().__init__(LtNode, "compare/lt", "Lt")


class LeNode(_CompareNode):
    def _op(self, a: float, b: float) -> bool:
        return a <= b


class LeNodeDefinition(_CompareNodeDefinition):
    def __init__(self):
        super().__init__(LeNode, "compare/le", "Le")


class GtNode(_CompareNode):
    def _op(self, a: float, b: float) -> bool:
        return a > b


class GtNodeDefinition(_CompareNodeDefinition):
    def __init__(self):
        super().__init__(GtNode, "compare/gt", "Gt")


class GeNode(_CompareNode):
    def _op(self, a: float, b: float) -> bool:
        return a >= b


class GeNodeDefinition(_CompareNodeDefinition):
    def __init__(self):
        super().__init__(GeNode, "compare/ge", "Ge")
