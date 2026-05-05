"""Tests for AnyEnum / unify / resolve and the IntEnum binary guard."""

import io
from enum import IntEnum, StrEnum

import pytest

from evo_lib.argtypes import (
    ArgTypes,
    TypeMismatchError,
    UnresolvedTypeError,
    argtype_to_stream,
)
from evo_lib.config import ConfigObject
from evo_lib.graph.graph import Graph
from evo_lib.graph.node import Node, NodeDefinition, unify
from evo_lib.graph.nodes.compare import EqEnumNodeDefinition


class _IntColor(IntEnum):
    RED = 0
    GREEN = 1


class _StrMode(StrEnum):
    A = "a"
    B = "b"


def test_unify_concrete_match():
    assert type(unify(ArgTypes.F32(), ArgTypes.F32())) is ArgTypes.F32


def test_unify_concrete_mismatch_raises():
    with pytest.raises(TypeMismatchError):
        unify(ArgTypes.F32(), ArgTypes.I32())


@pytest.mark.parametrize("enum_cls", [_IntColor, _StrMode])
def test_unify_var_with_concrete_binds_either_way(enum_cls):
    var, e = ArgTypes.AnyEnum(), ArgTypes.Enum(enum_cls)
    assert unify(var, e) is e
    assert unify(e, var) is e


def test_unify_two_vars_returns_left():
    v1, v2 = ArgTypes.AnyEnum(), ArgTypes.AnyEnum()
    assert unify(v1, v2) is v1


def test_unify_anyenum_with_non_enum_raises():
    with pytest.raises(TypeMismatchError):
        unify(ArgTypes.AnyEnum(), ArgTypes.F32())


def test_argtype_to_stream_rejects_unresolved_var():
    with pytest.raises(UnresolvedTypeError):
        argtype_to_stream(ArgTypes.AnyEnum(), io.BytesIO())


def test_enum_value_to_stream_intenum_only():
    buf = io.BytesIO()
    ArgTypes.Enum(_IntColor).value_to_stream(_IntColor.GREEN, buf)
    assert buf.getvalue() == (1).to_bytes(4, "little")

    with pytest.raises(TypeError, match="IntEnum"):
        ArgTypes.Enum(_StrMode).value_to_stream(_StrMode.A, io.BytesIO())


class _Stub(Node):
    def on_run(self):
        raise NotImplementedError


def _make_node(definition: NodeDefinition, name: str) -> Node:
    n = definition.instantiate_node(name, ConfigObject())
    definition.create_node_endpoints(n, ConfigObject())
    return n


def test_resolve_propagates_concrete_type_through_eq_enum():
    producer_def = NodeDefinition(_Stub, "test/producer", "Producer")
    producer_def.add_value_output("color", ArgTypes.Enum(_IntColor))
    producer = _make_node(producer_def, "p")

    eq = _make_node(EqEnumNodeDefinition(), "eq")
    producer.get_value_output("color").link(eq.get_value_input("a"))

    graph = Graph("g")
    graph.add_node(producer)
    graph.add_node(eq)
    env = graph.resolve_types()

    bound = env.get("eq", "a")
    assert isinstance(bound, ArgTypes.Enum)
    assert bound.enum_type is _IntColor


def test_resolve_propagates_through_polymorphic_chain():
    """Producer → Forwarder(AnyEnum→AnyEnum) → eq.a: Enum(C) must reach eq.a."""
    producer_def = NodeDefinition(_Stub, "test/producer", "Producer")
    producer_def.add_value_output("color", ArgTypes.Enum(_IntColor))
    producer = _make_node(producer_def, "p")

    forwarder_def = NodeDefinition(_Stub, "test/forwarder", "Forwarder")
    T = ArgTypes.AnyEnum()
    forwarder_def.add_value_input("in", T, 0)
    forwarder_def.add_value_output("out", T)
    fwd = _make_node(forwarder_def, "fwd")

    eq = _make_node(EqEnumNodeDefinition(), "eq")

    producer.get_value_output("color").link(fwd.get_value_input("in"))
    fwd.get_value_output("out").link(eq.get_value_input("a"))

    graph = Graph("g")
    for n in (producer, fwd, eq):
        graph.add_node(n)

    env = graph.resolve_types()
    bound = env.get("eq", "a")
    assert isinstance(bound, ArgTypes.Enum)
    assert bound.enum_type is _IntColor
