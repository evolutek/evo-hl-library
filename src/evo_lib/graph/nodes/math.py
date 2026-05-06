"""Pure arithmetic nodes: Add, Sub, Mul, Div, Mod, Neg, Abs, Min, Max."""

from evo_lib.argtypes import ArgTypes
from evo_lib.graph.node import Node, NodeDefinition
from evo_lib.task import ImmediateResultTask, Task


class _BinaryF32Node(Node):
    """Base for two-input one-output F32 ops. Subclasses override _op."""

    def _op(self, a: float, b: float) -> float:
        raise NotImplementedError

    def on_run(self) -> Task[()]:
        a = self.get_value_input("a").get_value()
        b = self.get_value_input("b").get_value()
        self.get_value_output("result").set_value(self._op(a, b))
        return ImmediateResultTask()


class _UnaryF32Node(Node):
    def _op(self, a: float) -> float:
        raise NotImplementedError

    def on_run(self) -> Task[()]:
        a = self.get_value_input("a").get_value()
        self.get_value_output("result").set_value(self._op(a))
        return ImmediateResultTask()


class _BinaryF32NodeDefinition(NodeDefinition):
    def __init__(self, node_cls: type[Node], name: str, title: str):
        super().__init__(node_cls, name, title)
        self.add_value_input("a", ArgTypes.F32(), 0.0)
        self.add_value_input("b", ArgTypes.F32(), 0.0)
        self.add_value_output("result", ArgTypes.F32())


class _UnaryF32NodeDefinition(NodeDefinition):
    def __init__(self, node_cls: type[Node], name: str, title: str):
        super().__init__(node_cls, name, title)
        self.add_value_input("a", ArgTypes.F32(), 0.0)
        self.add_value_output("result", ArgTypes.F32())


class AddNode(_BinaryF32Node):
    def _op(self, a: float, b: float) -> float:
        return a + b


class AddNodeDefinition(_BinaryF32NodeDefinition):
    def __init__(self):
        super().__init__(AddNode, "math/add", "Add")


class SubNode(_BinaryF32Node):
    def _op(self, a: float, b: float) -> float:
        return a - b


class SubNodeDefinition(_BinaryF32NodeDefinition):
    def __init__(self):
        super().__init__(SubNode, "math/sub", "Sub")


class MulNode(_BinaryF32Node):
    def _op(self, a: float, b: float) -> float:
        return a * b


class MulNodeDefinition(_BinaryF32NodeDefinition):
    def __init__(self):
        super().__init__(MulNode, "math/mul", "Mul")


class DivNode(_BinaryF32Node):
    def _op(self, a: float, b: float) -> float:
        # Let ZeroDivisionError propagate (don't silence /0).
        return a / b


class DivNodeDefinition(_BinaryF32NodeDefinition):
    def __init__(self):
        super().__init__(DivNode, "math/div", "Div")


class ModNode(_BinaryF32Node):
    def _op(self, a: float, b: float) -> float:
        return a % b if b != 0.0 else 0.0


class ModNodeDefinition(_BinaryF32NodeDefinition):
    def __init__(self):
        super().__init__(ModNode, "math/mod", "Mod")


class MinNode(_BinaryF32Node):
    def _op(self, a: float, b: float) -> float:
        return a if a < b else b


class MinNodeDefinition(_BinaryF32NodeDefinition):
    def __init__(self):
        super().__init__(MinNode, "math/min", "Min")


class MaxNode(_BinaryF32Node):
    def _op(self, a: float, b: float) -> float:
        return a if a > b else b


class MaxNodeDefinition(_BinaryF32NodeDefinition):
    def __init__(self):
        super().__init__(MaxNode, "math/max", "Max")


class NegNode(_UnaryF32Node):
    def _op(self, a: float) -> float:
        return -a


class NegNodeDefinition(_UnaryF32NodeDefinition):
    def __init__(self):
        super().__init__(NegNode, "math/neg", "Neg")


class AbsNode(_UnaryF32Node):
    def _op(self, a: float) -> float:
        return a if a >= 0.0 else -a


class AbsNodeDefinition(_UnaryF32NodeDefinition):
    def __init__(self):
        super().__init__(AbsNode, "math/abs", "Abs")
