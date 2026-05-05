"""Pure comparison nodes returning bool.

F32: Eq, Ne, Lt, Le, Gt, Ge.
String: EqStr, NeStr.
Enum:  EqEnum, NeEnum (polymorphic over any enum class).
"""

from typing import Any

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


class _CompareStrNode(Node):
    def _op(self, a: str, b: str) -> bool:
        raise NotImplementedError

    def on_run(self) -> Task[()]:
        a = self.get_value_input("a").get_value()
        b = self.get_value_input("b").get_value()
        self.get_value_output("result").set_value(self._op(a, b))
        return ImmediateResultTask()


class _CompareStrNodeDefinition(NodeDefinition):
    def __init__(self, node_cls: type[Node], name: str, title: str):
        super().__init__(node_cls, name, title)
        self.add_value_input("a", ArgTypes.String(), "")
        self.add_value_input("b", ArgTypes.String(), "")
        self.add_value_output("result", ArgTypes.Bool())


class EqStrNode(_CompareStrNode):
    def _op(self, a: str, b: str) -> bool:
        return a == b


class EqStrNodeDefinition(_CompareStrNodeDefinition):
    def __init__(self):
        super().__init__(EqStrNode, "compare/eq_str", "Eq (str)")


class NeStrNode(_CompareStrNode):
    def _op(self, a: str, b: str) -> bool:
        return a != b


class NeStrNodeDefinition(_CompareStrNodeDefinition):
    def __init__(self):
        super().__init__(NeStrNode, "compare/ne_str", "Ne (str)")


def _enum_equal(a: Any, b: Any) -> bool:
    # Enum members compare equal to their int value (IntEnum) but NOT to their
    # name string. The editor stores the constant as the enum name to keep the
    # combo UX (display "Blue", not "5"), so we fall back to name comparison.
    if a == b:
        return True
    a_name = a.name if hasattr(a, "name") else (a if isinstance(a, str) else None)
    b_name = b.name if hasattr(b, "name") else (b if isinstance(b, str) else None)
    return a_name is not None and a_name == b_name


class _CompareEnumNode(Node):
    def _op(self, a: Any, b: Any) -> bool:
        raise NotImplementedError

    def on_run(self) -> Task[()]:
        a = self.get_value_input("a").get_value()
        b = self.get_value_input("b").get_value()
        self.get_value_output("result").set_value(self._op(a, b))
        return ImmediateResultTask()


class _CompareEnumNodeDefinition(NodeDefinition):
    def __init__(self, node_cls: type[Node], name: str, title: str):
        super().__init__(node_cls, name, title)
        # Shared T so a and b are unified to the same enum class at resolve time.
        T = ArgTypes.AnyEnum()
        self.add_value_input("a", T, 0)
        self.add_value_input("b", T, 0)
        self.add_value_output("result", ArgTypes.Bool())


class EqEnumNode(_CompareEnumNode):
    def _op(self, a: Any, b: Any) -> bool:
        return _enum_equal(a, b)


class EqEnumNodeDefinition(_CompareEnumNodeDefinition):
    def __init__(self):
        super().__init__(EqEnumNode, "compare/eq_enum", "Eq (enum)")


class NeEnumNode(_CompareEnumNode):
    def _op(self, a: Any, b: Any) -> bool:
        return not _enum_equal(a, b)


class NeEnumNodeDefinition(_CompareEnumNodeDefinition):
    def __init__(self):
        super().__init__(NeEnumNode, "compare/ne_enum", "Ne (enum)")
